import os
import shutil
import qrcode
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import models, database

router = APIRouter()

# Garantia absoluta do caminho dos templates no Docker
templates = Jinja2Templates(directory="/code/app/templates")

# ========== CAMINHOS FORÇADOS E ABSOLUTOS DO DOCKER ==========
STATIC_DIR = "/code/app/static"
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
QRCODES_DIR = os.path.join(STATIC_DIR, "qrcodes")

# ====== ROTAS ======
@router.get("/")
def painel_admin(request: Request, db: Session = Depends(database.get_db)):
    pecas = db.query(models.Peca).order_by(models.Peca.id.desc()).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html", 
        context={"pecas": pecas}
    )

@router.post("/cadastrar")
async def cadastrar_peca(
    titulo: str = Form(...),
    descricao: str = Form(...),
    fotos: list[UploadFile] = File(default=[]),
    videos: list[UploadFile] = File(default=[]),
    db: Session = Depends(database.get_db)
):  
    
    if len(fotos) > 6 or len(videos) > 6:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Limite excedido: Você só pode enviar no máximo 6 fotos e 6 vídeos."
    )
    
    try:
        nova_peca = models.Peca(titulo=titulo, descricao=descricao)
        db.add(nova_peca)
        db.commit()
        db.refresh(nova_peca)
        
        # Gera e salva o QRCode
        url_publica = f"http://localhost:8000/peca/{nova_peca.id}"        
        qr = qrcode.make(url_publica)
        
        # Define o nome e caminho do arquivo
        qr_filename = f"qr_peca_{nova_peca.id}.png"
        # CORREÇÃO 1: Usando os.path.join em vez da barra (/)
        qr_path_full = os.path.join(QRCODES_DIR, qr_filename)
        
        # Salva a imagem
        qr.save(qr_path_full)
        
        # Salva o caminho relativo no banco
        qr_path_db = f"/static/qrcodes/{qr_filename}"
        nova_peca.qr_code_path = qr_path_db
        db.commit()
        
        # Processamento das midias
        def processar_arquivos(arquivos, tipo):
            contador = 0
            for arquivo in arquivos:
                if arquivo.filename and contador < 6:  # Limita a 6 por tipo
                    try:
                        nome_seguro = f"peca_{nova_peca.id}_{arquivo.filename.replace(' ', '_')}"
                        # CORREÇÃO 2: Usando os.path.join
                        caminho_arquivo = os.path.join(UPLOADS_DIR, nome_seguro)

                        # Salva o arquivo no disco
                        with open(caminho_arquivo, "wb") as buffer:
                            shutil.copyfileobj(arquivo.file, buffer)
                        
                        # Registra no banco de dados
                        nova_midia = models.Midia(
                            peca_id=nova_peca.id,
                            tipo=tipo,
                            url_path=f"/static/uploads/{nome_seguro}",
                            legenda=f"Mídia do artefato: {titulo}"
                        )
                        db.add(nova_midia)
                        contador += 1
                    
                    except Exception as e:
                        # CORREÇÃO 3: Sintaxe da f-string corrigida
                        print(f"Erro ao salvar mídia: {e}")
                        continue
        
        # Processa fotos
        if fotos:
            processar_arquivos(fotos, "foto")
        
        # Processa vídeos
        if videos:
            processar_arquivos(videos, "video")
        
        # Commit final de todas as mídias
        db.commit()
        return RedirectResponse(url="/admin", status_code=303)
    
    except Exception as e:      
        # Desfaz qualquer operação no banco em caso de erro crítico
        db.rollback()
        
        # Relança a exceção para o FastAPI tratar e imprimir no terminal
        raise