<div align="center">

# Vanta

**Self-Hosted, Privacy-First Research-as-a-Service**

*A 15-stage multi-agent deep research engine that runs entirely inside your perimeter.*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-6366f1?style=flat-square)](LICENSE)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

---

### 🌐 [Try the Hosted Web App](https://vanta-hazel.vercel.app/console) &nbsp;•&nbsp; 📖 [Full Documentation](docs/)

</div>

---

## ⚡ Quickstart: Local Installation

Run one command in your terminal to install and launch the **private Research Console** directly on your machine (no landing page, no marketing text):

### macOS / Linux:
```bash
curl -sSL https://raw.githubusercontent.com/avirooppal/Vanta-Deep-Research-API/main/install.sh | bash
```

### Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/avirooppal/Vanta-Deep-Research-API/main/install.ps1 | iex
```

> **What happens**: Vanta installs to `~/.vanta`, starts your local engine, and automatically opens your browser to **`http://localhost:8000`** with the dedicated Research Console ready to work.

---

## 🌟 Key Highlights

- **15-Stage Research Engine**: Executes an autonomous multi-round loop (Hypothesize → Multi-Engine Search → Extract → Validate → Contradiction Detection → Falsification → Synthesize → Citation Entailment).
- **Bring Your Own Key (BYOK)**: Supports OpenAI, Anthropic, Google Gemini, OpenRouter, Groq, Cerebras, and local Ollama.
- **Zero-Trust Privacy**: Ephemeral in-memory key isolation, AES-128 Fernet encryption at rest, and prompt injection sentinels.
- **Atomic Evidence Graph**: Facts extracted into typed claims and embedded into PostgreSQL with `pgvector`.
- **Adaptive Research Scopes**: Switch between **Study** (Feynman breakdown & quiz), **Brief** (BLUF action items), **Research** (balanced), and **Deep** (exhaustive literature review).

---

## ☁️ Cloud Deployment

Deploy Vanta's backend to your own cloud infrastructure in 1 click:

- **[Deploy on Render](docs/deployment.md#2-render-blueprint-1-click)** (Free tier available)
- **[Deploy on Railway](docs/deployment.md#1-railway-1-click)**
- **[Deploy on Fly.io](docs/deployment.md#3-flyio)**
- **[Self-Hosted Cloud VPS (Caddy SSL)](docs/deployment.md#4-self-hosted-cloud-vps-caddy-automatic-ssl)**

---

## 📚 Documentation

Detailed technical documentation and guides:

| Document | Description |
|---|---|
| 📐 **[Architecture & Pipeline](docs/architecture.md)** | Deep dive into the 15-stage multi-agent pipeline and engine loop |
| 🔌 **[API Reference](docs/api.md)** | Complete REST & SSE endpoints, request schemas, and export formats |
| 🗄️ **[Database & Models](docs/database.md)** | PostgreSQL + `pgvector` ER diagrams and schema specifications |
| 🛡️ **[Security Architecture](docs/security.md)** | Zero-trust credential broker, encryption at rest, and audit logging |
| 🚀 **[Cloud Deployment Guide](docs/deployment.md)** | Step-by-step guides for Render, Railway, Fly.io, and VPS |

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
