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

# ====== ROTA: CADASTRAR PEÇA ======
@router.post("/cadastrar")
async def cadastrar_peca(
    titulo: str = Form(...),
    descricao: str = Form(...),
    fotos: list[UploadFile] = File(default=[]),
    youtube_links: list[str] = Form(default=[]),
    db: Session = Depends(database.get_db)
):  
    # Filtra para não contar campos vazios
    fotos_validas = [f for f in fotos if f.filename]
    links_validos = [link.strip() for link in youtube_links if link.strip()]
    
    # Travas de segurança para limite de 
    if len(fotos_validas) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limite excedido: Máximo de 6 fotos.")
    
    if len(links_validos) > 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limite excedido: Máximo de 6 vídeos.")
    
    try:
        nova_peca = models.Peca(titulo=titulo, descricao=descricao)
        db.add(nova_peca)
        db.commit()
        db.refresh(nova_peca)
        url_publica = f"http://localhost:8000/peca/{nova_peca.id}"        
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
    
# ====== ROTA DE ATUALIZAR (UPDATE) ======
@router.post("/editar/{peca_id}")
async def editar_peca(
    peca_id: int,
    titulo: str = Form(...),
    descricao: str = Form(...),
    db: Session = Depends(database.get_db)
):
    # Busca a peça no banco de dados
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    
    # Atualiza os dados
    peca.titulo = titulo
    peca.descricao = descricao
    
    db.commit()
    # Redireciona de volta para o painel
    return RedirectResponse(url="/admin", status_code=303)


# ====== ROTA DE DELETAR (DELETE) ======
@router.post("/deletar/{peca_id}")
async def deletar_peca(
    peca_id: int,
    db: Session = Depends(database.get_db)
):
    # Busca a peça no banco de dados
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada.")
    
    db.delete(peca)
    db.commit()    
    # Redireciona de volta para o painel
    return RedirectResponse(url="/admin", status_code=303)