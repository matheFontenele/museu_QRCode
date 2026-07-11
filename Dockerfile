# Usa uma imagem oficial do Python, leve e otimizada
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /code

# Copia o arquivo de dependências e instala
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copia o restante do código para dentro do contêiner
COPY ./app /code/app

# Comando padrão para rodar a aplicação
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
