# LLM Gateway

A production-grade multi-LLM gateway and evaluation platform: request routing across
providers with retry/fallback, semantic caching, and evaluation/analytics on top of
generation traffic.

- Backend: FastAPI + SQLAlchemy + Pydantic v2 + Alembic
- Frontend: React + TypeScript + Tailwind CSS
- Data: PostgreSQL, Redis, Qdrant

## Getting started

```bash
cp env.example .env
cd backend
python -m venv .venv
.venv\Scripts\activate  # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
