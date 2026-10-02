from __future__ import annotations

import os
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field
from dotenv import load_dotenv

from .services.analysis import docs, impact_analysis, build_flows
from .services.embeddings import Embedder
from .services.github import GitHubIngestor
from .services.llm import LLMService
from .services.retrieval import RetrievalEngine
from .services.vector_store import LocalVectorStore

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Codebase Intelligence API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedder = Embedder()
vector_store = LocalVectorStore()
retrieval = RetrievalEngine(embedder, vector_store)
llm = LLMService()
ingestor = GitHubIngestor()
CURRENT: dict[str, Any] = {}


class AnalyzeRequest(BaseModel):
    url: HttpUrl


class ChatRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)


class AuthRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class FileSummaryRequest(BaseModel):
    path: str


class ProfileUpdateRequest(BaseModel):
    name: str
    email: str


class ImpactRequest(BaseModel):
    target: str


DB_PATH = Path(__file__).resolve().parent / "workspace.db"

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db() -> None:
    with db_connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
        conn.commit()

def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000).hex()
    return digest, salt.hex()

def bearer_user(authorization: str | None) -> dict[str, Any] | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    with db_connect() as conn:
        row = conn.execute("SELECT u.id, u.name, u.email FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (token,)).fetchone()
    return dict(row) if row else None

ensure_db()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "codebase-intelligence", "repo_loaded": bool(CURRENT)}

@app.post("/api/auth/signup")
def signup(payload: AuthRequest):
    email = payload.email.strip().lower()
    name = payload.name.strip() or email.split("@")[0].title()
    if len(password := payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    digest, salt = hash_password(password)
    try:
        with db_connect() as conn:
            cur = conn.execute("INSERT INTO users(name,email,password_hash,salt,created_at) VALUES(?,?,?,?,?)", (name,email,digest,salt,datetime.now(timezone.utc).isoformat()))
            user_id = cur.lastrowid
            token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token,user_id,datetime.now(timezone.utc).isoformat()))
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    return {"token": token, "user": {"id": user_id, "name": name, "email": email}}

@app.post("/api/auth/login")
def login(payload: AuthRequest):
    email = payload.email.strip().lower()
    with db_connect() as conn:
        row = conn.execute("SELECT id,name,email,password_hash,salt FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        digest, _ = hash_password(payload.password, row["salt"])
        if not hmac.compare_digest(digest, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token,row["id"],datetime.now(timezone.utc).isoformat()))
        conn.commit()
    return {"token": token, "user": {"id": row["id"], "name": row["name"], "email": row["email"]}}

@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)):
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return {"user": user}

@app.put("/api/auth/profile")
def update_profile(payload: ProfileUpdateRequest, authorization: str | None = Header(default=None)):
    user = bearer_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in.")
    name = payload.name.strip() or user["name"]
    email = payload.email.strip().lower() or user["email"]
    try:
        with db_connect() as conn:
            conn.execute("UPDATE users SET name=?, email=? WHERE id=?", (name,email,user["id"]))
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="That email is already in use.") from exc
    return {"user": {"id": user["id"], "name": name, "email": email}}

@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        with db_connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
    return {"ok": True}


@app.post("/api/repos/analyze")
async def analyze_repo(payload: AnalyzeRequest):
    global CURRENT
    try:
        result = await ingestor.analyze(str(payload.url))
        vector_store.clear()
        indexed = retrieval.index(result["contents"])
        result["indexed_chunks"] = indexed
        result["docs"] = docs(result)
        result["flows"] = build_flows(result)
        CURRENT = result  # keep source contents server-side for chat / impact
        response = {k: v for k, v in result.items() if k != "contents"}
        return response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(payload: ChatRequest):
    if not CURRENT:
        raise HTTPException(status_code=409, detail="Analyze a repository first.")
    if len(payload.question.strip()) < 2:
        raise HTTPException(status_code=422, detail="Question is too short")
    hits = retrieval.retrieve(payload.question, limit=6)
    answer = await llm.answer(payload.question, hits, CURRENT.get("repo", {}).get("full_name", "this repository"), payload.history[-8:])
    return {**answer, "references": [{"path": h["path"], "chunk": h["chunk"], "score": h["score"]} for h in hits]}


@app.post("/api/files/summary")
async def file_summary(payload: FileSummaryRequest):
    if not CURRENT:
        raise HTTPException(status_code=409, detail="Analyze a repository first.")
    path = payload.path.strip()
    item = next((x for x in CURRENT.get("contents", []) if x.get("path") == path), None)
    if not item:
        raise HTTPException(status_code=404, detail="File not found in the current repository.")
    text = item.get("text", "")
    hits = [{"path": path, "chunk": 1, "score": 1.0, "text": text[:18000]}]
    result = await llm.file_summary(path, text, CURRENT.get("repo", {}).get("full_name", "repository"))
    return {**result, "path": path, "language": item.get("language"), "lines": item.get("lines", 0)}

@app.post("/api/impact")
def impact(payload: ImpactRequest):
    if not CURRENT:
        raise HTTPException(status_code=409, detail="Analyze a repository first.")
    return impact_analysis(CURRENT, payload.target)


@app.get("/api/repos/current")
def current_repo():
    if not CURRENT:
        raise HTTPException(status_code=404, detail="No repository analyzed yet.")
    data = {k: v for k, v in CURRENT.items() if k not in {"contents"}}
    return data
