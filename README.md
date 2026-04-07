# OrbitDesk — Advanced AI Ticketing System

A smart internal ticketing platform where AI reads every incoming ticket, classifies it, decides whether to auto-resolve it, and if not, routes it to the correct department and best-fit employee.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Recharts, CSS Variables |
| Backend | Python FastAPI, SQLite |
| AI / LLM | Anthropic Claude (claude-sonnet-4) |
| Fonts | Syne (display) + DM Mono (body) |

---

## Features

### Module 1 — Ticket Intake & AI Analysis
- Every ticket is analyzed by Claude before anything happens
- Returns structured JSON: **category, severity, sentiment, summary, confidence score, estimated resolution time, routing recommendation**
- Categories: Billing, Bug, Access, HR, Server, DB, Feature, Other
- Severity: Critical, High, Medium, Low

### Module 2 — Auto-Resolution Engine
- AI decides if it can handle the ticket without a human (password resets, FAQs, policy questions, billing clarifications)
- Generates a professional, specific auto-response
- User can mark: **Was this helpful? Yes / No**
- Feedback tracked for auto-resolution success rate analytics

### Module 3 — Intelligent Department Routing
- Tickets that need humans are routed per the spec's routing table
- Server/DB issues → Engineering (Critical priority bump)
- Access/account lock → IT (High)
- Legal queries → Legal (High)
- Payroll → Finance, Leave/HR → HR, etc.

### Module 4 — Employee Directory & Assignee Suggestion
- Full employee directory with: name, email, department, role, skill tags, availability (Available/Busy/On Leave)
- AI-suggested assignee considers: **skill match + current load + availability**
- Auto-assigns lowest-load available employee matching required skills
- Admin can add, edit, deactivate employees

### Module 5 — Ticket Lifecycle Management
- Status flow: New → Assigned → In Progress → Pending Info → Resolved → Closed
- Internal notes and external messages
- Full timeline of every action with actor + timestamp
- Escalation: High/Critical tickets auto-reassigned if not picked up within 2 hours (via `/api/escalate-check`)
- Search + filter by status, severity, department, category

### Module 6 — Analytics Dashboard
- Total tickets: open, resolved, auto-resolved, escalated
- Department load bar chart
- Severity breakdown pie chart
- 7-day ticket volume trend
- Avg resolution time by department
- Top 5 ticket categories this week
- Auto-resolution success rate (donut meter)

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Anthropic API key

### Backend
```bash
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python main.py
# Runs on http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
```

The frontend proxies `/api` calls to the backend automatically.

---

## Known Limitations

1. **No real-time updates** — requires page refresh to see new ticket changes (bonus: add WebSocket/SSE)
2. **Escalation is manual trigger** — call `POST /api/escalate-check` or add a cron job for automatic 2-hour checks
3. **No email integration** — notifications are simulated in the UI
4. **SQLite** — fine for demo, switch to PostgreSQL for production multi-user scale
5. **No authentication** — all users share the same view; production would need role-based auth

---

## Project Structure

```
ticketing-system/
├── backend/
│   ├── main.py          # FastAPI app, all routes, AI analysis
│   └── requirements.txt
└── frontend/
    ├── public/index.html
    └── src/
        ├── App.js        # Root + sidebar navigation
        ├── App.css       # Global design system
        ├── pages/
        │   ├── Dashboard.js
        │   ├── NewTicket.js
        │   ├── TicketsPage.js
        │   ├── TicketDetail.js
        │   ├── EmployeesPage.js
        │   └── AnalyticsPage.js
        └── utils/api.js  # All fetch helpers
```
