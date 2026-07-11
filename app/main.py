import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import models, database
from app.routes import admin, public

app = FastAPI(title="Museu da Bíblia")

models.Base.metadata.create_all(bind=database.engine)

# ========== CAMINHOS FORÇADOS E ABSOLUTOS DO DOCKER ==========
BASE_DIR = "/code/app"
STATIC_DIR = "/code/app/static"

# Garante a criação das pastas usando os.makedirs (que aceita strings)
os.makedirs(os.path.join(STATIC_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "qrcodes"), exist_ok=True)

# Logging de segurança
print("="*60)
print(f"✅ FORÇANDO DIRETÓRIOS DOCKER")
print(f"STATIC_DIR: {STATIC_DIR}")
print("="*60)

# Monta a pasta de arquivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ====== CONFIGURAÇÃO DE TEMPLATES ======
# Usa os.path.join em vez da barra (/) para juntar o caminho
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ====== REGISTRA AS ROTAS ======
app.include_router(admin.router, prefix="/admin")
app.include_router(public.router)

# ====== ROTA HOME ======
@app.get("/")
def home():
    """Redireciona a tela inicial para o painel do curador (admin)"""
    return RedirectResponse(url="/admin")

# ====== STARTUP EVENT ======
@app.on_event("startup")
async def startup_event():
    """Executado quando o servidor inicia"""
    print("✅ Servidor iniciado com sucesso!")
    print("📍 Acesse: http://localhost:8000/admin")

@app.on_event("shutdown")
async def shutdown_event():
    """Executado quando o servidor desliga"""
    print("❌ Servidor desligado")