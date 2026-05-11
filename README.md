# ⚡ Brainy Prospect — Web

> Plataforma B2B de prospecção com IA. Versão **web** (FastAPI + Jinja/Alpine), pronta para deploy em **Railway** com PostgreSQL.

---

## ✨ O que faz

- **Análise de site via IA** (DeepSeek/OpenAI) — gera ICP, nichos, palavras-chave
- **Busca multi-fonte** de leads B2B (Bing + DuckDuckGo + Google Maps)
- **Enriquecimento** automático: emails, telefones, WhatsApp, Instagram, LinkedIn, CNPJ, tech stack, decisores
- **IA-SDR**: pontua cada lead 0-100, gera pitch e mensagens prontas (A/B + abertura personalizada)
- **CRM/Pipeline** Kanban, campanhas, follow-ups, watch-list de mudanças
- **Painel Admin completo** (usuários, aprovações, configurações globais, jobs)
- **Multi-usuário** com aprovação manual via admin
- **Exporta** CSV / XLSX / JSON

---

## 🏗 Arquitetura

```
app/
 ├─ web/             ← Camada FastAPI (NOVA)
 │   ├─ main.py        FastAPI app + páginas server-rendered
 │   ├─ security.py    bcrypt + JWT
 │   ├─ users.py       UserRepository
 │   ├─ deps.py        require_user / require_admin
 │   ├─ jobs.py        JobManager in-memory para hunts longos
 │   ├─ routes/        auth, leads, admin
 │   ├─ templates/     login, register, app, admin (Jinja2 + Tailwind + Alpine)
 │   └─ static/        app.js, admin.js
 ├─ database/        SQLAlchemy (User adicionado), suporta SQLite e PostgreSQL
 ├─ services/        lead_hunter, contact_enricher, exporter, messaging, …
 ├─ scrapers/        bing, duckduckgo, google_maps, site
 ├─ models/          Pydantic (ICPProfile, LeadDraft, …)
 ├─ config/          Pydantic settings + JSON persistente
 └─ ui/              UI desktop original (PySide6) — mantida intacta
web_main.py           ← Entrypoint web (Railway)
main.py               ← Entrypoint desktop (PySide6)
```

---

## 🚀 Deploy no Railway

### 1) Crie o projeto

1. Faça o push deste repositório para o GitHub.
2. Em **railway.app**, clique em **New Project → Deploy from GitHub repo** e selecione `brainyprospect`.
3. Adicione um plugin **PostgreSQL** (Railway → New → Database → PostgreSQL).
4. Em **Variables**, defina:

| Variável | Valor | Obrigatório |
|----------|-------|-------------|
| `SECRET_KEY` | string aleatória ≥32 chars (use `python -c "import secrets;print(secrets.token_urlsafe(64))"`) | **sim** |
| `ADMIN_EMAIL` | `giovannesartor@gmail.com` | sim |
| `ADMIN_PASSWORD` | `Giotop12@` | sim |
| `ADMIN_NAME` | `Giovanne Sartor` | não |
| `BRAINY_DATA_DIR` | `/data` (se montar volume) ou vazio | não |
| `CORS_ORIGINS` | `*` em dev, domínios específicos em prod | não |

> O `DATABASE_URL` é injetado automaticamente pelo plugin Postgres do Railway.

### 2) Volume persistente (opcional mas recomendado)

Em **Settings → Volumes**, monte um volume em `/data` e defina `BRAINY_DATA_DIR=/data`. Isso persistirá:
- exports gerados
- logs
- (em dev sem Postgres) o sqlite

### 3) Healthcheck

A rota `/health` já está configurada (`railway.json`).

### 4) Primeiro acesso

Após o deploy, abra a URL do Railway:
- `/login` → entre com `giovannesartor@gmail.com` / `Giotop12@`
- `/admin` → painel administrativo (aprovação de usuários, configs, etc.)
- Configure as **API keys** de DeepSeek/OpenAI em **Admin → Configurações**.

---

## 🧪 Rodar localmente (web)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(64))')"

uvicorn web_main:app --reload --port 8000
```

Acesse <http://localhost:8000>. Login: `giovannesartor@gmail.com` / `Giotop12@`.

---

## 👥 Fluxo de usuário

1. **Visitante** → `/register` → cria conta com status `pending`.
2. **Admin** → `/admin` → vê pendentes → **Aprovar**.
3. **Usuário aprovado** → `/login` → entra em `/app`.

> Não há confirmação de email. A barreira é a aprovação do admin.

---

## 🛡 Painel Admin

Acesse `/admin` com a conta admin. Funcionalidades:

| Aba | O que faz |
|-----|-----------|
| **Visão geral** | KPIs (usuários, leads, jobs), saúde de Bing/DDG/Google Maps/IA, info do banco |
| **Usuários** | Aprovar / bloquear / excluir / promover-rebaixar admin / resetar senha |
| **Configurações** | API keys (DeepSeek/OpenAI), parâmetros de scraping, templates de mensagens |
| **Jobs** | Lista todos os jobs em execução de todos os usuários, limpar antigos |

---

## 📡 API REST

Documentação interativa em `/api/docs` (Swagger UI).

Principais endpoints:

```
POST  /api/auth/register              criar conta (status=pending)
POST  /api/auth/login                 retorna JWT + cookie httponly
POST  /api/auth/logout
GET   /api/auth/me

GET   /api/dashboard                  KPIs + pipeline + buscas recentes
GET   /api/leads                      filtros: text/city/state/niche/min_score/...
GET   /api/leads/{id}
PATCH /api/leads/{id}                 status, priority, observations, ...
DELETE /api/leads/{id}
GET   /api/leads/export/{csv|xlsx|json}

POST  /api/analyze                    analisa site/descrição (ICP)
POST  /api/hunt                       inicia prospecção (retorna job_id)
GET   /api/jobs/{job_id}              progress polling
GET   /api/jobs

GET   /api/campaigns
POST  /api/campaigns
DELETE /api/campaigns/{id}

GET   /api/searches

# Admin (requer role=admin)
GET   /api/admin/overview
GET   /api/admin/users[?status=pending]
POST  /api/admin/users/{id}/approve
POST  /api/admin/users/{id}/block
DELETE /api/admin/users/{id}
PATCH /api/admin/users/{id}            { role, status, full_name, ... }
POST  /api/admin/users/{id}/reset-password
GET   /api/admin/settings
PATCH /api/admin/settings
GET   /api/admin/jobs
POST  /api/admin/jobs/cleanup
```

Autenticação: cookie `bp_token` (httponly) ou header `Authorization: Bearer <jwt>`.

---

## 🖥 Versão desktop (legada)

A UI original PySide6 continua em `app/ui/` — rode com `python main.py`. Use `requirements-desktop.txt`.

Documentação desktop original: [`README-desktop.md`](README-desktop.md).

---

## 🧰 Stack

- **Backend**: FastAPI 0.115, SQLAlchemy 2, Pydantic 2, PyJWT, bcrypt
- **Frontend**: Jinja2 SSR + Tailwind (CDN) + Alpine.js (CDN) — zero build step
- **DB**: SQLite (dev) / PostgreSQL (Railway)
- **IA**: DeepSeek ou OpenAI (compatible API)
- **Scraping**: Requests + BeautifulSoup + lxml + Playwright (opcional, p/ Google Maps)

---

## 🔒 Segurança

- Senhas com **bcrypt** (12 rounds).
- JWT assinado com `SECRET_KEY` (defina sempre em produção; ≥32 chars).
- Cookies `httponly` + `samesite=lax`. Habilite `secure=True` ao usar HTTPS (auto com Railway).
- Aprovação manual de novas contas.
- Admin não pode rebaixar/desativar a si mesmo via API.

---

## 📝 Licença

Privado / proprietário. © 2026 Giovanne Sartor.
