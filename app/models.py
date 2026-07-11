from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Peca(Base):
    __tablename__ = "pecas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(150), index=True)
    descricao = Column(Text) # Até 1000 caracteres
    qr_code_path = Column(String(255), nullable=True)
    
    # Relação: Uma peça tem várias mídias. Se a peça for apagada, as mídias também são.
    midias = relationship("Midia", back_populates="peca", cascade="all, delete-orphan")

class Midia(Base):
    __tablename__ = "midias"

    id = Column(Integer, primary_key=True, index=True)
    peca_id = Column(Integer, ForeignKey("pecas.id"))
    tipo = Column(String(10)) # Vai guardar 'foto' ou 'video'
    url_path = Column(String(255)) # O caminho do arquivo salvo
    legenda = Column(String(120)) # Texto em baixo com até 120 caracteres
    
    # Relação de volta para a peça
    peca = relationship("Peca", back_populates="midias")