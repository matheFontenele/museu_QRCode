import os
import shutil
import qrcode
import secrets
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import models, database
from urllib.parse import quote

router = APIRouter()

# Instancia o esquema de segurança básico
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

# ========== CAMINHOS FORÇADOS E ABSOLUTOS DO DOCKER ==========
STATIC_DIR = "/code/app/static"
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
QRCODES_DIR = os.path.join(STATIC_DIR, "qrcodes")

# ====== ROTAS ======

@router.get("/")
def painel_admin(
    request: Request, 
    db: Session = Depends(database.get_db),
    usuario: str = Depends(verificar_credenciais) # <-- CADEADO ATIVADO
):
    pecas = db.query(models.Peca).order_by(models.Peca.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html", 
        context={"pecas": pecas}
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
        base_url = str(request.base_url).rstrip("/")
        url_publica = f"{base_url}/peca/{nova_peca.id}"        
        qr = qrcode.make(url_publica)
        qr_filename = f"qr_peca_{nova_peca.id}.png"
        qr_path_full = os.path.join(QRCODES_DIR, qr_filename)
        qr.save(qr_path_full)
        qr_path_db = f"/static/qrcodes/{qr_filename}"
        nova_peca.qr_code_path = qr_path_db
        db.commit()
        
        # Processamento das Fotos Unitárias
        for arquivo in fotos_validas:
            try:
                nome_seguro = f"peca_{nova_peca.id}_{arquivo.filename.replace(' ', '_')}"
                caminho_arquivo = os.path.join(UPLOADS_DIR, nome_seguro)
                
                with open(caminho_arquivo, "wb") as buffer:
                    shutil.copyfileobj(arquivo.file, buffer)
                
                nova_midia = models.Midia(
                    peca_id=nova_peca.id,
                    tipo="foto",
                    url_path=f"/static/uploads/{nome_seguro}",
                    legenda=f"Foto do artefato: {titulo}"
                )
                db.add(nova_midia)
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")
                continue
                
        # Processamento dos Links do YouTube
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

        # 2. Calcula como vai ficar o total (Atuais que não serão excluídas + Novas)
        fotos_atuais = len([m for m in peca.midias if m.tipo == 'foto' and m.id not in midias_para_excluir])
        videos_atuais = len([m for m in peca.midias if m.tipo == 'video' and m.id not in midias_para_excluir])
        
        # 3. Trava de segurança elegante (Redireciona com mensagem de erro)
        if (fotos_atuais + len(fotos_validas)) > 6 or (videos_atuais + len(links_validos)) > 6:
            msg = quote("A peça não pode ter mais de 6 fotos ou 6 vídeos no total. Nenhuma alteração foi salva.")
            return RedirectResponse(url=f"/admin?erro={msg}", status_code=303)

        # 4. Atualiza os textos
        peca.titulo = titulo
        peca.descricao = descricao
        
        # 5. Processa a exclusão das mídias antigas (Só chega aqui se passou no limite)
        for midia_id in midias_para_excluir:
            midia_obj = db.query(models.Midia).filter(models.Midia.id == midia_id, models.Midia.peca_id == peca_id).first()
            if midia_obj:
                if midia_obj.tipo == "foto":
                    filename = midia_obj.url_path.split('/')[-1]
                    caminho_fisico = os.path.join(UPLOADS_DIR, filename)
                    if os.path.exists(caminho_fisico):
                        os.remove(caminho_fisico)
                
                # Deleta do banco
                db.delete(midia_obj)
        
        # Salva as exclusões
        db.commit()
        db.refresh(peca)

        # 6. Adiciona as Novas Fotos
        for arquivo in fotos_validas:
            nome_seguro = f"peca_{peca.id}_{arquivo.filename.replace(' ', '_')}"
            caminho_arquivo = os.path.join(UPLOADS_DIR, nome_seguro)
            
            with open(caminho_arquivo, "wb") as buffer:
                shutil.copyfileobj(arquivo.file, buffer)
            
            nova_midia = models.Midia(
                peca_id=peca.id, tipo="foto",
                url_path=f"/static/uploads/{nome_seguro}",
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