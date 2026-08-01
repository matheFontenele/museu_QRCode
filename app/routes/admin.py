import os
import io
import qrcode
import math
import secrets
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse, HTMLResponse # <-- IMPORTANTE: HTMLResponse adicionado
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import models, database
from urllib.parse import quote

# Carrega as variáveis do arquivo .env (segurança local)
load_dotenv()

# ========== CONFIGURAÇÃO CLOUDINARY ==========
cloudinary.config( 
  cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"), 
  api_key = os.getenv("CLOUDINARY_API_KEY"), 
  api_secret = os.getenv("CLOUDINARY_API_SECRET") 
)

PASTA_BASE = os.getenv("CLOUDINARY_FOLDER", "museu")
router = APIRouter()
security = HTTPBasic()

# ========== FUNÇÃO DE VERIFICAÇÃO DE ACESSO ==========
def verificar_credenciais(credentials: HTTPBasicCredentials = Depends(security)):
    # Defina aqui o Usuário e Senha mestre do painel
    USUARIO_CERTO = "admin"
    SENHA_CERTA = "museu123"
    
    # O compare_digest protege contra ataques de timing na verificação de string
    usuario_correto = secrets.compare_digest(credentials.username, USUARIO_CERTO)
    senha_correta = secrets.compare_digest(credentials.password, SENHA_CERTA)
    
    if not (usuario_correto and senha_correta):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso Negado. Credenciais Inválidas.",
            headers={"WWW-Authenticate": "Basic"}, # Força a caixinha de login no navegador
        )
    return credentials.username

# Garantia absoluta do caminho dos templates no Docker
templates = Jinja2Templates(directory="/code/app/templates")

# ====== ROTAS ======

@router.get("/")
def painel_admin(
    request: Request, 
    page: int = 1, # Lê a página atual da URL (padrão é 1)
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO
):
    itens_por_pagina = 9
    
    # 1. Descobre o total de peças cadastradas no banco
    total_pecas = db.query(models.Peca).count()
    
    # 2. Calcula o total de páginas arredondando para cima
    total_paginas = math.ceil(total_pecas / itens_por_pagina) if total_pecas > 0 else 1
    
    # 3. Trava de segurança (se o usuário digitar uma página que não existe na URL)
    if page < 1:
        page = 1
    elif page > total_paginas and total_paginas > 0:
        page = total_paginas
        
    # 4. Calcula o ponto de partida no banco de dados (Offset)
    offset = (page - 1) * itens_por_pagina
    
    # 5. Busca apenas os 9 itens daquela página específica
    pecas = db.query(models.Peca).order_by(models.Peca.id.desc()).limit(itens_por_pagina).offset(offset).all()
    
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html", 
        context={
            "pecas": pecas,
            "page": page,
            "total_pages": total_paginas,
            "total_pecas": total_pecas
        }
    )

# ====== ROTA: CADASTRAR PEÇA ======
@router.post("/cadastrar")
async def cadastrar_peca(
    request: Request,
    titulo: str = Form(...),
    descricao: str = Form(...),
    fotos: list[UploadFile] = File(default=[]),
    youtube_links: list[str] = Form(default=[]),
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO
):  
    # Filtra para não contar campos vazios
    fotos_validas = [f for f in fotos if f.filename]
    links_validos = [link.strip() for link in youtube_links if link.strip()]
    
    # Travas de segurança elegantes para limite
    if len(fotos_validas) > 6:
        msg = quote("Limite excedido: Máximo de 6 fotos.")
        return RedirectResponse(url=f"/admin?erro={msg}", status_code=303)
    
    if len(links_validos) > 6:
        msg = quote("Limite excedido: Máximo de 6 vídeos.")
        return RedirectResponse(url=f"/admin?erro={msg}", status_code=303)
    
    try:
        nova_peca = models.Peca(titulo=titulo, descricao=descricao)
        db.add(nova_peca)
        db.commit()
        db.refresh(nova_peca)
        
        # 1. Gera o QR Code na memória e faz o upload pro Cloudinary
        base_url = str(request.base_url).rstrip("/")
        url_publica = f"{base_url}/peca/{nova_peca.id}"        
        qr = qrcode.make(url_publica)
        
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)
        
        # CORREÇÃO: f-string aplicada
        upload_qr = cloudinary.uploader.upload(buffer, folder=f"{PASTA_BASE}/qrcodes")
        nova_peca.qr_code_path = upload_qr["secure_url"] # Salva o link seguro do Cloudinary
        db.commit()
        
        # 2. Upload das Fotos Unitárias direto pro Cloudinary
        for arquivo in fotos_validas:
            try:
                # CORREÇÃO: f-string aplicada
                upload_foto = cloudinary.uploader.upload(arquivo.file, folder=f"{PASTA_BASE}/fotos")
                
                nova_midia = models.Midia(
                    peca_id=nova_peca.id,
                    tipo="foto",
                    url_path=upload_foto["secure_url"], # Link seguro do Cloudinary
                    legenda=f"Foto do artefato: {titulo}"
                )
                db.add(nova_midia)
            except Exception as e:
                print(f"Erro ao subir foto: {e}")
                continue
                
        # 3. Processamento dos Links do YouTube
        for link in links_validos:
            nova_midia = models.Midia(
                peca_id=nova_peca.id,
                tipo="video",
                url_path=link,
                legenda=f"Vídeo do artefato: {titulo}"
            )
            db.add(nova_midia)
        
        db.commit()
        return RedirectResponse(url="/admin", status_code=303)
    
    except Exception as e:      
        db.rollback()
        raise
        
# ====== ROTA: ATUALIZAR (UPDATE) ======
@router.post("/editar/{peca_id}")
async def editar_peca(
    peca_id: int,
    titulo: str = Form(...),
    descricao: str = Form(...),
    midias_para_excluir: list[int] = Form(default=[]),
    novas_fotos: list[UploadFile] = File(default=[]),
    novos_youtube_links: str = Form(default=""),
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO
):
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    if not peca: 
        return RedirectResponse(url="/admin", status_code=303)
    
    try:
        # 1. Filtra as entradas válidas
        fotos_validas = [f for f in novas_fotos if f.filename]
        links_validos = [link.strip() for link in novos_youtube_links.split('\n') if link.strip()]

        # 2. Calcula como vai ficar o total
        fotos_atuais = len([m for m in peca.midias if m.tipo == 'foto' and m.id not in midias_para_excluir])
        videos_atuais = len([m for m in peca.midias if m.tipo == 'video' and m.id not in midias_para_excluir])
        
        # 3. Trava de segurança
        if (fotos_atuais + len(fotos_validas)) > 6 or (videos_atuais + len(links_validos)) > 6:
            msg = quote("A peça não pode ter mais de 6 fotos ou 6 vídeos no total. Nenhuma alteração foi salva.")
            return RedirectResponse(url=f"/admin?erro={msg}", status_code=303)

        # 4. Atualiza os textos
        peca.titulo = titulo
        peca.descricao = descricao
        
        # 5. Processa a exclusão das mídias antigas do Banco de Dados
        for midia_id in midias_para_excluir:
            midia_obj = db.query(models.Midia).filter(models.Midia.id == midia_id, models.Midia.peca_id == peca_id).first()
            if midia_obj:
                db.delete(midia_obj) 
        
        # Salva as exclusões
        db.commit()
        db.refresh(peca)

        # 6. Adiciona as Novas Fotos no Cloudinary
        for arquivo in fotos_validas:
            # CORREÇÃO: Variável PASTA_BASE aplicada na edição
            upload_foto = cloudinary.uploader.upload(arquivo.file, folder=f"{PASTA_BASE}/fotos")
            
            nova_midia = models.Midia(
                peca_id=peca.id, tipo="foto",
                url_path=upload_foto["secure_url"],
                legenda=f"Foto do artefato: {titulo}"
            )
            db.add(nova_midia)
            
        # 7. Adiciona os Novos Links do YouTube
        for link in links_validos:
            nova_midia = models.Midia(
                peca_id=peca.id, tipo="video",
                url_path=link, legenda=f"Vídeo do artefato: {titulo}"
            )
            db.add(nova_midia)

        db.commit()
        return RedirectResponse(url="/admin", status_code=303)

    except Exception as e:
        db.rollback()
        raise
    
# ====== ROTA DE DELETAR (DELETE) ======
@router.post("/deletar/{peca_id}")
async def deletar_peca(
    peca_id: int,
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO
):
    # Busca a peça no banco de dados
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    
    db.delete(peca)
    db.commit()    
    return RedirectResponse(url="/admin", status_code=303)

# ====== ROTA: ETIQUETA PARA IMPRESSÃO ======
@router.get("/etiqueta/{peca_id}", response_class=HTMLResponse)
async def gerar_etiqueta(
    peca_id: int, 
    request: Request, 
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO (Somente Admin imprime)
):
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    
    if not peca:
        return RedirectResponse(url="/admin?erro=Peça não encontrada", status_code=303)
        
    # Tenta achar a primeira foto cadastrada para ser a "Capa" da etiqueta
    foto_principal = next((m.url_path for m in peca.midias if m.tipo == 'foto'), None)
    
    return templates.TemplateResponse(
        request=request,
        name="admin/etiqueta.html", 
        context={
            "peca": peca, 
            "foto_principal": foto_principal
        }
    )