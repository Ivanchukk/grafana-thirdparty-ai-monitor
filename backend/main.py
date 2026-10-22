import asyncio
import logging
import os
import secrets
import time
from pathlib import Path
from uuid import uuid4
import httpx
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from backend.agent import investigate, is_mock
from backend.grafana import Grafana

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
app = FastAPI(title="Grafana AI Operations Assistant", version="1.0.0")
sessions = {}
investigation_gate = asyncio.Semaphore(2)


def authenticated(x_ai_proxy_key: str = Header(default=""), x_grafana_user: str = Header(default="")):
    path = Path("/run/ai-secrets/proxy_key")
    expected = path.read_text().strip() if path.exists() else ""
    if not expected or not secrets.compare_digest(expected, x_ai_proxy_key) or not x_grafana_user:
        raise HTTPException(401, "Use the authenticated Grafana plugin proxy")
    return x_grafana_user


@app.get("/health")
def health():
    return {"status": "ok", "mode": "mock" if is_mock() else "live", "grafana_token_ready": Path("/run/ai-secrets/grafana_token").exists()}


@app.get("/dashboards")
async def dashboards(user=Depends(authenticated)):
    return await Grafana().dashboards()


class ContextRequest(BaseModel):
    dashboard_uid: str = Field(default="elasticsearch-demo", min_length=1, max_length=128)
    from_time: str = Field(default="now-30m", max_length=64)
    to_time: str = Field(default="now", max_length=64)
    variables: dict[str, str | list[str]] = Field(default_factory=dict, max_length=30)


class ChatRequest(ContextRequest):
    question: str = Field(default="Is there anything wrong with my Elasticsearch cluster?", min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=40)


@app.post("/context")
async def context(body: ContextRequest, user=Depends(authenticated)):
    try:
        return await Grafana().context(body.dashboard_uid, body.variables, body.from_time, body.to_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Grafana context retrieval failed; check backend logs and provisioning") from exc


@app.post("/chat")
async def chat(body: ChatRequest, user=Depends(authenticated)):
    now = time.monotonic()
    for key in list(sessions):
        if now-sessions[key]["updated"] > 1800 and not sessions[key]["lock"].locked():
            del sessions[key]
    session_id = body.session_id or str(uuid4())
    if session_id not in sessions:
        if body.session_id:
            raise HTTPException(404, "Chat expired. Start a new investigation.")
        if len(sessions) >= 100:
            raise HTTPException(429, "Chat capacity reached. Try again later.")
        sessions[session_id] = {"owner": user, "history": [], "updated": now, "turns": 0, "lock": asyncio.Lock()}
    session = sessions[session_id]
    if session["owner"] != user:
        raise HTTPException(404, "Chat not found")
    if session["lock"].locked() or investigation_gate.locked():
        raise HTTPException(429, "An investigation is already running. Try again shortly.")
    try:
        async with session["lock"], investigation_gate:
            grafana = Grafana()
            ctx = await grafana.context(body.dashboard_uid, body.variables, body.from_time, body.to_time)
            result = await investigate(grafana, ctx, body.question, session["history"])
            session["history"] = (session["history"] + [{"question": body.question, "answer": result["answer"][:6000], "dashboard_uid": body.dashboard_uid}])[-6:]
            session["updated"] = time.monotonic()
            session["turns"] += 1
            return {**result, "session_id": session_id, "turn": session["turns"]}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(504, "Investigation timed out; narrow the scope and try again") from exc
    except Exception as exc:
        logging.getLogger(__name__).exception("Investigation failed")
        raise HTTPException(502, "Investigation failed. Check Grafana connectivity, model tool support and backend logs.") from exc
