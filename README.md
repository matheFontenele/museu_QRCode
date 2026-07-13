# Museu QR Code

Aplicacao web para gerenciamento de pecas do acervo do Museu da Biblia, com cadastro de itens, upload de fotos, links de videos do YouTube e geracao automatica de QR Codes para acesso publico.

O fluxo principal e simples: o curador cadastra uma peca no painel administrativo, o sistema gera um QR Code apontando para a pagina publica da peca, e o visitante escaneia o codigo para ver a descricao, fotos e videos relacionados.

## Funcionalidades

- Painel administrativo protegido por autenticacao HTTP Basic.
- Cadastro, edicao e exclusao de pecas do acervo.
- Geracao automatica de QR Code para cada peca cadastrada.
- Upload de fotos para a Cloudinary.
- Cadastro de links do YouTube para exibicao em carrossel.
- Limite de ate 6 fotos e 6 videos por peca.
- Pagina publica responsiva para visitantes.
- Armazenamento dos dados em banco PostgreSQL via `DATABASE_URL`.
- Armazenamento dos links das midias e dos QR Codes no banco.

## Tecnologias

- Python 3.11
- FastAPI
- Uvicorn
- Jinja2
- SQLAlchemy
- PostgreSQL / Supabase
- python-dotenv
- qrcode + Pillow
- Cloudinary
- Bootstrap 5
- Docker e Docker Compose

## Estrutura do projeto

```text
.
|-- app/
|   |-- database.py              # Configuracao da conexao com o banco
|   |-- main.py                  # Inicializacao do FastAPI e registro das rotas
|   |-- models.py                # Modelos SQLAlchemy: Peca e Midia
|   |-- routes/
|   |   |-- admin.py             # Rotas protegidas do painel administrativo
|   |   `-- public.py            # Rota publica de visualizacao da peca
|   |-- static/
|   |   |-- qrcodes/             # Pasta mantida para arquivos estaticos locais
|   |   `-- uploads/             # Pasta mantida para arquivos estaticos locais
|   `-- templates/
|       |-- admin/index.html     # Interface do painel administrativo
|       `-- public/peca.html     # Pagina publica da peca
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
`-- .env.example
```

## Variaveis de ambiente

O projeto usa variaveis de ambiente para guardar credenciais e configuracoes sensiveis.

Crie um arquivo `.env` na raiz do projeto:

```bash
cp .env.example .env
```

Depois preencha os valores reais:

```env
DATABASE_URL=postgresql://usuario:senha@host:5432/nome_do_banco
CLOUDINARY_CLOUD_NAME=seu_cloud_name
CLOUDINARY_API_KEY=sua_api_key
CLOUDINARY_API_SECRET=sua_api_secret
```

Para Supabase, use a URL de conexao PostgreSQL fornecida pelo painel do projeto.

O arquivo `.env.example` deve ser commitado como modelo, sem segredos reais. O arquivo `.env` local e variacoes como `.env.local` devem permanecer fora do Git.

## Como executar com Docker

Esta e a forma recomendada, pois o codigo esta configurado para usar os caminhos internos do container em `/code/app`.

```bash
docker compose up --build
```

Depois acesse:

```text
http://localhost:8000/admin
```

Ao iniciar, a aplicacao cria automaticamente as tabelas no banco configurado em `DATABASE_URL`.

## Credenciais do painel

As credenciais atuais do painel administrativo estao definidas em `app/routes/admin.py`:

```text
Usuario: admin
Senha: museu123
```

Antes de publicar o projeto, altere essas credenciais ou mova esses valores para variaveis de ambiente.

## Rotas principais

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/` | Redireciona para `/admin` |
| `GET` | `/admin` | Lista as pecas cadastradas no painel |
| `POST` | `/admin/cadastrar` | Cadastra uma nova peca e gera o QR Code |
| `POST` | `/admin/editar/{peca_id}` | Atualiza dados e midias de uma peca |
| `POST` | `/admin/deletar/{peca_id}` | Remove uma peca do acervo |
| `GET` | `/peca/{peca_id}` | Exibe a pagina publica da peca |

## Modelo de dados

### Peca

Representa um item do acervo.

- `id`
- `titulo`
- `descricao`
- `qr_code_path`
- `midias`

### Midia

Representa uma foto enviada ou um link de video vinculado a uma peca.

- `id`
- `peca_id`
- `tipo`: `foto` ou `video`
- `url_path`
- `legenda`

## Midias e arquivos gerados

As fotos enviadas pelo painel e os QR Codes gerados pela aplicacao sao enviados para a Cloudinary:

```text
museu/fotos
museu/qrcodes
```

O banco salva as URLs seguras retornadas pela Cloudinary. As pastas locais abaixo continuam no projeto como estrutura de arquivos estaticos, mas o conteudo gerado nao deve ser versionado:

```text
app/static/uploads/
app/static/qrcodes/
```

## Observacoes importantes

- O painel aceita imagens pelo formulario e links do YouTube para videos.
- O frontend valida alguns limites, mas o backend tambem bloqueia mais de 6 fotos ou 6 videos por peca.
- A pagina publica monta os videos do YouTube em `iframe` a partir do link salvo.
- Ao excluir uma midia no painel, a referencia e removida do banco. A limpeza do arquivo na Cloudinary deve ser feita separadamente, caso necessario.
- O projeto atualmente esta otimizado para execucao via Docker por causa dos caminhos absolutos usados em `app/main.py` e `app/routes/admin.py`.
