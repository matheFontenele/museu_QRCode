from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# O banco de dados será criado na raiz do diretório mapeado pelo Docker
SQLALCHEMY_DATABASE_URL = "sqlite:///./museu.db"

# connect_args={"check_same_thread": False} é necessário apenas no SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependência para injetar a sessão do banco nas rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
