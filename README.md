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
python criar_admin.py seu-email@exemplo.br
```

A senha é pedida no terminal (mínimo de 8 caracteres). Rodar de novo com o mesmo e-mail troca a senha.

Dados fictícios para demonstração (dentro de `backend`; não precisa de `SECRET_KEY`):

```powershell
python seed.py            # cria os projetos e espécimes de exemplo
python seed.py --limpar   # remove só os de exemplo
```

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
