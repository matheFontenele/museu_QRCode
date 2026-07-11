import os
import shutil
import qrcode
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import models, database

router = APIRouter()
templates = Jinja2Templates(directory="/code/app/templates")

# ========== CAMINHOS FORÇADOS E ABSOLUTOS DO DOCKER ==========
STATIC_DIR = "/code/app/static"
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")
QRCODES_DIR = os.path.join(STATIC_DIR, "qrcodes")

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
    try:
        nova_peca = models.Peca(titulo=titulo, descricao=descricao)
        db.add(nova_peca)
        db.commit()
        db.refresh(nova_peca)
        
        # Gera e Salva o QR Code
        url_publica = f"http://localhost:8000/peca/{nova_peca.id}"
        qr = qrcode.make(url_publica)
        
        qr_filename = f"qr_peca_{nova_peca.id}.png"
        qr_path_full = os.path.join(QRCODES_DIR, qr_filename)
        
        # Salva usando string absoluta
        qr.save(str(qr_path_full))
        
        # Salva o caminho relativo no banco
        qr_path_db = f"/static/qrcodes/{qr_filename}"
        nova_peca.qr_code_path = qr_path_db
        db.commit()
        
        # Processamento de Mídias
        def processar_arquivos(arquivos, tipo):
            contador = 0
            for arquivo in arquivos:
                if arquivo.filename and contador < 6:
                    try:
                        nome_seguro = f"peca_{nova_peca.id}_{arquivo.filename.replace(' ', '_')}"
                        caminho_arquivo = os.path.join(UPLOADS_DIR, nome_seguro)
                        
                        with open(caminho_arquivo, "wb") as buffer:
                            shutil.copyfileobj(arquivo.file, buffer)
                            
                        nova_midia = models.Midia(
                            peca_id=nova_peca.id,
                            tipo=tipo,
                            url_path=f"/static/uploads/{nome_seguro}",
                            legenda=f"Mídia: {titulo}"
                        )
                        db.add(nova_midia)
                        contador += 1
                    except Exception as e:
                        print(f"Erro salvando mídia: {e}")
                        continue
                        
        if fotos:
            processar_arquivos(fotos, "foto")
        if videos:
            processar_arquivos(videos, "video")
            
        db.commit()
        return RedirectResponse(url="/admin", status_code=303)
        
    except Exception as e:
        db.rollback()
        raise