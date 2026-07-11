from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .. import models, database

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/peca/{peca_id}")
def ler_peca(request: Request, peca_id: int, db: Session = Depends(database.get_db)):
    # Busca a peça no banco de dados
    peca = db.query(models.Peca).filter(models.Peca.id == peca_id).first()
    
    if not peca:
        raise HTTPException(status_code=404, detail="Peça não encontrada no museu")
    
    # Renderiza o HTML passando os dados usando a sintaxe atualizada do FastAPI
    return templates.TemplateResponse(
        request=request,
        name="public/peca.html", 
        context={"peca": peca}
    )
