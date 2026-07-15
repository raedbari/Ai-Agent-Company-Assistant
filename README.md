# Travel-X Company AI Assistant

An intelligent customer-service assistant for **Travel-X**. It understands Arabic customer messages, identifies the appropriate service and department, collects requirements across a multi-turn conversation, and creates a reviewable and editable ticket draft that is not finalized until the customer confirms it.

The project currently runs locally as an integrated MVP. It includes a customer chat interface, a protected department ticket dashboard, persistent storage in PostgreSQL, and request-traffic protection through Redis.

## Project Status

The current version proves the complete core workflow:

~~~text
Customer message
→ Understand intent and service
→ Validate model decisions
→ Collect missing requirements
→ Create a versioned draft
→ Add or edit features
→ Confirm the requested draft version
→ Create exactly one ticket
→ Route it to the responsible department
~~~

## Travel-X Departments

| Department | Main responsibilities |
|---|---|
| CYBTX | Hosting, cybersecurity, backups, monitoring, and AI-agent services |
| TXSaaS | Website, mobile application, SaaS platform, API integration, and software maintenance services |
| Destination | Marketing, logo design, visual identity, and social-media design services |

## Implemented Features

- Classifies customer messages as service requests, questions, clarifications, draft edits, confirmations, abuse, or out-of-scope messages.
- Extracts all explicitly stated requirements from compound messages with evidence from the customer's current message.
- Uses a Decision Guard to prevent unsupported model claims from being persisted.
- Uses a centralized catalog for services, requirements, questions, and departments.
- Preserves conversation state and the active question across multiple messages.
- Handles side questions and returns to the pending requirement.
- Improves the explanation when semantic repetition or clarification failure is detected.
- Uses RAG to answer from company knowledge and return the sources used.
- Uses department agents and skills to specialize each department's knowledge and behavior.
- Creates editable, versioned ticket drafts.
- Requires confirmation of the correct draft version before ticket creation.
- Prevents duplicate tickets through an idempotency key.
- Persists sessions, tickets, and audit events in PostgreSQL.
- Protects request rates and sessions through Redis.
- Provides an Arabic Next.js chat interface and a protected ticket dashboard.

## Technology Stack

### Backend

- Python and FastAPI
- LangChain and LangGraph
- DeepSeek through OpenRouter
- Pydantic and asynchronous SQLAlchemy
- PostgreSQL, Redis, and Alembic
- Pytest

### Frontend

- Next.js, React, and TypeScript
- Tailwind CSS
- jose for signed sessions
- bcryptjs for employee-password verification

## Architecture

~~~mermaid
flowchart TD
    U[Customer] --> F[Next.js Chat UI]
    F --> A[FastAPI]
    A --> G[Traffic Guard]
    G --> W[LangGraph Workflow]
    W --> C[Classifier + Decision Guard]
    C --> P[Policy + Requirements Collector]
    P --> R[RAG / Department Agent]
    P --> D[Ticket Draft and Confirmation]
    D --> DB[(PostgreSQL)]
    G --> RD[(Redis)]
~~~

### Layer Responsibilities

| Layer | Responsibility |
|---|---|
| domain | Conversation state, decisions, services, drafts, and ticket models |
| application | Classification, validation, policies, requirement collection, and ticket creation |
| graph | LangGraph nodes, branches, and conversation workflow orchestration |
| infrastructure | PostgreSQL, Redis, model integration, knowledge base, and skills |
| prompts | Focused model instructions for each task |
| api | HTTP contracts, dependencies, and error handling |
| frontend | Customer chat, employee authentication, and ticket dashboard |

## Project Structure

~~~text
Travel-X-Customer-Agent-Phase-2/
├── frontend/                 # Next.js application
│   └── src/
│       ├── app/              # Pages and frontend API routes
│       └── lib/              # Authentication and shared helpers
├── knowledge/                # Travel-X knowledge used by RAG
├── migrations/               # Database migrations
├── scripts/                  # Local run and diagnostic scripts
├── skills/                   # Department skills and instructions
├── src/travelx_agent/
│   ├── api/
│   ├── application/
│   │   └── ports/
│   ├── core/
│   ├── domain/
│   ├── graph/
│   ├── infrastructure/
│   └── prompts/
├── tests/
├── alembic.ini
├── pyproject.toml
└── README.md
~~~

## Local Requirements

- Python with a virtual environment.
- Node.js and npm.
- PostgreSQL.
- A locally available Redis instance.
- A valid OpenRouter API key.

Versions used during local development included Python 3.13, Node.js 22, and PostgreSQL 14.

## Backend Setup

From the project root in PowerShell:

~~~powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
~~~

Copy the example environment file:

~~~powershell
Copy-Item .env.example .env
~~~

Add local values to .env. Never commit this file to GitHub:

~~~env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=deepseek/deepseek-v4-flash

PERSISTENCE_BACKEND=postgresql
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/travelx_agent

TRAFFIC_GUARD_BACKEND=redis
REDIS_URL=redis://localhost:6379/0

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
~~~

Apply the database migrations:

~~~powershell
alembic upgrade head
~~~

Verify Redis connectivity:

~~~powershell
python scripts\check_redis.py
~~~

Start the backend:

~~~powershell
python -m uvicorn travelx_agent.main:app --reload
~~~

Local URLs:

- Swagger UI: http://127.0.0.1:8000/docs
- Health endpoint: http://127.0.0.1:8000/health

A 404 response from http://127.0.0.1:8000/ is expected because the backend does not define a root route.

## Frontend Setup

~~~powershell
Set-Location .\frontend
npm install
~~~

Create frontend/.env.local:

~~~env
TRAVELX_API_URL=http://127.0.0.1:8000
TRAVELX_ADMIN_USERNAME=
TRAVELX_ADMIN_PASSWORD_HASH_B64=
TRAVELX_AUTH_SECRET=
~~~

This file must contain an employee username, a Base64-encoded bcrypt password hash, and a strong random session secret. Do not store the raw password and never commit .env.local.

Start the frontend:

~~~powershell
npm run dev
~~~

Local URLs:

- Customer chat: http://localhost:3000/
- Employee login: http://localhost:3000/login
- Ticket dashboard: http://localhost:3000/tickets

## Main API Endpoints

### Health Check

~~~http
GET /health
~~~

### Send a Message

~~~http
POST /v1/chat
Content-Type: application/json
~~~

~~~json
{
  "message": "I want to develop a website for my restaurant",
  "session_id": "example-session-001"
}
~~~

To confirm a specific draft version:

~~~json
{
  "message": "Approved, create the ticket",
  "session_id": "example-session-001",
  "draft_version": 2
}
~~~

### Department Tickets

~~~http
GET /v1/departments/{department}/tickets?limit=50
~~~

Available department values:

~~~text
cybtx
txsaas
destination
~~~

## Tests

From the project root:

~~~powershell
python -m compileall src
python -m pytest -q
~~~

The test suite covers requirement collection, evidence validation, repetition handling, clarification behavior, RAG, draft editing, ticket confirmation, idempotency, persistence, and API routes.

## Important Architecture Decisions

### Why LangChain?

LangChain is used for model integration, prompts, structured outputs, tools, and RAG.

### Why LangGraph?

The conversation has explicit state, stages, and branches, including requirement collection, draft review, editing, and confirmation.

### Why a Decision Guard?

The model proposes an interpretation, but the application does not persist a requirement unless it is supported by evidence from the customer's current message.

### Why Is There No Supervisor Yet?

Most requests are routed to one department, so a router or department registry is sufficient. A supervisor should be introduced only when one customer request requires several agents to collaborate and their results must be combined.

## Roadmap

### 1. Protect Administrative Backend Endpoints

Protecting only the Next.js ticket page does not prevent direct access to FastAPI. Authentication and authorization must also be added to:

~~~http
GET /v1/departments/{department}/tickets
~~~

Each employee should only be allowed to access tickets belonging to authorized departments.

### 2. Complete the Ticket Lifecycle

Add statuses such as:

~~~text
new
assigned
in_progress
waiting_for_customer
resolved
closed
~~~

Also add employee assignment, internal notes, and an audit trail for status changes.

### 3. Live Human Handoff

Allow a qualified employee to take over the same customer chat session from the AI assistant.

Required capabilities:

- A HandoffRequest with waiting, active, and closed statuses.
- An employee handoff queue.
- Session ownership transfer from agent to human.
- Access to the transcript, collected requirements, and handoff reason.
- Prevention of AI responses while a human owns the conversation.
- An option for the employee to return the session to the AI assistant.
- Real-time updates or polling for the first version.

### 4. Employee Accounts and Roles

- A separate account for each employee instead of one shared account.
- Department assignments for each employee.
- Administrator, supervisor, and employee roles.
- Audit events for login, ticket assignment, and conversation takeover.

### 5. Model Provider Failure Handling

Convert connection failures and timeouts into a controlled API response, add limited retries, and prevent tracebacks or internal details from reaching the user.

### 6. External Integrations

- Email notifications when a ticket is created.
- CRM integration.
- Department notifications.
- Callback requests.

### 7. Convert the Project into a Reusable Company Template

Separate the generic agent engine from Travel-X data so that services, policies, knowledge, and skills can be replaced without copying and rewriting the entire application.

## Before Publishing to GitHub

Do not publish the project before preparing .gitignore and reviewing every tracked file.

At minimum, exclude:

~~~gitignore
.env
.env.*
!.env.example
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/

frontend/.env.local
frontend/node_modules/
frontend/.next/
frontend/out/

*.log
*.sqlite3
*.db
*.dump
*.sql
*.zip

.vscode/
.idea/
~~~

Review these locations manually:

- knowledge/ for confidential company information.
- skills/ for internal company policies.
- migrations/ for real credentials or connection strings.
- .env.example to ensure it contains only variable names and safe placeholders.
- Git history for secrets that may have been committed previously and later deleted.

If a credential or API key has ever been exposed, deleting it from the current file is not enough. Revoke or rotate the old value.

After preparing .gitignore, inspect the repository with:

~~~powershell
git status --short
git status --ignored
~~~

Do not run git add . until you have reviewed the complete list.

## Notes

- The project is a strong and extensible MVP, but it should not be publicly deployed before administrative backend endpoints are protected.
- Redis must be available when TRAFFIC_GUARD_BACKEND=redis. If Redis is unavailable while REDIS_FAIL_OPEN=false, the API returns 503.
- Real secrets must exist only in environment variables.