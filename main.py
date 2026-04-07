from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
import os
import httpx
from datetime import datetime, timedelta
import uuid

app = FastAPI(title="AI Ticketing System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "ticketing.db"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            skill_tags TEXT DEFAULT '[]',
            availability_status TEXT DEFAULT 'Available',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            submitted_by_email TEXT NOT NULL,
            status TEXT DEFAULT 'New',
            category TEXT,
            severity TEXT,
            sentiment TEXT,
            ai_summary TEXT,
            resolution_path TEXT,
            confidence_score REAL,
            estimated_resolution_hours REAL,
            suggested_department TEXT,
            assigned_to TEXT,
            auto_response TEXT,
            helpful_feedback TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            resolved_at TEXT,
            FOREIGN KEY (assigned_to) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS ticket_timeline (
            id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );

        CREATE TABLE IF NOT EXISTS ticket_notes (
            id TEXT PRIMARY KEY,
            ticket_id TEXT NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            is_internal INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );
    """)
    conn.commit()
    
    # Seed employees if empty
    count = c.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    if count == 0:
        seed_employees(c)
        conn.commit()
    
    conn.close()

def seed_employees(c):
    employees = [
        ("Engineering", "Software Engineer", ["Bug", "Feature", "Database", "Server"]),
        ("Engineering", "Senior Engineer", ["Bug", "Feature", "Server", "Database"]),
        ("Engineering", "DevOps Engineer", ["Server", "Database", "Access"]),
        ("IT", "IT Support Specialist", ["Access", "Bug"]),
        ("IT", "Systems Administrator", ["Server", "Access", "Database"]),
        ("HR", "HR Manager", ["HR"]),
        ("HR", "HR Specialist", ["HR"]),
        ("Finance", "Finance Analyst", ["Billing"]),
        ("Finance", "Payroll Specialist", ["Billing"]),
        ("Product", "Product Manager", ["Feature", "Bug"]),
        ("Marketing", "Marketing Manager", ["Other"]),
        ("Legal", "Legal Counsel", ["Other"]),
    ]
    names = [
        ("Arjun Sharma", "arjun@company.com"),
        ("Priya Patel", "priya@company.com"),
        ("Rahul Nair", "rahul@company.com"),
        ("Sneha Iyer", "sneha@company.com"),
        ("Vikram Reddy", "vikram@company.com"),
        ("Anjali Gupta", "anjali@company.com"),
        ("Kiran Menon", "kiran@company.com"),
        ("Deepa Joshi", "deepa@company.com"),
        ("Suresh Kumar", "suresh@company.com"),
        ("Meera Singh", "meera@company.com"),
        ("Arun Pillai", "arun@company.com"),
        ("Divya Rao", "divya@company.com"),
    ]
    statuses = ["Available", "Available", "Busy", "Available", "On Leave",
                "Available", "Busy", "Available", "Available", "Available", "Available", "Busy"]
    
    for i, ((dept, role, skills), (name, email), status) in enumerate(zip(employees, names, statuses)):
        c.execute(
            "INSERT INTO employees (id, name, email, department, role, skill_tags, availability_status) VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), name, email, dept, role, json.dumps(skills), status)
        )

# ─── AI Analysis ──────────────────────────────────────────────────────────────

async def analyze_ticket_with_ai(title: str, description: str) -> dict:
    prompt = f"""You are an AI support ticket analyzer. Analyze this ticket and return ONLY a valid JSON object with no other text.

Ticket Title: {title}
Ticket Description: {description}

Return this exact JSON structure:
{{
  "category": "<one of: Billing, Bug, Access, HR, Server, DB, Feature, Other>",
  "ai_summary": "<2-3 sentence professional summary of the issue>",
  "severity": "<one of: Critical, High, Medium, Low>",
  "sentiment": "<one of: Frustrated, Neutral, Polite>",
  "resolution_path": "<one of: Auto-resolve, Assign to department>",
  "suggested_department": "<one of: Engineering, IT, Finance, HR, Product, Marketing, Legal, DevOps>",
  "confidence_score": <number between 0.5 and 1.0>,
  "estimated_resolution_hours": <number: 1 to 72>,
  "auto_response": "<if resolution_path is Auto-resolve, write a professional helpful response addressing the specific issue. If Assign to department, write null>",
  "routing_reason": "<one sentence explaining why you chose this department>"
}}

Rules:
- Server down, DB corruption → Critical severity, Engineering/DevOps
- Password reset, FAQ, policy questions → Auto-resolve
- Access/account lock → IT, High severity
- Payroll/salary → Finance
- Leave/HR policy → HR
- Bug reports → Engineering, severity based on impact
- Feature requests → Product/Engineering, Medium severity
- Legal queries → Legal, High severity
- Be specific in the auto_response, reference the actual issue"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            data = resp.json()
            text = data["content"][0]["text"].strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
    except Exception as e:
        # Fallback mock analysis
        return {
            "category": "Other",
            "ai_summary": f"Ticket regarding: {title}. User has submitted a support request requiring attention.",
            "severity": "Medium",
            "sentiment": "Neutral",
            "resolution_path": "Assign to department",
            "suggested_department": "IT",
            "confidence_score": 0.75,
            "estimated_resolution_hours": 8,
            "auto_response": None,
            "routing_reason": "Defaulting to IT support for general requests."
        }

def get_best_assignee(department: str, category: str, db_conn) -> Optional[str]:
    c = db_conn.cursor()
    # Get available employees in the department with matching skills
    employees = c.execute("""
        SELECT e.id, e.name, e.skill_tags, e.availability_status,
               COUNT(t.id) as open_tickets
        FROM employees e
        LEFT JOIN tickets t ON t.assigned_to = e.id AND t.status NOT IN ('Resolved', 'Closed')
        WHERE e.department = ? AND e.is_active = 1 AND e.availability_status != 'On Leave'
        GROUP BY e.id
        ORDER BY 
            CASE WHEN e.availability_status = 'Available' THEN 0 ELSE 1 END,
            open_tickets ASC
    """, (department,)).fetchall()
    
    if not employees:
        return None
    
    # Score by skill match + load
    best = None
    best_score = -1
    for emp in employees:
        skills = json.loads(emp["skill_tags"])
        skill_match = 1 if category in skills else 0
        load_penalty = min(emp["open_tickets"], 5) * 0.1
        avail_bonus = 0.3 if emp["availability_status"] == "Available" else 0
        score = skill_match + avail_bonus - load_penalty
        if score > best_score:
            best_score = score
            best = emp["id"]
    
    return best

def add_timeline_event(conn, ticket_id: str, actor: str, action: str, note: str = None):
    conn.execute(
        "INSERT INTO ticket_timeline (id, ticket_id, actor, action, note) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), ticket_id, actor, action, note)
    )

def check_escalations():
    """Check for unattended High/Critical tickets older than 2 hours"""
    conn = get_db()
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    
    stale = c.execute("""
        SELECT id, suggested_department, category 
        FROM tickets 
        WHERE severity IN ('High', 'Critical') 
        AND status IN ('New', 'Assigned')
        AND created_at < ?
    """, (cutoff,)).fetchall()
    
    for ticket in stale:
        new_assignee = get_best_assignee(ticket["suggested_department"], ticket["category"], conn)
        if new_assignee:
            conn.execute(
                "UPDATE tickets SET assigned_to=?, status='Assigned', updated_at=datetime('now') WHERE id=?",
                (new_assignee, ticket["id"])
            )
            add_timeline_event(conn, ticket["id"], "System", "Auto-escalated", 
                             "Ticket auto-reassigned due to no response within 2 hours")
    
    conn.commit()
    conn.close()

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str
    description: str
    submitted_by: str
    submitted_by_email: str

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    note: Optional[str] = None
    is_internal: Optional[bool] = True

class FeedbackUpdate(BaseModel):
    helpful: bool

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department: str
    role: str
    skill_tags: List[str] = []
    availability_status: str = "Available"

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    skill_tags: Optional[List[str]] = None
    availability_status: Optional[str] = None
    is_active: Optional[bool] = None

# ─── Ticket Routes ────────────────────────────────────────────────────────────

@app.post("/api/tickets")
async def create_ticket(ticket: TicketCreate, background_tasks: BackgroundTasks):
    analysis = await analyze_ticket_with_ai(ticket.title, ticket.description)
    
    conn = get_db()
    ticket_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    status = "Resolved" if analysis["resolution_path"] == "Auto-resolve" else "New"
    assigned_to = None
    
    if status == "New":
        dept = analysis.get("suggested_department", "IT")
        assigned_to = get_best_assignee(dept, analysis["category"], conn)
        if assigned_to:
            status = "Assigned"
    
    conn.execute("""
        INSERT INTO tickets (id, title, description, submitted_by, submitted_by_email,
            status, category, severity, sentiment, ai_summary, resolution_path,
            confidence_score, estimated_resolution_hours, suggested_department,
            assigned_to, auto_response, created_at, updated_at, resolved_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        ticket_id, ticket.title, ticket.description, ticket.submitted_by,
        ticket.submitted_by_email, status, analysis["category"], analysis["severity"],
        analysis["sentiment"], analysis["ai_summary"], analysis["resolution_path"],
        analysis["confidence_score"], analysis["estimated_resolution_hours"],
        analysis.get("suggested_department"), assigned_to,
        analysis.get("auto_response"), now, now,
        now if status == "Resolved" else None
    ))
    
    actor = "AI System"
    if status == "Resolved":
        add_timeline_event(conn, ticket_id, actor, "Auto-resolved", analysis.get("auto_response", "")[:200])
    else:
        add_timeline_event(conn, ticket_id, actor, "Ticket analyzed", 
                          f"Category: {analysis['category']}, Severity: {analysis['severity']}")
        if assigned_to:
            emp = conn.execute("SELECT name FROM employees WHERE id=?", (assigned_to,)).fetchone()
            add_timeline_event(conn, ticket_id, actor, "Assigned", 
                              f"Assigned to {emp['name']} ({analysis.get('suggested_department')})")
    
    conn.commit()
    
    result = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    conn.close()
    
    return dict(result)

@app.get("/api/tickets")
def list_tickets(status: str = None, department: str = None, severity: str = None,
                 category: str = None, search: str = None):
    conn = get_db()
    query = """
        SELECT t.*, e.name as assignee_name, e.department as assignee_dept
        FROM tickets t
        LEFT JOIN employees e ON t.assigned_to = e.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if department:
        query += " AND t.suggested_department = ?"
        params.append(department)
    if severity:
        query += " AND t.severity = ?"
        params.append(severity)
    if category:
        query += " AND t.category = ?"
        params.append(category)
    if search:
        query += " AND (t.title LIKE ? OR t.description LIKE ? OR t.submitted_by LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    query += " ORDER BY CASE t.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, t.created_at DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    conn = get_db()
    ticket = conn.execute("""
        SELECT t.*, e.name as assignee_name, e.email as assignee_email, e.department as assignee_dept
        FROM tickets t LEFT JOIN employees e ON t.assigned_to = e.id
        WHERE t.id = ?
    """, (ticket_id,)).fetchone()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    timeline = conn.execute(
        "SELECT * FROM ticket_timeline WHERE ticket_id=? ORDER BY created_at ASC",
        (ticket_id,)
    ).fetchall()
    
    notes = conn.execute(
        "SELECT * FROM ticket_notes WHERE ticket_id=? ORDER BY created_at ASC",
        (ticket_id,)
    ).fetchall()
    
    conn.close()
    return {
        **dict(ticket),
        "timeline": [dict(t) for t in timeline],
        "notes": [dict(n) for n in notes]
    }

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update: TicketUpdate):
    conn = get_db()
    ticket = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    now = datetime.utcnow().isoformat()
    
    if update.status:
        resolved_at = now if update.status in ("Resolved", "Closed") else ticket["resolved_at"]
        conn.execute(
            "UPDATE tickets SET status=?, updated_at=?, resolved_at=? WHERE id=?",
            (update.status, now, resolved_at, ticket_id)
        )
        add_timeline_event(conn, ticket_id, "Agent", f"Status → {update.status}")
    
    if update.assigned_to:
        emp = conn.execute("SELECT name FROM employees WHERE id=?", (update.assigned_to,)).fetchone()
        conn.execute(
            "UPDATE tickets SET assigned_to=?, status='Assigned', updated_at=? WHERE id=?",
            (update.assigned_to, now, ticket_id)
        )
        if emp:
            add_timeline_event(conn, ticket_id, "Agent", "Reassigned", f"Assigned to {emp['name']}")
    
    if update.note:
        conn.execute(
            "INSERT INTO ticket_notes (id, ticket_id, author, content, is_internal) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), ticket_id, "Agent", update.note, 1 if update.is_internal else 0)
        )
        add_timeline_event(conn, ticket_id, "Agent", "Note added")
    
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/tickets/{ticket_id}/feedback")
def submit_feedback(ticket_id: str, feedback: FeedbackUpdate):
    conn = get_db()
    conn.execute(
        "UPDATE tickets SET helpful_feedback=?, updated_at=datetime('now') WHERE id=?",
        ("yes" if feedback.helpful else "no", ticket_id)
    )
    add_timeline_event(conn, ticket_id, "User", 
                      "Feedback submitted", f"{'Helpful' if feedback.helpful else 'Not helpful'}")
    conn.commit()
    conn.close()
    return {"success": True}

# ─── Employee Routes ───────────────────────────────────────────────────────────

@app.get("/api/employees")
def list_employees(department: str = None, active_only: bool = True):
    conn = get_db()
    query = """
        SELECT e.*,
               COUNT(t.id) as open_tickets,
               AVG(CASE WHEN t.resolved_at IS NOT NULL 
                   THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24 
                   ELSE NULL END) as avg_resolution_hours
        FROM employees e
        LEFT JOIN tickets t ON t.assigned_to = e.id
        WHERE 1=1
    """
    params = []
    if active_only:
        query += " AND e.is_active = 1"
    if department:
        query += " AND e.department = ?"
        params.append(department)
    query += " GROUP BY e.id ORDER BY e.department, e.name"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["skill_tags"] = json.loads(d.get("skill_tags") or "[]")
        d["avg_resolution_hours"] = round(d["avg_resolution_hours"], 1) if d["avg_resolution_hours"] else None
        result.append(d)
    return result

@app.post("/api/employees")
def create_employee(emp: EmployeeCreate):
    conn = get_db()
    emp_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO employees (id, name, email, department, role, skill_tags, availability_status) VALUES (?,?,?,?,?,?,?)",
        (emp_id, emp.name, emp.email, emp.department, emp.role, 
         json.dumps(emp.skill_tags), emp.availability_status)
    )
    conn.commit()
    result = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    conn.close()
    d = dict(result)
    d["skill_tags"] = json.loads(d["skill_tags"])
    return d

@app.patch("/api/employees/{emp_id}")
def update_employee(emp_id: str, update: EmployeeUpdate):
    conn = get_db()
    emp = conn.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not emp:
        raise HTTPException(404, "Employee not found")
    
    fields = []
    params = []
    if update.name is not None:
        fields.append("name=?"); params.append(update.name)
    if update.email is not None:
        fields.append("email=?"); params.append(update.email)
    if update.department is not None:
        fields.append("department=?"); params.append(update.department)
    if update.role is not None:
        fields.append("role=?"); params.append(update.role)
    if update.skill_tags is not None:
        fields.append("skill_tags=?"); params.append(json.dumps(update.skill_tags))
    if update.availability_status is not None:
        fields.append("availability_status=?"); params.append(update.availability_status)
    if update.is_active is not None:
        fields.append("is_active=?"); params.append(1 if update.is_active else 0)
    
    if fields:
        params.append(emp_id)
        conn.execute(f"UPDATE employees SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
    
    conn.close()
    return {"success": True}

# ─── Analytics Routes ──────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics():
    conn = get_db()
    c = conn.cursor()
    
    # Ticket counts
    totals = c.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status NOT IN ('Resolved','Closed') THEN 1 ELSE 0 END) as open,
            SUM(CASE WHEN status IN ('Resolved','Closed') THEN 1 ELSE 0 END) as resolved,
            SUM(CASE WHEN resolution_path='Auto-resolve' THEN 1 ELSE 0 END) as auto_resolved,
            SUM(CASE WHEN status='Escalated' THEN 1 ELSE 0 END) as escalated
        FROM tickets
    """).fetchone()
    
    # Auto-resolution success rate
    auto_stats = c.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN helpful_feedback='yes' THEN 1 ELSE 0 END) as helpful
        FROM tickets WHERE resolution_path='Auto-resolve' AND helpful_feedback IS NOT NULL
    """).fetchone()
    
    success_rate = 0
    if auto_stats["total"] > 0:
        success_rate = round((auto_stats["helpful"] / auto_stats["total"]) * 100, 1)
    
    # Dept load
    dept_load = c.execute("""
        SELECT suggested_department as department, COUNT(*) as count
        FROM tickets WHERE status NOT IN ('Resolved','Closed') AND suggested_department IS NOT NULL
        GROUP BY suggested_department ORDER BY count DESC
    """).fetchall()
    
    # Avg resolution time by dept
    avg_res = c.execute("""
        SELECT suggested_department as department,
               ROUND(AVG((julianday(resolved_at) - julianday(created_at)) * 24), 1) as avg_hours
        FROM tickets WHERE resolved_at IS NOT NULL AND suggested_department IS NOT NULL
        GROUP BY suggested_department
    """).fetchall()
    
    # Top categories this week
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    top_cats = c.execute("""
        SELECT category, COUNT(*) as count FROM tickets
        WHERE created_at >= ? AND category IS NOT NULL
        GROUP BY category ORDER BY count DESC LIMIT 5
    """, (week_ago,)).fetchall()
    
    # Severity breakdown
    severity_breakdown = c.execute("""
        SELECT severity, COUNT(*) as count FROM tickets
        WHERE severity IS NOT NULL GROUP BY severity
    """).fetchall()
    
    # Daily ticket trend (last 7 days)
    daily_trend = c.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM tickets
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """, (week_ago,)).fetchall()
    
    conn.close()
    return {
        "totals": dict(totals),
        "auto_resolution_success_rate": success_rate,
        "dept_load": [dict(r) for r in dept_load],
        "avg_resolution_by_dept": [dict(r) for r in avg_res],
        "top_categories_this_week": [dict(r) for r in top_cats],
        "severity_breakdown": [dict(r) for r in severity_breakdown],
        "daily_trend": [dict(r) for r in daily_trend],
    }

@app.post("/api/escalate-check")
def run_escalation_check():
    check_escalations()
    return {"success": True}

@app.on_event("startup")
def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
