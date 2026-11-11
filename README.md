# EntomoBase

Catálogo web de coleções entomológicas. API em FastAPI (SQLAlchemy) e frontend em Vue 3 sem etapa de build.

## Rodar localmente

A partir da raiz do projeto, no PowerShell:

```powershell
# uma vez: criar o ambiente e instalar as dependências
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

# API (http://127.0.0.1:8000)
cd backend
$env:ENTOMOBASE_ENV = "dev"
uvicorn main:app --reload
```

Em outro terminal, sirva o frontend (ele espera a API em `http://127.0.0.1:8000`):

```powershell
cd frontend
python -m http.server 5500
```

e abra `http://127.0.0.1:5500`.

O endereço da API que o site usa fica em `frontend/config.js` (`apiUrl`). Ao publicar o frontend, troque esse valor pelo endereço público da API e defina `CORS_ORIGINS` na API com o endereço do site.

Criar o primeiro usuário do laboratório (não existe usuário padrão). Dentro de `backend`:

```powershell
python create_admin.py seu-email@exemplo.br
```

A senha é pedida no terminal (mínimo de 8 caracteres). Rodar de novo com o mesmo e-mail troca a senha.

Dados fictícios para demonstração (dentro de `backend`; não precisa de `SECRET_KEY`):

```powershell
python seed.py            # cria os projetos e espécimes de exemplo
python seed.py --remove   # remove só os de exemplo
```

## Esquemas

Os diagramas do banco de dados e do site estão em `docs/esquema_banco.png` e `docs/esquema_site.png` (também em `.svg`).

## Banco de dados e migrações

A estrutura do banco é controlada pelo Alembic (pasta `backend/migrations`). Em uso normal não há nada a fazer: **a API aplica as migrações pendentes ao iniciar**, e o `seed.py` e o `create_admin.py` também.

Comandos, dentro de `backend` com o ambiente virtual ativo:

```powershell
alembic current                                # em que versão o banco está
alembic upgrade head                           # aplica as migrações pendentes (a API já faz isso)
alembic check                                  # confere se models.py e as migrações estão de acordo
alembic downgrade -1                           # desfaz a última migração
alembic revision --autogenerate -m "o que mudou"   # cria uma migração depois de mudar models.py
```

Para mudar uma tabela: edite `models.py`, rode `alembic revision --autogenerate -m "..."`, **leia o arquivo criado em `migrations/versions`** (o Alembic erra em casos como renomear colunas), rode `alembic upgrade head` e depois `pytest`. O teste `test_models_and_migrations_are_in_sync` falha se você esquecer de criar a migração.

Um banco que tem tabelas mas não tem o histórico das migrações (criado antes do Alembic) é **recusado**, com uma mensagem explicando, para a API não adivinhar o estado dele e danificá-lo. Como os dados atuais são de demonstração, basta apagar o arquivo e recriar:

```powershell
cd backend
del entomobase.db
python seed.py                          # dados de demonstração
python create_admin.py seu-email@exemplo.br   # primeiro usuário
```

Cuidados:
- Voltar além da primeira migração (`alembic downgrade base`) apaga todas as tabelas e os dados.
- Rode uma única cópia da API ao atualizar o banco; duas cópias subindo juntas tentariam migrar ao mesmo tempo.

## Testes

```powershell
pip install -r backend\requirements-dev.txt
cd backend
pytest               # roda os testes
pytest --cov         # roda os testes e mostra a cobertura de código (mínimo exigido: 80%)
```

Os testes usam um banco temporário próprio e nunca tocam em `entomobase.db`. Não acessam a internet: o GBIF é simulado. Cobrem login e limite de tentativas, o que visitantes veem, projetos, espécimes, importação, exportação (CSV nos dois idiomas e Darwin Core), cache do GBIF, migração do banco antigo, CORS e a conferência de que todo texto do site tem tradução.

## Variáveis de ambiente

| Variável | Para que serve |
|---|---|
| `SECRET_KEY` | Chave que assina os tokens de login. **Obrigatória** fora do desenvolvimento. |
| `ENTOMOBASE_ENV` | Com o valor `dev`, a API sobe sem `SECRET_KEY` usando uma chave temporária (os logins caem a cada reinício). Use só em desenvolvimento. |
| `CORS_ORIGINS` | Endereços dos sites que podem usar a API pelo navegador, separados por vírgula (ex.: `https://acervo.meulab.br`). Em modo `dev`, sem a variável, valem `http://127.0.0.1:5500` e `http://localhost:5500`. Fora do `dev`, sem ela, nenhum outro site consegue usar a API. |
| `DATABASE_URL` | Banco de dados. Sem ela, usa SQLite local (`entomobase.db`). |

Para gerar uma `SECRET_KEY` de produção:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Nunca coloque a chave no código nem em um commit.
