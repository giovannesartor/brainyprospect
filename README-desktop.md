# ⚡ LeadHunter AI

> Aplicativo desktop **macOS** em Python para **prospecção B2B inteligente** com IA. Análise automática de site → identificação de ICP → busca multi-fonte de leads → enriquecimento de contatos → qualificação por IA → exportação comercial.

Inspirado visualmente em **Linear / Raycast / Arc**.

---

## ✨ Recursos

- **Análise de site via IA** (DeepSeek / OpenAI) — gera resumo, ICP, nichos e palavras-chave
- **Busca de leads** no **Google Maps** (Playwright) e **Bing** (HTML)
- **Enriquecimento automático** entrando no site da empresa (emails, telefones, WhatsApp, Instagram, LinkedIn)
- **IA-SDR**: pontua cada lead 0-100, justifica e gera abordagem comercial pronta
- **Filtros avançados** (cidade, UF, nicho, score, com email, com WhatsApp, sem site)
- **Exportação** CSV / XLSX / JSON com layout profissional
- **Dashboard** com totais, score médio, top nichos e últimas pesquisas
- **Histórico** de buscas, **Logs** e **Configurações** com API keys protegidas
- **Multi-thread** (QThread) — UI nunca trava
- **Anti-bloqueio**: delays randômicos, user-agents rotativos, retries, proxy opcional
- Pronto para **PostgreSQL** futuramente, **API REST**, **multiusuário**, **CRM** e **automação WhatsApp/Email**

---

## 🧱 Arquitetura

```
app/
 ├─ ui/             # PySide6 (theme, main_window, pages, widgets, workers)
 ├─ services/       # Orquestração: lead_hunter, contact_enricher, exporter
 │   └─ ai/         # Provider modular DeepSeek/OpenAI
 ├─ scrapers/       # site_scraper, google_maps_scraper, bing_scraper
 ├─ database/       # SQLAlchemy + repository pattern
 ├─ models/         # Pydantic (ICPProfile, LeadDraft, ...)
 ├─ config/         # Pydantic settings (singleton)
 ├─ utils/          # http, contacts, logger
 ├─ assets/
 ├─ bootstrap.py    # init_db + Qt
 └─ paths.py        # caminhos (dev e PyInstaller)
config/             # settings.default.json (sementes)
scripts/            # setup.sh, build_macos.sh
LeadHunterAI.spec   # PyInstaller (.app)
main.py             # entrypoint
```

Padrões: **Repository**, **Service Layer**, **Provider modular para IA**, **Pydantic** para tipagem, **Loguru** para logging, **PEP8 + type hints**.

---

## 🚀 Instalação (macOS)

> Pré-requisitos: **Python 3.12+** (recomendado via [pyenv](https://github.com/pyenv/pyenv) ou `brew install python@3.12`).

```bash
cd "Brainy Prospect"
bash scripts/setup.sh
```

O script cria um `.venv`, instala as dependências e baixa o **Chromium do Playwright**.

### Rodar em modo dev

```bash
source .venv/bin/activate
python main.py
```

---

## 🔐 Configuração de API keys

O arquivo `config/settings.default.json` é semente. Em runtime as configurações ficam em:

```
~/Library/Application Support/LeadHunterAI/config/settings.json
```

Você pode editar pela tela **Configurações** dentro do app (recomendado) ou direto no arquivo.

> ⚠️ **A chave DeepSeek que veio na primeira execução está exposta no código-fonte.** Rotacione no painel da DeepSeek e configure a nova via tela **Configurações**.

---

## 🧪 Como usar

1. Abra o app → vá em **Buscar Leads**.
2. Cole um site (ex.: `https://quantovale.online`) **ou** descreva seu negócio **ou** preencha nichos manuais.
3. Informe cidade/UF, ajuste “Resultados por nicho”.
4. Clique **Iniciar prospecção**. Acompanhe o progresso em tempo real.
5. Vá em **Leads** para filtrar, ver detalhes e exportar.

---

## 📦 Build do `.app` macOS

```bash
bash scripts/build_macos.sh
open dist/LeadHunterAI.app
```

Para **assinar e notarizar**, use `codesign` + `xcrun notarytool` (não incluído por exigir Apple Developer ID).

---

## 🔧 Configurações principais

| Chave | Descrição |
|---|---|
| `ai.default_provider` | `deepseek` ou `openai` |
| `ai.deepseek.api_key` | API Key DeepSeek |
| `ai.openai.api_key` | API Key OpenAI |
| `scraping.timeout_seconds` | Timeout HTTP (s) |
| `scraping.min/max_delay_ms` | Delay randômico anti-bloqueio |
| `scraping.max_retries` | Retentativas |
| `scraping.user_agent_rotation` | Rotação de User-Agent |
| `scraping.proxy` | `http://user:pass@host:port` |
| `scraping.headless` | Chromium headless on/off |

---

## 🧯 Troubleshooting

- **`playwright._impl._api_types.Error: Executable doesn't exist`** → rode `python -m playwright install chromium`.
- **`AIClientError: API key não configurada`** → vá em **Configurações** e cole sua chave.
- **Google Maps sem resultados** → desative `headless` em Configurações para depurar visualmente; verifique seu IP / proxy.
- **App `.app` não abre (Gatekeeper)** → `xattr -cr dist/LeadHunterAI.app` ou assine com Developer ID.

---

## 🛣 Roadmap (preparado, não implementado)

- 🔌 API REST (FastAPI)
- 🗄 PostgreSQL (basta trocar string em `app/database/db.py`)
- 👥 Login multiusuário
- ☁️ Cloud sync
- 💬 Automação WhatsApp / Email
- 📇 CRM kanban interno

---

## 📜 Licença

Uso interno / comercial do solicitante. Todos os direitos reservados.
