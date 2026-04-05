# AI Agent Webapp

A full-stack web application for AI agent development and deployment.

## 📁 Project Structure

```
ai-agent-webapp/
├── frontend/                 # Next.js React frontend application
│   ├── src/
│   │   ├── app/             # Next.js app directory
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom React hooks
│   │   ├── lib/             # Utility functions and helpers
│   │   ├── types/           # TypeScript type definitions
│   │   └── styles/          # Global and component styles
│   └── package.json
│
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── api/             # API route handlers
│   │   ├── agent/           # AI agent logic
│   │   ├── core/            # Core configuration and utilities
│   │   ├── db/              # Database models and queries
│   │   ├── models/          # Pydantic models
│   │   ├── schemas/         # Request/response schemas
│   │   ├── services/        # Business logic services
│   │   └── main.py          # Application entry point
│   ├── tests/               # Test suite
│   └── requirements.txt
│
├── workers/                  # Background task workers
│   └── tasks/               # Async task definitions
│
├── infra/                   # Infrastructure configuration
│
├── docs/                    # Documentation
│
├── .github/                 # GitHub workflows and configurations
│
├── .env.example             # Environment variables template
├── docker-compose.yml       # Docker Compose configuration
└── README.md               # This file
```

## 🚀 Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure as needed
3. Run the application using Docker:
   ```bash
   docker-compose up
   ```

## 📚 Documentation

See `/docs` for detailed documentation.

## 🔧 Development

- **Frontend**: Next.js TypeScript React app
- **Backend**: FastAPI Python application
- **Workers**: Async task processing

## 📝 License

MIT
