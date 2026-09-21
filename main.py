"""
Vents By Zeus Tickets — Streamlit edition.

Roles: admin, manager, agent, gate.
Features:
  - Modern dark-blue theme, embedded HTML/CSS
  - Events, ticket types, agents, staff (admin/manager/gate)
  - Direct + agent sales, commission ledger, payout workflow
  - Analytics: sales by agent, by ticket type, charts
  - Public ticket lookup, QR codes, one-time gate check-in
  - Reconciliation, audit log, sales CSV export

Run:
    streamlit run main.py
"""
from __future__ import annotations

import csv
import io
import os
import pathlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

import bcrypt
import pandas as pd
import plotly.express as px  # noqa: F401  (available for custom charts)
import plotly.graph_objects as go
import qrcode
import streamlit as st
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------------------
# Paths & configuration
# ---------------------------------------------------------------------------
APP_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = APP_DIR / "vbz_tickets.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
ENV = os.getenv("ENV", "development")

IS_SQLITE = DATABASE_URL.startswith("sqlite")

PAYMENT_METHODS = ["Cash", "EcoCash", "InnBucks", "Bank Transfer", "Card", "Other"]
PAYOUT_METHODS = ["Cash", "EcoCash", "InnBucks", "Bank Transfer"]

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

st.set_page_config(
    page_title="Vents By Zeus Tickets",
    page_icon="🎟️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Theme / UI
# ---------------------------------------------------------------------------
THEME_CSS = """
<style>
:root {
    --vbz-bg-0:      #071120;
    --vbz-bg-1:      #0a1628;
    --vbz-bg-2:      #0f2847;
    --vbz-bg-3:      #163556;
    --vbz-border:    #1e3a5f;
    --vbz-border-hi: #2c5282;
    --vbz-text:      #e6f1ff;
    --vbz-muted:     #8aa8c8;
    --vbz-accent:    #22d3ee;
    --vbz-good:      #34d399;
    --vbz-warn:      #fbbf24;
    --vbz-danger:    #f87171;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}

.stApp {
    background:
        radial-gradient(1200px 600px at 10% -10%, #143a63 0%, transparent 50%),
        radial-gradient(900px 500px at 100% 0%, #0c3355 0%, transparent 50%),
        linear-gradient(180deg, var(--vbz-bg-1) 0%, var(--vbz-bg-0) 100%);
    color: var(--vbz-text);
}

h1, h2, h3, h4 { color: var(--vbz-text); letter-spacing: -0.01em; }
h1 { font-weight: 800; }
h2 { font-weight: 700; }
p, span, label, div { color: var(--vbz-text); }

.vbz-card {
    background: linear-gradient(180deg, rgba(22,53,86,0.7) 0%, rgba(15,40,71,0.85) 100%);
    border: 1px solid var(--vbz-border);
    border-radius: 16px;
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
    backdrop-filter: blur(8px);
}

.vbz-card-tight {
    background: linear-gradient(180deg, rgba(22,53,86,0.6) 0%, rgba(15,40,71,0.75) 100%);
    border: 1px solid var(--vbz-border);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
}

.vbz-kpi {
    position: relative;
    background: linear-gradient(135deg, #163556 0%, #0f2847 100%);
    border: 1px solid var(--vbz-border-hi);
    border-radius: 16px;
    padding: 20px 22px;
    overflow: hidden;
}
.vbz-kpi::after {
    content: "";
    position: absolute;
    top: 0; right: 0;
    width: 120px; height: 120px;
    background: radial-gradient(circle at top right, rgba(34,211,238,0.18), transparent 60%);
    pointer-events: none;
}
.vbz-kpi-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--vbz-muted);
    margin-bottom: 6px;
}
.vbz-kpi-value {
    font-size: 30px;
    font-weight: 800;
    color: var(--vbz-text);
    line-height: 1.1;
}
.vbz-kpi-sub {
    font-size: 12px;
    color: var(--vbz-muted);
    margin-top: 6px;
}

.vbz-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.vbz-badge-good   { background: rgba(52,211,153,0.15); color: var(--vbz-good);   border: 1px solid rgba(52,211,153,0.35); }
.vbz-badge-warn   { background: rgba(251,191,36,0.15);  color: var(--vbz-warn);   border: 1px solid rgba(251,191,36,0.35); }
.vbz-badge-danger { background: rgba(248,113,113,0.15); color: var(--vbz-danger); border: 1px solid rgba(248,113,113,0.35); }
.vbz-badge-info   { background: rgba(34,211,238,0.15);  color: var(--vbz-accent); border: 1px solid rgba(34,211,238,0.35); }
.vbz-badge-muted  { background: rgba(138,168,200,0.12); color: var(--vbz-muted);  border: 1px solid rgba(138,168,200,0.25); }

.vbz-hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 22px 26px;
    border-radius: 18px;
    background:
        linear-gradient(135deg, rgba(34,211,238,0.10), rgba(15,40,71,0.0) 55%),
        linear-gradient(180deg, #163556 0%, #0f2847 100%);
    border: 1px solid var(--vbz-border-hi);
    margin-bottom: 20px;
}
.vbz-hero-title { font-size: 26px; font-weight: 800; margin: 0; }
.vbz-hero-sub   { color: var(--vbz-muted); font-size: 13px; margin-top: 4px; }
.vbz-hero-user  { text-align: right; font-size: 13px; color: var(--vbz-muted); }
.vbz-hero-user b { color: var(--vbz-text); }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0c1f38 0%, #071120 100%);
    border-right: 1px solid var(--vbz-border);
}
section[data-testid="stSidebar"] .vbz-brand {
    font-weight: 900;
    letter-spacing: 0.14em;
    color: var(--vbz-accent);
    font-size: 13px;
    padding: 6px 0 2px 0;
}
section[data-testid="stSidebar"] .vbz-brand small {
    display: block;
    color: var(--vbz-muted);
    letter-spacing: 0.05em;
    font-weight: 400;
    text-transform: none;
    font-size: 11px;
    margin-top: 2px;
}

.stTextInput input, .stNumberInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] > div,
.stDateInput input {
    background: #0b1d33 !important;
    color: var(--vbz-text) !important;
    border-radius: 10px !important;
    border: 1px solid var(--vbz-border) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--vbz-accent) !important;
    box-shadow: 0 0 0 2px rgba(34,211,238,0.15) !important;
}

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    background: linear-gradient(180deg, #22d3ee 0%, #0891b2 100%) !important;
    color: #04121f !important;
    font-weight: 800 !important;
    border: 0 !important;
    border-radius: 10px !important;
    padding: 0.55rem 1.2rem !important;
    box-shadow: 0 6px 18px rgba(34,211,238,0.25) !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
    border-bottom: 1px solid var(--vbz-border);
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--vbz-muted);
    border-radius: 10px 10px 0 0;
    padding: 10px 16px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(180deg, rgba(34,211,238,0.12), rgba(34,211,238,0.0)) !important;
    color: var(--vbz-accent) !important;
    border-bottom: 2px solid var(--vbz-accent);
}

[data-testid="stDataFrame"] {
    background: #0b1d33;
    border-radius: 12px;
    border: 1px solid var(--vbz-border);
    overflow: hidden;
}

details, .streamlit-expanderHeader {
    background: #0f2847 !important;
    border-radius: 10px !important;
    border: 1px solid var(--vbz-border) !important;
}

.stAlert {
    border-radius: 10px !important;
    border: 1px solid var(--vbz-border-hi) !important;
}

hr { border-color: var(--vbz-border) !important; }
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", user: Optional[dict] = None):
    role_labels = {
        "admin": "Administrator",
        "manager": "Manager",
        "agent": "Agent",
        "gate": "Gate Staff",
    }
    role = role_labels.get(user.get("role") if user else "", "Guest")
    username = user.get("username", "") if user else ""
    st.markdown(
        f"""
        <div class="vbz-hero">
            <div>
                <div class="vbz-hero-title">{title}</div>
                <div class="vbz-hero-sub">{subtitle}</div>
            </div>
            <div class="vbz-hero-user">
                <b>{username or 'Not signed in'}</b><br>{role}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, sub: str = "", accent: str = ""):
    value_style = f"color:{accent};" if accent else ""
    sub_html = f'<div class="vbz-kpi-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="vbz-kpi">
            <div class="vbz-kpi-label">{label}</div>
            <div class="vbz-kpi-value" style="{value_style}">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "muted") -> str:
    return f'<span class="vbz-badge vbz-badge-{kind}">{text}</span>'


def status_badge(status: str) -> str:
    mapping = {"PAID": "good", "USED": "info", "CANCELLED": "danger"}
    return badge(status, mapping.get(status, "muted"))


def card_open(title: str = ""):
    st.markdown('<div class="vbz-card">', unsafe_allow_html=True)
    if title:
        st.markdown(f"### {title}")


def card_close():
    st.markdown("</div>", unsafe_allow_html=True)


CHART_COLORS = [
    "#22d3ee", "#38bdf8", "#818cf8", "#a78bfa",
    "#f472b6", "#fbbf24", "#34d399", "#f87171",
]


def bar_chart(labels: list[str], values: list[float], title: str = "") -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker=dict(color=CHART_COLORS[: len(labels)],
                        line=dict(color="#0a1628", width=1)),
            text=[f"${v:,.2f}" for v in values],
            textposition="outside",
            hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(color="#e6f1ff", size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6f1ff", family="Arial"),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(showgrid=False, tickfont=dict(color="#8aa8c8")),
        yaxis=dict(showgrid=True, gridcolor="#1e3a5f",
                   tickfont=dict(color="#8aa8c8"), zeroline=False),
        bargap=0.35,
        height=340,
    )
    return fig


def pie_chart(labels: list[str], values: list[float], title: str = "") -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=CHART_COLORS[: len(labels)],
                        line=dict(color="#0a1628", width=2)),
            textinfo="percent",
            textfont=dict(color="#0a1628", size=12, family="Arial"),
            hovertemplate="%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(color="#e6f1ff", size=15)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6f1ff", family="Arial"),
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=True,
        legend=dict(font=dict(color="#e6f1ff"), bgcolor="rgba(0,0,0,0)"),
        height=340,
    )
    return fig


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin", nullable=False)  # admin|manager|gate|agent:<id>
    active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    venue = Column(String, nullable=False)
    event_date = Column(String, nullable=False)
    capacity = Column(Integer, default=0)
    active = Column(Boolean, default=True)


class TicketType(Base):
    __tablename__ = "ticket_types"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    allocation = Column(Integer, default=0)
    event = relationship("Event")


class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, default="")
    commission_rate = Column(Numeric(5, 2), default=Decimal("15.00"))
    active = Column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    reference = Column(String, unique=True, nullable=False, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    ticket_type_id = Column(Integer, ForeignKey("ticket_types.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    buyer_name = Column(String, nullable=False)
    buyer_phone = Column(String, default="")
    payment_method = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default="PAID")
    created_at = Column(DateTime, default=utcnow)
    used_at = Column(DateTime, nullable=True)
    event = relationship("Event")
    ticket_type = relationship("TicketType")
    agent = relationship("Agent")


class Commission(Base):
    __tablename__ = "commissions"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    rate = Column(Numeric(5, 2), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    paid = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    ticket = relationship("Ticket")


class Payout(Base):
    __tablename__ = "payouts"
    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String, default="Cash")
    note = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)
    agent = relationship("Agent")


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    method = Column(String, nullable=False)
    reference = Column(String, default="")
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    detail = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)


Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Auto-migration (adds columns to existing SQLite DBs)
# ---------------------------------------------------------------------------
def auto_migrate():
    if not IS_SQLITE:
        return
    if not DB_PATH.exists():
        return
    import sqlite3
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    def cols(table: str) -> set[str]:
        cur.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in cur.fetchall()}

    def has_table(table: str) -> bool:
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cur.fetchone() is not None

    def add(table: str, column: str, ddl: str):
        if has_table(table) and column not in cols(table):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            con.commit()
            print(f"[migrate] added {table}.{column}")

    add("payouts", "method", "VARCHAR DEFAULT 'Cash'")
    add("users", "must_change_password", "BOOLEAN DEFAULT 0")
    add("users", "active", "BOOLEAN DEFAULT 1")
    add("tickets", "used_at", "DATETIME")

    con.close()


auto_migrate()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def q2(value) -> Decimal:
    return to_decimal(value).quantize(Decimal("0.01"))


def make_qr_png(url: str) -> bytes:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_session() -> Session:
    return SessionLocal()


def audit(db: Session, actor: str, action: str, detail: str = ""):
    db.add(AuditLog(actor=actor, action=action, detail=detail[:500]))


def bootstrap():
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username=ADMIN_USERNAME).first():
            db.add(User(
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
                active=True,
                must_change_password=(ENV == "production"),
            ))
            db.commit()
    finally:
        db.close()


bootstrap()


def generate_reference(db: Session, event_id: int) -> str:
    for _ in range(20):
        ref = f"VBZ-{event_id:03d}-{secrets.token_hex(3).upper()}"
        if not db.query(Ticket.id).filter_by(reference=ref).first():
            return ref
    return f"VBZ-{event_id:03d}-{secrets.token_hex(5).upper()}"


def generate_agent_code(db: Session) -> str:
    for _ in range(50):
        code = f"VBZ{secrets.randbelow(9000) + 1000}"
        if not db.query(Agent.id).filter_by(code=code).first():
            return code
    return f"VBZ{secrets.token_hex(3).upper()}"


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------
def agent_ledger(db: Session, agent_id: int) -> dict:
    earned = q2(db.query(func.coalesce(func.sum(Commission.amount), 0))
                .filter_by(agent_id=agent_id).scalar())
    paid_commissions = q2(db.query(func.coalesce(func.sum(Commission.amount), 0))
                          .filter(Commission.agent_id == agent_id,
                                  Commission.paid.is_(True)).scalar())
    unpaid_commissions = q2(db.query(func.coalesce(func.sum(Commission.amount), 0))
                            .filter(Commission.agent_id == agent_id,
                                    Commission.paid.is_(False)).scalar())
    paid_payouts = q2(db.query(func.coalesce(func.sum(Payout.amount), 0))
                      .filter_by(agent_id=agent_id).scalar())
    outstanding = q2(earned - paid_payouts)
    return {
        "earned": earned,
        "paid_commissions": paid_commissions,
        "unpaid_commissions": unpaid_commissions,
        "paid_payouts": paid_payouts,
        "outstanding": outstanding,
    }


def sales_by_agent(db: Session) -> list[dict]:
    rows = (
        db.query(
            Ticket.agent_id,
            func.count(Ticket.id).label("count"),
            func.coalesce(func.sum(Ticket.amount), 0).label("total"),
        )
        .filter(Ticket.status.in_(["PAID", "USED"]))
        .group_by(Ticket.agent_id)
        .all()
    )
    agent_map = {a.id: a for a in db.query(Agent).all()}
    out: list[dict] = []
    for agent_id, count, total in rows:
        total_d = q2(total)
        if agent_id is None:
            out.append({
                "code": "DIRECT", "name": "Direct / Admin", "label": "Direct / Admin",
                "count": count, "total": total_d, "commission": Decimal("0"),
            })
        else:
            a = agent_map.get(agent_id)
            rate = to_decimal(a.commission_rate) if a else Decimal("0")
            out.append({
                "code": a.code if a else f"agent:{agent_id}",
                "name": a.name if a else "",
                "label": f"{a.code} — {a.name}" if a else f"agent:{agent_id}",
                "count": count,
                "total": total_d,
                "commission": q2(total_d * rate / Decimal("100")),
            })
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


def sales_by_ticket_type(db: Session) -> list[dict]:
    rows = (
        db.query(
            Ticket.ticket_type_id,
            func.count(Ticket.id).label("count"),
            func.coalesce(func.sum(Ticket.amount), 0).label("total"),
        )
        .filter(Ticket.status.in_(["PAID", "USED"]))
        .group_by(Ticket.ticket_type_id)
        .all()
    )
    tt_map = {t.id: t for t in db.query(TicketType).all()}
    out: list[dict] = []
    for tt_id, count, total in rows:
        tt = tt_map.get(tt_id)
        event_name = tt.event.name if tt and tt.event else ""
        tt_name = tt.name if tt else f"type:{tt_id}"
        out.append({
            "event": event_name,
            "ticket_type": tt_name,
            "label": f"{event_name} — {tt_name}" if event_name else tt_name,
            "count": count,
            "total": q2(total),
        })
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


def agent_sales_by_type(db: Session, agent_id: int) -> list[dict]:
    rows = (
        db.query(
            Ticket.ticket_type_id,
            func.count(Ticket.id).label("count"),
            func.coalesce(func.sum(Ticket.amount), 0).label("total"),
        )
        .filter(Ticket.status.in_(["PAID", "USED"]), Ticket.agent_id == agent_id)
        .group_by(Ticket.ticket_type_id)
        .all()
    )
    tt_map = {t.id: t for t in db.query(TicketType).all()}
    out: list[dict] = []
    for tt_id, count, total in rows:
        tt = tt_map.get(tt_id)
        event_name = tt.event.name if tt and tt.event else ""
        tt_name = tt.name if tt else f"type:{tt_id}"
        out.append({
            "event": event_name,
            "ticket_type": tt_name,
            "label": f"{event_name} — {tt_name}" if event_name else tt_name,
            "count": count,
            "total": q2(total),
        })
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_state():
    for k, v in {
        "user": None,
        "page": "login",
        "flash": None,
        "last_ticket_id": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def set_flash(kind: str, message: str):
    st.session_state.flash = (kind, message)


def show_flash():
    if st.session_state.flash:
        kind, message = st.session_state.flash
        {"success": st.success, "error": st.error,
         "warning": st.warning, "info": st.info}[kind](message)
        st.session_state.flash = None


def current_user() -> Optional[dict]:
    return st.session_state.get("user")


def require_role(*roles: str) -> Optional[dict]:
    u = current_user()
    if not u:
        st.session_state.page = "login"
        st.rerun()
        return None
    if roles and u["role"] not in roles:
        st.error("You do not have permission to view this page.")
        return None
    return u


def logout():
    st.session_state.user = None
    st.session_state.page = "login"
    st.rerun()


# ---------------------------------------------------------------------------
# Business logic — create sale
# ---------------------------------------------------------------------------
def create_sale(
    db: Session,
    *,
    actor: str,
    ticket_type_id: int,
    buyer_name: str,
    buyer_phone: str,
    payment_method: str,
    agent_id: Optional[int],
) -> tuple[Optional[Ticket], Optional[str]]:
    if payment_method not in PAYMENT_METHODS:
        return None, "Invalid payment method"
    if not buyer_name.strip():
        return None, "Buyer name is required"

    tt = db.get(TicketType, ticket_type_id)
    if not tt:
        return None, "Ticket type not found"

    used = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_type_id == tt.id,
            Ticket.status.in_(["PAID", "USED"]),
        )
        .count()
    )
    if tt.allocation and used >= tt.allocation:
        return None, "Ticket allocation sold out"

    token = secrets.token_urlsafe(32)
    ref = generate_reference(db, tt.event_id)

    t = Ticket(
        reference=ref,
        token=token,
        event_id=tt.event_id,
        ticket_type_id=tt.id,
        agent_id=agent_id,
        buyer_name=buyer_name.strip(),
        buyer_phone=buyer_phone.strip(),
        payment_method=payment_method,
        amount=q2(tt.price),
        status="PAID",
    )
    db.add(t)
    db.flush()
    db.add(PaymentRecord(ticket_id=t.id, method=payment_method, verified=True))

    if agent_id:
        a = db.get(Agent, agent_id)
        if a:
            rate = to_decimal(a.commission_rate)
            commission_amount = q2(to_decimal(tt.price) * rate / Decimal("100"))
            db.add(Commission(
                ticket_id=t.id,
                agent_id=agent_id,
                rate=rate,
                amount=commission_amount,
            ))

    audit(db, actor, "SALE",
          f"ref={ref}; amount={tt.price}; method={payment_method}; "
          f"agent={agent_id or 'direct'}")
    db.commit()
    return t, None


# ---------------------------------------------------------------------------
# Page — Login
# ---------------------------------------------------------------------------
def page_login():
    inject_theme()

    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        st.markdown(
            """
            <div style="text-align:center;padding-top:20px">
                <div style="font-size:52px">🎟️</div>
                <div style="font-size:26px;font-weight:900;letter-spacing:0.06em;color:#22d3ee;margin-top:6px">
                    VENTS BY ZEUS
                </div>
                <div style="color:#8aa8c8;letter-spacing:0.2em;font-size:12px;margin-bottom:22px">
                    TICKETING PLATFORM
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="vbz-card">', unsafe_allow_html=True)
        st.markdown("### Staff Login")
        show_flash()

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            db = get_session()
            try:
                u = db.query(User).filter_by(username=username, active=True).first()
                if not u or not verify_password(password, u.password_hash):
                    audit(db, "anonymous", "LOGIN_FAIL", f"username={username}")
                    db.commit()
                    st.error("Incorrect username or password.")
                    return

                role = "admin"
                agent_id: Optional[int] = None
                if u.role.startswith("agent:"):
                    try:
                        agent_id = int(u.role.split(":", 1)[1])
                    except (ValueError, IndexError):
                        st.error("Broken account configuration.")
                        return
                    a = db.get(Agent, agent_id)
                    if not a or not a.active:
                        st.error("This agent account is suspended.")
                        return
                    role = "agent"
                elif u.role in ("gate", "manager", "admin"):
                    role = u.role

                audit(db, f"{role}:{username}", "LOGIN_OK", "")
                db.commit()

                st.session_state.user = {
                    "username": u.username,
                    "role": role,
                    "agent_id": agent_id,
                    "must_change_password": bool(u.must_change_password),
                }
                st.session_state.page = {
                    "admin": "dashboard",
                    "manager": "dashboard",
                    "agent": "agent",
                    "gate": "scan",
                }[role]
                st.rerun()
            finally:
                db.close()

        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page — Dashboard (admin + manager)
# ---------------------------------------------------------------------------
def page_dashboard():
    u = require_role("admin", "manager")
    if not u:
        return

    inject_theme()
    hero("Management Dashboard", "Events • Sales • Agents • Payouts • Analytics", u)
    show_flash()

    if u.get("must_change_password"):
        st.warning("You are using a temporary password. Change it from **Change Password** in the sidebar.")

    db = get_session()
    try:
        sold = db.query(Ticket).filter(Ticket.status.in_(["PAID", "USED"])).count()
        scanned = db.query(Ticket).filter(Ticket.status == "USED").count()
        revenue = q2(
            db.query(func.coalesce(func.sum(Ticket.amount), 0))
            .filter(Ticket.status.in_(["PAID", "USED"]))
            .scalar()
        )
        commissions = q2(db.query(func.coalesce(func.sum(Commission.amount), 0)).scalar())
        commissions_unpaid = q2(
            db.query(func.coalesce(func.sum(Commission.amount), 0))
            .filter(Commission.paid.is_(False))
            .scalar()
        )
        net = q2(revenue - commissions)

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: kpi("Gross Sales", f"${revenue}", f"{sold} tickets")
        with c2: kpi("Tickets Sold", str(sold), "Paid + used")
        with c3: kpi("Checked In", str(scanned), "Redeemed", accent="#34d399")
        with c4: kpi("Commission Owed", f"${commissions_unpaid}", "Unpaid", accent="#fbbf24")
        with c5: kpi("Net Revenue", f"${net}", f"After ${commissions} commission")

        st.write("")
        tabs = st.tabs([
            "📅 Events", "🎫 Ticket Types", "🧑‍💼 Agents", "💸 Payouts",
            "🚪 Gate Users", "🧑‍💼 Staff & Admins", "🧾 Recent Sales",
            "📊 Analytics",
        ])

        # -------- Events --------
        with tabs[0]:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                card_open("Create Event")
                with st.form("create_event", clear_on_submit=True):
                    name = st.text_input("Event name")
                    venue = st.text_input("Venue")
                    event_date = st.date_input("Event date")
                    capacity = st.number_input("Capacity", min_value=0, step=1, value=100)
                    if st.form_submit_button("Create Event", use_container_width=True):
                        if not name or not venue:
                            st.error("Name and venue are required.")
                        else:
                            db.add(Event(name=name, venue=venue,
                                         event_date=str(event_date),
                                         capacity=int(capacity)))
                            audit(db, f"{u['role']}:{u['username']}", "EVENT_CREATE",
                                  f"name={name}")
                            db.commit()
                            set_flash("success", f"Event '{name}' created.")
                            st.rerun()
                card_close()
            with col_list:
                card_open("All Events")
                events = db.query(Event).order_by(Event.id.desc()).all()
                if events:
                    st.dataframe(pd.DataFrame([{
                        "ID": e.id, "Name": e.name, "Venue": e.venue,
                        "Date": e.event_date, "Capacity": e.capacity,
                        "Active": "✅" if e.active else "—",
                    } for e in events]), use_container_width=True, hide_index=True)
                else:
                    st.info("No events yet.")
                card_close()

        # -------- Ticket Types --------
        with tabs[1]:
            events = db.query(Event).filter(Event.active.is_(True)).all()
            col_form, col_list = st.columns([1, 2])
            with col_form:
                card_open("Add Ticket Type")
                if not events:
                    st.info("Create an event first.")
                else:
                    with st.form("create_tt", clear_on_submit=True):
                        ev = st.selectbox("Event", options=events,
                                          format_func=lambda e: f"{e.name} ({e.event_date})")
                        tt_name = st.text_input("Name (General / VIP / VVIP)")
                        price = st.number_input("Price (USD)", min_value=0.0, step=0.5, format="%.2f")
                        allocation = st.number_input("Allocation", min_value=0, step=1, value=100)
                        if st.form_submit_button("Add Ticket Type", use_container_width=True):
                            if not tt_name:
                                st.error("Name is required.")
                            else:
                                db.add(TicketType(event_id=ev.id, name=tt_name,
                                                  price=Decimal(str(price)),
                                                  allocation=int(allocation)))
                                audit(db, f"{u['role']}:{u['username']}", "TICKETTYPE_CREATE",
                                      f"event={ev.id}; name={tt_name}")
                                db.commit()
                                set_flash("success", "Ticket type added.")
                                st.rerun()
                card_close()
            with col_list:
                card_open("All Ticket Types")
                tts = db.query(TicketType).all()
                if tts:
                    st.dataframe(pd.DataFrame([{
                        "ID": tt.id,
                        "Event": tt.event.name if tt.event else "",
                        "Name": tt.name,
                        "Price": float(tt.price),
                        "Allocation": tt.allocation,
                    } for tt in tts]), use_container_width=True, hide_index=True)
                else:
                    st.info("No ticket types yet.")
                card_close()

        # -------- Agents --------
        with tabs[2]:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                card_open("Create Agent")
                with st.form("create_agent", clear_on_submit=True):
                    a_name = st.text_input("Agent name")
                    a_phone = st.text_input("Phone")
                    a_rate = st.number_input("Commission rate (%)",
                                             min_value=0.0, max_value=100.0,
                                             value=15.0, step=0.5)
                    if st.form_submit_button("Create Agent", use_container_width=True):
                        if not a_name:
                            st.error("Name is required.")
                        else:
                            code = generate_agent_code(db)
                            ag = Agent(code=code, name=a_name, phone=a_phone,
                                       commission_rate=Decimal(str(a_rate)))
                            db.add(ag); db.flush()
                            temp_password = secrets.token_urlsafe(9)
                            db.add(User(username=code.lower(),
                                        password_hash=hash_password(temp_password),
                                        role=f"agent:{ag.id}",
                                        active=True,
                                        must_change_password=True))
                            audit(db, f"{u['role']}:{u['username']}", "AGENT_CREATE",
                                  f"code={code}; name={a_name}")
                            db.commit()
                            set_flash("success", "Agent created.")
                            st.info(f"**Username:** `{code.lower()}`  \n"
                                    f"**Temporary password:** `{temp_password}`  \n"
                                    "Share securely — the agent must change it on first login.")
                card_close()
            with col_list:
                card_open("All Agents")
                agents = db.query(Agent).order_by(Agent.id.desc()).all()
                if not agents:
                    st.info("No agents yet.")
                for a in agents:
                    ledger = agent_ledger(db, a.id)
                    label = f"{a.code} — {a.name}  •  {'Active' if a.active else 'Suspended'}"
                    with st.expander(label):
                        c1, c2, c3, c4 = st.columns(4)
                        with c1: kpi("Earned", f"${ledger['earned']}")
                        with c2: kpi("Paid Out", f"${ledger['paid_payouts']}")
                        with c3: kpi("Outstanding", f"${ledger['outstanding']}", accent="#fbbf24")
                        with c4: kpi("Commission %", f"{a.commission_rate}")
                        st.write("")
                        cr, cs, cb = st.columns([1, 1, 1])
                        new_rate = cr.number_input("Commission %", min_value=0.0,
                                                   max_value=100.0,
                                                   value=float(a.commission_rate),
                                                   step=0.5, key=f"rate_{a.id}")
                        new_active = cs.selectbox("Status", options=[True, False],
                                                  index=0 if a.active else 1,
                                                  format_func=lambda b: "Active" if b else "Suspended",
                                                  key=f"active_{a.id}")
                        if cb.button("Save", key=f"save_{a.id}", use_container_width=True):
                            a.commission_rate = Decimal(str(new_rate))
                            a.active = new_active
                            urow = db.query(User).filter_by(username=a.code.lower()).first()
                            if urow:
                                urow.active = new_active
                            audit(db, f"{u['role']}:{u['username']}", "AGENT_SETTINGS",
                                  f"agent={a.id}; rate={new_rate}; active={new_active}")
                            db.commit()
                            set_flash("success", "Agent settings saved.")
                            st.rerun()
                card_close()

        # -------- Payouts --------
        with tabs[3]:
            st.markdown("#### Process an Agent Payout")
            st.caption("Record money paid to an agent. Marks outstanding commissions as paid and writes to the audit log.")

            agents = db.query(Agent).order_by(Agent.name).all()
            if not agents:
                st.info("Create an agent first.")
            else:
                col_form, col_summary = st.columns([1, 1])
                with col_form:
                    card_open("New Payout")
                    agent = st.selectbox("Agent", options=agents,
                                         format_func=lambda a: f"{a.code} — {a.name}",
                                         key="payout_agent")
                    ledger = agent_ledger(db, agent.id)
                    st.markdown(
                        f"""
                        <div style="display:flex;gap:16px;margin-bottom:10px">
                            <div>
                                <div class="vbz-kpi-label">Outstanding</div>
                                <div class="vbz-kpi-value" style="color:#fbbf24;font-size:22px">
                                    ${ledger['outstanding']}
                                </div>
                            </div>
                            <div>
                                <div class="vbz-kpi-label">Unpaid Commission</div>
                                <div class="vbz-kpi-value" style="font-size:22px">
                                    ${ledger['unpaid_commissions']}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with st.form("payout_form", clear_on_submit=True):
                        amount = st.number_input(
                            "Amount to pay (USD)", min_value=0.0,
                            max_value=float(max(ledger["outstanding"], Decimal("0"))) or 1e9,
                            step=0.5, format="%.2f",
                            value=float(max(ledger["outstanding"], Decimal("0"))))
                        method = st.selectbox("Payment method", PAYOUT_METHODS)
                        note = st.text_input("Note (optional)", placeholder="Week 1 settlement")
                        submitted = st.form_submit_button("Record Payout", use_container_width=True)

                    if submitted:
                        if amount <= 0:
                            st.error("Amount must be greater than 0.")
                        else:
                            amount_dec = q2(amount)
                            unpaid = (db.query(Commission)
                                      .filter_by(agent_id=agent.id, paid=False)
                                      .order_by(Commission.id.asc()).all())
                            remaining = amount_dec
                            marked = 0
                            for c in unpaid:
                                if remaining <= 0:
                                    break
                                c.paid = True
                                remaining -= to_decimal(c.amount)
                                marked += 1
                            db.add(Payout(agent_id=agent.id, amount=amount_dec,
                                          method=method, note=note))
                            audit(db, f"{u['role']}:{u['username']}", "PAYOUT",
                                  f"agent={agent.id}; amount={amount_dec}; "
                                  f"method={method}; commissions_marked={marked}")
                            db.commit()
                            set_flash("success",
                                      f"Recorded ${amount_dec} payout to {agent.name} "
                                      f"({marked} commission entries marked paid).")
                            st.rerun()
                    card_close()

                with col_summary:
                    card_open("Recent Payouts")
                    recent = db.query(Payout).order_by(Payout.id.desc()).limit(25).all()
                    if recent:
                        st.dataframe(pd.DataFrame([{
                            "Agent": p.agent.code if p.agent else "",
                            "Amount": float(p.amount),
                            "Method": p.method,
                            "Note": p.note,
                            "When": p.created_at,
                        } for p in recent]), use_container_width=True, hide_index=True)
                    else:
                        st.info("No payouts recorded yet.")
                    card_close()

                st.markdown("#### Agent Balances at a Glance")
                rows = []
                for a in agents:
                    led = agent_ledger(db, a.id)
                    rows.append({
                        "Code": a.code, "Name": a.name,
                        "Commission %": float(a.commission_rate),
                        "Earned": float(led["earned"]),
                        "Paid Out": float(led["paid_payouts"]),
                        "Outstanding": float(led["outstanding"]),
                        "Status": "Active" if a.active else "Suspended",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # -------- Gate Users --------
        with tabs[4]:
            col_form, col_list = st.columns([1, 2])
            with col_form:
                card_open("Add Gate User")
                with st.form("create_gate", clear_on_submit=True):
                    g_user = st.text_input("Username")
                    g_pass = st.text_input("Password (min 10 chars)", type="password")
                    if st.form_submit_button("Create Gate User", use_container_width=True):
                        if len(g_pass) < 10:
                            st.error("Password must be at least 10 characters.")
                        elif not g_user:
                            st.error("Username is required.")
                        elif db.query(User).filter_by(username=g_user).first():
                            st.error("Username already exists.")
                        else:
                            db.add(User(username=g_user,
                                        password_hash=hash_password(g_pass),
                                        role="gate", active=True,
                                        must_change_password=True))
                            audit(db, f"{u['role']}:{u['username']}", "GATE_USER_CREATE",
                                  f"username={g_user}")
                            db.commit()
                            set_flash("success", f"Gate user '{g_user}' created.")
                            st.rerun()
                card_close()
            with col_list:
                card_open("Gate Users")
                gate_users = db.query(User).filter_by(role="gate").all()
                if gate_users:
                    st.dataframe(pd.DataFrame([{
                        "Username": gu.username,
                        "Active": "✅" if gu.active else "—",
                        "Must change password": "Yes" if gu.must_change_password else "No",
                    } for gu in gate_users]), use_container_width=True, hide_index=True)
                else:
                    st.info("No gate users yet.")
                card_close()

        # -------- Staff (admins + managers + gate) --------
        with tabs[5]:
            st.markdown("#### Staff & Admin Accounts")
            st.caption("Managers can sell tickets, run reconciliation, and view reports. "
                       "Only admins can create admin/manager accounts or reset their passwords.")

            col_form, col_list = st.columns([1, 2])
            with col_form:
                card_open("New Staff Member")
                current_role = u["role"]
                with st.form("create_staff", clear_on_submit=True):
                    s_username = st.text_input("Username (e.g. tina.admin)")
                    s_password = st.text_input("Temporary password (min 10 chars)", type="password")
                    s_role = st.selectbox(
                        "Role", options=["manager", "admin", "gate"],
                        format_func=lambda r: {
                            "admin": "Admin — full access",
                            "manager": "Manager — reports + sales",
                            "gate": "Gate — scanning only",
                        }[r],
                        disabled=(current_role != "admin"),
                    )
                    st.caption(
                        "Only admins can create new admin or manager accounts."
                        if current_role == "admin"
                        else "As a manager, you can create gate accounts only."
                    )
                    submitted = st.form_submit_button("Create Account", use_container_width=True)

                if submitted:
                    if current_role != "admin" and s_role in ("admin", "manager"):
                        st.error("Only admins can create admin or manager accounts.")
                    elif len(s_password) < 10:
                        st.error("Password must be at least 10 characters.")
                    elif not s_username or len(s_username) < 3:
                        st.error("Username must be at least 3 characters.")
                    elif db.query(User).filter_by(username=s_username).first():
                        st.error("Username already exists.")
                    else:
                        db.add(User(username=s_username,
                                    password_hash=hash_password(s_password),
                                    role=s_role, active=True,
                                    must_change_password=True))
                        audit(db, f"{u['role']}:{u['username']}", "STAFF_CREATE",
                              f"username={s_username}; role={s_role}")
                        db.commit()
                        set_flash("success", f"{s_role.title()} '{s_username}' created.")
                        st.rerun()
                card_close()

            with col_list:
                card_open("All Staff Accounts")
                staff = (db.query(User)
                         .filter(User.role.in_(["admin", "manager", "gate"]))
                         .order_by(User.id.desc()).all())
                if not staff:
                    st.info("No staff accounts yet.")
                else:
                    st.dataframe(pd.DataFrame([{
                        "Username": s.username,
                        "Role": s.role.title(),
                        "Active": "✅" if s.active else "🚫",
                        "Must change password": "Yes" if s.must_change_password else "No",
                    } for s in staff]), use_container_width=True, hide_index=True)

                    st.markdown("##### Manage accounts")
                    for s in staff:
                        if s.username == u["username"]:
                            continue
                        with st.expander(f"{s.username} — {s.role}"):
                            c1, c2 = st.columns([1, 1])
                            new_active = c1.selectbox(
                                "Status", options=[True, False],
                                index=0 if s.active else 1,
                                format_func=lambda b: "Active" if b else "Suspended",
                                key=f"staff_active_{s.id}")
                            if c2.button("Save", key=f"staff_save_{s.id}",
                                         use_container_width=True):
                                if u["role"] != "admin" and s.role in ("admin", "manager"):
                                    st.error("Only admins can modify admin or manager accounts.")
                                else:
                                    s.active = new_active
                                    if not s.active:
                                        s.must_change_password = True
                                    audit(db, f"{u['role']}:{u['username']}", "STAFF_SETTINGS",
                                          f"username={s.username}; active={s.active}")
                                    db.commit()
                                    set_flash("success", "Account updated.")
                                    st.rerun()

                            st.caption("Reset password")
                            reset_pw = st.text_input("New temporary password (min 10)",
                                                     type="password",
                                                     key=f"staff_pw_{s.id}")
                            if st.button("Reset Password", key=f"staff_pwbtn_{s.id}",
                                         use_container_width=True):
                                if len(reset_pw) < 10:
                                    st.error("Password must be at least 10 characters.")
                                elif u["role"] != "admin" and s.role in ("admin", "manager"):
                                    st.error("Only admins can reset admin or manager passwords.")
                                else:
                                    s.password_hash = hash_password(reset_pw)
                                    s.must_change_password = True
                                    audit(db, f"{u['role']}:{u['username']}",
                                          "STAFF_PASSWORD_RESET", f"username={s.username}")
                                    db.commit()
                                    set_flash("success", f"Password reset for {s.username}.")
                                    st.rerun()
                card_close()

        # -------- Recent Sales --------
        with tabs[6]:
            st.markdown("#### Recent Sales")
            recent = db.query(Ticket).order_by(Ticket.id.desc()).limit(25).all()
            if not recent:
                st.info("No sales yet.")
            for t in recent:
                with st.expander(f"{t.reference} — {t.buyer_name} — ${t.amount} — {t.status}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Event:** {t.event.name}")
                        st.write(f"**Ticket:** {t.ticket_type.name}")
                        st.write(f"**Payment:** {t.payment_method}")
                        st.write(f"**Agent:** {t.agent.code if t.agent else 'DIRECT'}")
                        st.write(f"**Created:** {t.created_at}")
                        if t.used_at:
                            st.write(f"**Checked in:** {t.used_at}")
                    with c2:
                        st.image(make_qr_png(t.token), caption="Token QR", width=180)
                        st.code(t.token, language=None)
                    if t.status == "PAID":
                        if st.button("Cancel ticket", key=f"cancel_{t.id}"):
                            t.status = "CANCELLED"
                            c = db.query(Commission).filter_by(ticket_id=t.id).first()
                            if c:
                                db.delete(c)
                            audit(db, f"{u['role']}:{u['username']}", "TICKET_CANCEL",
                                  f"ticket={t.reference}")
                            db.commit()
                            set_flash("success", "Ticket cancelled.")
                            st.rerun()

        # -------- Analytics --------
        with tabs[7]:
            st.markdown("#### Sales Analytics")
            st.caption("Paid and used tickets. Cancelled tickets excluded.")

            by_agent = sales_by_agent(db)
            by_type = sales_by_ticket_type(db)

            total_revenue = q2(sum((r["total"] for r in by_agent), Decimal("0")))
            total_tickets = sum(r["count"] for r in by_agent)
            top_agent = by_agent[0] if by_agent else None
            top_type = by_type[0] if by_type else None
            direct = next((r for r in by_agent if r["code"] == "DIRECT"), None)

            k1, k2, k3, k4 = st.columns(4)
            with k1: kpi("Total Revenue", f"${total_revenue}", f"{total_tickets} tickets")
            with k2: kpi("Top Agent",
                         top_agent["code"] if top_agent else "—",
                         f"${top_agent['total']}" if top_agent else "no sales")
            with k3: kpi("Top Ticket Type",
                         top_type["ticket_type"] if top_type else "—",
                         f"${top_type['total']}" if top_type else "no sales")
            with k4: kpi("Direct Sales",
                         f"${direct['total']}" if direct else "$0.00",
                         f"{direct['count']} tickets" if direct else "no sales")

            st.write("")
            c_left, c_right = st.columns(2)
            with c_left:
                card_open("Revenue by Agent")
                if by_agent:
                    st.plotly_chart(bar_chart(
                        labels=[r["code"] for r in by_agent],
                        values=[float(r["total"]) for r in by_agent],
                        title="Total revenue per agent",
                    ), use_container_width=True, config={"displayModeBar": False})
                else:
                    st.info("No sales data yet.")
                card_close()
            with c_right:
                card_open("Revenue by Ticket Type")
                if by_type:
                    st.plotly_chart(pie_chart(
                        labels=[r["ticket_type"] for r in by_type],
                        values=[float(r["total"]) for r in by_type],
                        title="Share of revenue by ticket type",
                    ), use_container_width=True, config={"displayModeBar": False})
                else:
                    st.info("No sales data yet.")
                card_close()

            c_left, c_right = st.columns(2)
            with c_left:
                card_open("Sales by Agent")
                if by_agent:
                    st.dataframe(pd.DataFrame([{
                        "Code": r["code"],
                        "Name": r["name"] or "Direct",
                        "Tickets": r["count"],
                        "Revenue": float(r["total"]),
                        "Commission": float(r["commission"]),
                    } for r in by_agent]), use_container_width=True, hide_index=True)
                else:
                    st.info("No data.")
                card_close()
            with c_right:
                card_open("Sales by Ticket Type")
                if by_type:
                    st.dataframe(pd.DataFrame([{
                        "Event": r["event"],
                        "Ticket Type": r["ticket_type"],
                        "Tickets": r["count"],
                        "Revenue": float(r["total"]),
                    } for r in by_type]), use_container_width=True, hide_index=True)
                else:
                    st.info("No data.")
                card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Direct Sale
# ---------------------------------------------------------------------------
def page_sell():
    u = require_role("admin", "manager")
    if not u:
        return

    inject_theme()
    hero("Direct Sale", "Issue a ticket and take payment", u)
    show_flash()

    db = get_session()
    try:
        types = db.query(TicketType).join(Event).filter(Event.active.is_(True)).all()
        agents = db.query(Agent).filter(Agent.active.is_(True)).all()

        if not types:
            st.info("No active ticket types. Create one in the dashboard first.")
            return

        col_form, col_preview = st.columns([1, 1])

        with col_form:
            card_open("New Ticket")
            with st.form("sell_form", clear_on_submit=True):
                tt = st.selectbox("Ticket type", options=types,
                                  format_func=lambda t: f"{t.event.name} — {t.name} — ${t.price}")
                buyer_name = st.text_input("Customer name")
                buyer_phone = st.text_input("Customer phone (optional)")
                payment = st.selectbox("Payment method", PAYMENT_METHODS)
                agent_opts = [None] + agents
                agent = st.selectbox(
                    "Selling agent (optional)", options=agent_opts,
                    format_func=lambda a: "Direct / Admin sale" if a is None else f"{a.code} — {a.name}")
                if st.form_submit_button("Confirm Payment & Issue Ticket",
                                         use_container_width=True):
                    t, err = create_sale(
                        db, actor=f"{u['role']}:{u['username']}",
                        ticket_type_id=tt.id, buyer_name=buyer_name,
                        buyer_phone=buyer_phone, payment_method=payment,
                        agent_id=agent.id if agent else None)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["last_ticket_id"] = t.id
                        set_flash("success", f"Ticket issued: {t.reference}")
                        st.rerun()
            card_close()

        with col_preview:
            card_open("Latest Ticket")
            last_id = st.session_state.get("last_ticket_id")
            if last_id:
                t = db.get(Ticket, last_id)
                if t:
                    st.markdown(f"#### {t.event.name}")
                    st.write(f"{t.event.venue} • {t.event.event_date}")
                    st.write(f"**{t.ticket_type.name}** — ${t.amount}")
                    st.write(f"Buyer: **{t.buyer_name}**")
                    st.markdown(status_badge(t.status), unsafe_allow_html=True)
                    st.image(make_qr_png(t.token), width=220)
                    st.caption("Token (share with buyer):")
                    st.code(t.token, language=None)
            else:
                st.info("Sold tickets will appear here.")
            card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Agent dashboard
# ---------------------------------------------------------------------------
def page_agent():
    u = require_role("agent")
    if not u:
        return

    inject_theme()
    show_flash()

    db = get_session()
    try:
        a = db.get(Agent, u["agent_id"])
        if not a:
            st.error("Agent not found.")
            return

        hero("Agent Dashboard", f"{a.code} — {a.name}", u)
        st.caption(f"Commission rate: **{a.commission_rate}%**")

        ledger = agent_ledger(db, a.id)
        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi("Commission Earned", f"${ledger['earned']}")
        with c2: kpi("Paid Out", f"${ledger['paid_payouts']}", accent="#34d399")
        with c3: kpi("Outstanding", f"${ledger['outstanding']}", accent="#fbbf24")
        with c4: kpi("Unpaid Commission", f"${ledger['unpaid_commissions']}")

        st.write("")

        # Sales summary — matches what admin sees for this agent
        tickets = db.query(Ticket).filter_by(agent_id=a.id).order_by(Ticket.id.desc()).all()
        gross = sum((to_decimal(t.amount) for t in tickets
                     if t.status in ("PAID", "USED")), Decimal("0"))
        agent_by_type = agent_sales_by_type(db, a.id)

        col_chart, col_summary = st.columns([2, 1])

        with col_chart:
            card_open("Your Sales by Ticket Type")
            if agent_by_type:
                st.plotly_chart(bar_chart(
                    labels=[r["ticket_type"] for r in agent_by_type],
                    values=[float(r["total"]) for r in agent_by_type],
                    title=f"Revenue breakdown for {a.code}",
                ), use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("No sales yet.")
            card_close()

        with col_summary:
            card_open("Your Summary")
            st.metric("Tickets Sold", sum(r["count"] for r in agent_by_type))
            st.metric("Total Sales", f"${q2(gross)}")
            st.metric("Commission Earned", f"${ledger['earned']}")
            st.metric("Wallet Balance", f"${ledger['outstanding']}")
            card_close()

        st.write("")
        col_sell, col_recent = st.columns([1, 1])

        with col_sell:
            card_open("Sell a Ticket")
            types = db.query(TicketType).join(Event).filter(Event.active.is_(True)).all()
            if not types:
                st.info("No active ticket types available.")
            else:
                with st.form("agent_sale", clear_on_submit=True):
                    tt = st.selectbox("Ticket type", options=types,
                                      format_func=lambda t: f"{t.event.name} — {t.name} — ${t.price}")
                    buyer_name = st.text_input("Customer name")
                    buyer_phone = st.text_input("Customer phone")
                    payment = st.selectbox("Payment method", PAYMENT_METHODS)
                    if st.form_submit_button("Confirm Payment & Generate Ticket",
                                             use_container_width=True):
                        t, err = create_sale(
                            db, actor=f"agent:{a.id}",
                            ticket_type_id=tt.id, buyer_name=buyer_name,
                            buyer_phone=buyer_phone, payment_method=payment,
                            agent_id=a.id)
                        if err:
                            st.error(err)
                        else:
                            st.session_state["last_ticket_id"] = t.id
                            set_flash("success", f"Ticket issued: {t.reference}")
                            st.rerun()
            card_close()

        with col_recent:
            card_open("Latest Ticket")
            last_id = st.session_state.get("last_ticket_id")
            if last_id:
                t = db.get(Ticket, last_id)
                if t and t.agent_id == a.id:
                    st.markdown(f"#### {t.event.name}")
                    st.write(f"**{t.ticket_type.name}** — ${t.amount}")
                    st.write(f"Buyer: **{t.buyer_name}**")
                    st.markdown(status_badge(t.status), unsafe_allow_html=True)
                    st.image(make_qr_png(t.token), width=200)
                    st.code(t.token, language=None)
            else:
                st.info("Sold tickets will appear here.")
            card_close()

        st.write("")
        card_open("Your Sales")
        if tickets:
            st.dataframe(pd.DataFrame([{
                "Reference": t.reference,
                "Buyer": t.buyer_name,
                "Amount": float(t.amount),
                "Status": t.status,
                "Created": t.created_at,
            } for t in tickets]), use_container_width=True, hide_index=True)
        else:
            st.info("No sales yet.")
        card_close()

        st.write("")
        card_open("Payout History")
        payouts = db.query(Payout).filter_by(agent_id=a.id).order_by(Payout.id.desc()).all()
        if payouts:
            st.dataframe(pd.DataFrame([{
                "Amount": float(p.amount),
                "Method": p.method,
                "Note": p.note,
                "When": p.created_at,
            } for p in payouts]), use_container_width=True, hide_index=True)
        else:
            st.info("No payouts recorded yet.")
        card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Gate scanner
# ---------------------------------------------------------------------------
def page_scan():
    u = require_role("admin", "manager", "gate")
    if not u:
        return

    inject_theme()
    hero("Gate Scanner", "Validate tickets at the entrance", u)
    show_flash()

    col_form, col_result = st.columns([1, 1])

    with col_form:
        card_open("Enter Ticket Token")
        st.caption("Paste the token from the buyer's QR code, or paste the last segment of their URL.")
        with st.form("validate_form", clear_on_submit=True):
            raw = st.text_input("Token or URL", placeholder="AbC123... or /public-ticket/AbC123")
            submitted = st.form_submit_button("Validate", use_container_width=True)
        card_close()

    with col_result:
        if submitted and raw.strip():
            token = raw.strip().rstrip("/").split("/")[-1]
            db = get_session()
            try:
                t = db.query(Ticket).filter_by(token=token).first()
                if not t:
                    st.markdown(
                        '<div class="vbz-card" style="border-color:#7f1d1d">'
                        '<h2 style="color:#f87171">INVALID</h2>'
                        '<p>No ticket matches this token.</p></div>',
                        unsafe_allow_html=True)
                elif t.status == "USED":
                    st.markdown(
                        f'<div class="vbz-card" style="border-color:#78350f">'
                        f'<h2 style="color:#fbbf24">ALREADY USED</h2>'
                        f'<p>{t.reference} — checked in {t.used_at}</p></div>',
                        unsafe_allow_html=True)
                    st.write(f"**Event:** {t.event.name}")
                    st.write(f"**Buyer:** {t.buyer_name}")
                elif t.status != "PAID":
                    st.markdown(
                        f'<div class="vbz-card" style="border-color:#7f1d1d">'
                        f'<h2 style="color:#f87171">{t.status}</h2>'
                        f'<p>Ticket is not valid for entry.</p></div>',
                        unsafe_allow_html=True)
                else:
                    t.status = "USED"
                    t.used_at = utcnow()
                    audit(db, f"{u['role']}:{u['username']}", "CHECKIN", f"ref={t.reference}")
                    db.commit()
                    st.markdown(
                        f'<div class="vbz-card" style="border-color:#065f46">'
                        f'<h2 style="color:#34d399">VALID — CHECKED IN</h2>'
                        f'<p>{t.reference}</p></div>',
                        unsafe_allow_html=True)
                    st.write(f"**Event:** {t.event.name}")
                    st.write(f"**Venue:** {t.event.venue}")
                    st.write(f"**Ticket:** {t.ticket_type.name}")
                    st.write(f"**Buyer:** {t.buyer_name}")
            finally:
                db.close()


# ---------------------------------------------------------------------------
# Page — Public ticket lookup
# ---------------------------------------------------------------------------
def page_public_ticket():
    inject_theme()
    hero("Ticket Lookup", "Enter the token from your ticket")

    token = st.text_input("Ticket token")
    if token:
        token = token.strip().rstrip("/").split("/")[-1]
        db = get_session()
        try:
            t = db.query(Ticket).filter_by(token=token).first()
            if not t:
                st.error("No ticket found for that token.")
            else:
                card_open()
                st.markdown(f"### {t.event.name}")
                st.write(f"{t.event.venue} • {t.event.event_date}")
                st.write(f"**Ticket type:** {t.ticket_type.name}")
                st.write(f"**Reference:** {t.reference}")
                st.write(f"**Buyer:** {t.buyer_name}")
                st.markdown(status_badge(t.status), unsafe_allow_html=True)
                st.image(make_qr_png(t.token), width=220)
                card_close()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Page — Reconciliation
# ---------------------------------------------------------------------------
def page_reconciliation():
    u = require_role("admin", "manager")
    if not u:
        return

    inject_theme()
    hero("Payment Reconciliation", "Sales by payment method", u)

    db = get_session()
    try:
        rows = db.query(Ticket).order_by(Ticket.id.desc()).all()
        methods: dict[str, Decimal] = {}
        for t in rows:
            if t.status == "CANCELLED":
                continue
            methods[t.payment_method] = methods.get(
                t.payment_method, Decimal("0")) + to_decimal(t.amount)
        methods = {k: q2(v) for k, v in methods.items()}

        if methods:
            cols = st.columns(len(methods))
            for i, (k, v) in enumerate(methods.items()):
                with cols[i]:
                    kpi(k, f"${v}")

        st.write("")
        card_open("All Tickets")
        if rows:
            st.dataframe(pd.DataFrame([{
                "Reference": t.reference,
                "Buyer": t.buyer_name,
                "Method": t.payment_method,
                "Amount": float(t.amount),
                "Status": t.status,
                "Created": t.created_at,
            } for t in rows]), use_container_width=True, hide_index=True)
        card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Audit
# ---------------------------------------------------------------------------
def page_audit():
    u = require_role("admin", "manager")
    if not u:
        return

    inject_theme()
    hero("Audit Log", "Every state-changing action", u)

    db = get_session()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(500).all()
        card_open("Latest 500 entries")
        if logs:
            st.dataframe(pd.DataFrame([{
                "Time": l.created_at,
                "Actor": l.actor,
                "Action": l.action,
                "Detail": l.detail,
            } for l in logs]), use_container_width=True, hide_index=True)
        else:
            st.info("No audit entries yet.")
        card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Export
# ---------------------------------------------------------------------------
def page_export():
    u = require_role("admin", "manager")
    if not u:
        return

    inject_theme()
    hero("Export Sales", "Download all ticket sales as CSV", u)

    db = get_session()
    try:
        rows = db.query(Ticket).order_by(Ticket.id).all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["reference", "event", "ticket_type", "buyer", "phone",
                    "payment_method", "amount", "status", "agent",
                    "created_at", "used_at"])
        for t in rows:
            w.writerow([
                t.reference,
                t.event.name if t.event else "",
                t.ticket_type.name if t.ticket_type else "",
                t.buyer_name, t.buyer_phone, t.payment_method, t.amount,
                t.status, t.agent.code if t.agent else "DIRECT",
                t.created_at, t.used_at or "",
            ])
        card_open()
        st.download_button("Download vbz_ticket_sales.csv",
                           data=buf.getvalue(),
                           file_name="vbz_ticket_sales.csv",
                           mime="text/csv",
                           use_container_width=True)
        st.caption(f"{len(rows)} tickets in export.")
        card_close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Page — Change password
# ---------------------------------------------------------------------------
def page_change_password():
    u = current_user()
    if not u:
        st.session_state.page = "login"
        st.rerun()
        return

    inject_theme()
    hero("Change Password", "Keep your account secure", u)
    show_flash()

    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        card_open()
        with st.form("change_pw"):
            current = st.text_input("Current password", type="password")
            new1 = st.text_input("New password (min 10 chars)", type="password")
            new2 = st.text_input("Confirm new password", type="password")
            submitted = st.form_submit_button("Update Password", use_container_width=True)
        card_close()

        if submitted:
            if new1 != new2:
                st.error("New passwords do not match.")
            elif len(new1) < 10:
                st.error("New password must be at least 10 characters.")
            else:
                db = get_session()
                try:
                    db_user = db.query(User).filter_by(username=u["username"]).first()
                    if not db_user or not verify_password(current, db_user.password_hash):
                        st.error("Current password is incorrect.")
                    else:
                        db_user.password_hash = hash_password(new1)
                        db_user.must_change_password = False
                        audit(db, f"{u['role']}:{u['username']}", "PASSWORD_CHANGE",
                              f"user={u['username']}")
                        db.commit()
                        st.session_state.user["must_change_password"] = False
                        set_flash("success", "Password updated.")
                        st.rerun()
                finally:
                    db.close()


# ---------------------------------------------------------------------------
# Router + sidebar
# ---------------------------------------------------------------------------
PAGES = {
    "login": ("Login", page_login),
    "dashboard": ("Dashboard", page_dashboard),
    "sell": ("Direct Sale", page_sell),
    "agent": ("Agent Dashboard", page_agent),
    "scan": ("Gate Scanner", page_scan),
    "public_ticket": ("Ticket Lookup", page_public_ticket),
    "reconciliation": ("Reconciliation", page_reconciliation),
    "audit": ("Audit Log", page_audit),
    "export": ("Export CSV", page_export),
    "change_password": ("Change Password", page_change_password),
}

NAV_BY_ROLE = {
    None: ["public_ticket"],
    "admin": ["dashboard", "sell", "scan", "reconciliation",
              "audit", "export", "change_password"],
    "manager": ["dashboard", "sell", "scan", "reconciliation",
                "audit", "export", "change_password"],
    "agent": ["agent", "change_password"],
    "gate": ["scan", "change_password"],
}


def sidebar():
    with st.sidebar:
        st.markdown(
            """
            <div class="vbz-brand">
                VENTS BY ZEUS
                <small>Ticketing Platform</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        u = current_user()
        if u:
            role_label = {
                "admin": "Administrator",
                "manager": "Manager",
                "agent": "Agent",
                "gate": "Gate Staff",
            }.get(u["role"], u["role"])
            st.markdown(
                f"""
                <div class="vbz-card-tight" style="text-align:center">
                    <div style="font-size:12px;color:#8aa8c8;text-transform:uppercase;letter-spacing:0.12em">
                        Signed in
                    </div>
                    <div style="font-weight:800;font-size:16px;margin-top:4px">
                        {u['username']}
                    </div>
                    <div style="color:#22d3ee;font-size:12px;letter-spacing:0.1em;text-transform:uppercase;margin-top:2px">
                        {role_label}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            pages = NAV_BY_ROLE.get(u["role"], [])
            labels = [PAGES[p][0] for p in pages]
            current_label = PAGES.get(st.session_state.page, (labels[0],))[0]
            default_idx = labels.index(current_label) if current_label in labels else 0
            choice = st.radio("Navigate", labels, index=default_idx,
                              label_visibility="collapsed")
            for key in pages:
                if PAGES[key][0] == choice:
                    st.session_state.page = key
                    break
            st.write("")
            if st.button("Log out", use_container_width=True):
                logout()
        else:
            st.caption("Not signed in.")
            if st.session_state.page != "public_ticket":
                if st.button("View a ticket", use_container_width=True):
                    st.session_state.page = "public_ticket"
                    st.rerun()


def main():
    sidebar()

    u = current_user()
    role = u["role"] if u else None
    allowed = NAV_BY_ROLE.get(role, [])
    if st.session_state.page not in allowed:
        st.session_state.page = {
            "admin": "dashboard",
            "manager": "dashboard",
            "agent": "agent",
            "gate": "scan",
        }.get(role, "login")

    key = st.session_state.page
    _, fn = PAGES.get(key, PAGES["login"])
    fn()


if __name__ == "__main__":
    main()