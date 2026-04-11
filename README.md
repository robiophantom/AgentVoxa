# AgentVoxa 🤖📞

**AI Receptionist Platform** – answers queries via chat and phone calls, powered by Gemini AI, Vonage, Qdrant, and FastAPI.

---

## Architecture

```
AgentVoxa/
├── docker-compose.yml          # PostgreSQL + Qdrant
├── .env.example                # Root env vars template
├── backend/                    # FastAPI (Python)
│   ├── main.py
│   ├── requirements.txt
│   ├── core/                   # Config, DB, Qdrant, Security
│   ├── models/                 # SQLAlchemy models
│   ├── routers/                # API routes
│   └── services/               # Business logic
└── frontend/                   # Next.js (TypeScript)
    ├── app/                    # App Router pages
    ├── components/             # React components
    └── lib/                    # Auth, utils
```

## Quick Start

### 1. Start databases
```bash
cp .env.example .env
docker compose up -d
```

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # Edit with real keys
uvicorn main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
cp .env.example .env.local     # Edit with real keys
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Features

| Feature | Description |
|---|---|
| 🤖 AI Chat | WebSocket + REST chat with Gemini RAG |
| 📞 Voice Calls | Vonage WebSocket bridge + Pipecat STT/TTS |
| 📄 Knowledge Base | Upload PDF/DOCX/MD, chunk & embed with MiniLM |
| 🔍 Hybrid Search | Qdrant vector + FTS retrieval |
| 👥 Roles | Admin, Student (authenticated), Public User |
| 🔑 Auth | NextAuth.js Credentials provider (Google OAuth deferred) |
| 📊 Admin Dashboard | Document management, chat/call logs, admission insights |
| 🔀 Human Handoff | Auto-transfer call or suggest staff number on chat |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/token` | Login (get JWT) |
| POST | `/api/auth/register` | Register user |
| GET | `/api/auth/me` | Current user |
| POST | `/api/documents/upload` | Upload document (Admin) |
| GET | `/api/documents/` | List documents (Admin) |
| DELETE | `/api/documents/{id}` | Delete document (Admin) |
| POST | `/api/chat/` | Send chat message |
| WS | `/api/chat/ws` | WebSocket chat |
| POST | `/api/calls/answer` | Vonage answer webhook |
| POST | `/api/calls/event` | Vonage event webhook |
| WS | `/api/calls/ws/{uuid}` | Call audio stream |
| GET | `/api/admin/chat-logs` | Chat logs (Admin) |
| GET | `/api/admin/call-logs` | Call logs (Admin) |
| GET | `/api/admin/interested-users` | Admission leads (Admin) |
| GET | `/api/admin/stats` | Dashboard stats (Admin) |

## Environment Variables

Copy `.env.example` to `.env` and fill in:
- `GEMINI_API_KEY` – Google Gemini API key
- `VONAGE_API_KEY` / `VONAGE_API_SECRET` – Vonage credentials
- `DATABASE_URL` – PostgreSQL connection string
- `QDRANT_HOST` / `QDRANT_PORT` – Qdrant connection
- `SECRET_KEY` – JWT signing secret

## Tech Stack

**Backend**: FastAPI · SQLAlchemy · Qdrant · SentenceTransformers (MiniLM) · Gemini · Vonage · Pipecat

**Frontend**: Next.js 14 · TypeScript · Tailwind CSS · Framer Motion · shadcn/ui · NextAuth.js
