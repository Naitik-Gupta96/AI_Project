"""
HTTP and WebSocket API for the web UI.

    GET  /api/health
    GET  /api/catalog                         benchmarks, their tasks, available providers
    POST /api/sessions                        start a live session
    GET  /api/sessions                        live sessions, then stored ones
    GET  /api/sessions/{id}                   summary (live or stored)
    GET  /api/sessions/{id}/events?since=N    board events after seq N
    GET  /api/sessions/{id}/state?at=N        board state after the first N events
    POST /api/sessions/{id}/control           {"action": "pause" | "resume" | "step" | "stop"}
    WS   /ws/sessions/{id}                    backlog, then live board / cf / end messages

Every session's events are also written to ``<runs>/sessions/<id>/events.jsonl``,
so finished sessions can be reopened after a restart. If ``web/dist`` exists
it is served at ``/``.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_project.agents import build_team
from ai_project.benchmarks import registry
from ai_project.blackboard import Blackboard, JsonStore, StoreError
from ai_project.counterfactual import CounterfactualConfig
from ai_project.llm import prompts
from ai_project.llm.base import LLMProvider, LLMProviderError
from ai_project.llm.factory import make_provider
from ai_project.llm.providers.http import get_json
from ai_project.scheduler import SchedulerConfig
from ai_project.server.sessions import LiveSession, SessionManager
from ai_project.session import Session, SessionConfig


class StartSession(BaseModel):
    benchmark: str = "synthetic"
    task_id: str = "architecture"
    provider: str = "mock"
    cf_agents: list[str] = Field(default_factory=list)
    pace: float = Field(0.6, ge=0, le=10)
    max_messages: int = Field(12, ge=1, le=100)
    reject_after: int = Field(3, ge=1, le=50)
    max_concurrent_agents: int = Field(1, ge=1, le=8)
    apply: str = Field("both", pattern="^(prompt|weight|both)$")
    start_paused: bool = False


class Control(BaseModel):
    action: str = Field(pattern="^(pause|resume|step|stop)$")


def _model_providers() -> list[dict[str, Any]]:
    """Providers the machine can reach right now (mock is always available)."""
    found = [{"spec": "mock", "label": "Deterministic mock (rules, no model)"}]
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    try:
        for m in get_json(f"{host}/api/tags", timeout=1.5).get("models", []):
            found.append({"spec": f"ollama:{m['name']}", "label": f"Ollama · {m['name']}"})
    except LLMProviderError:
        pass
    vllm = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1").rstrip("/")
    try:
        for m in get_json(f"{vllm}/models", timeout=1.5).get("data", []):
            found.append({"spec": f"vllm:{m['id']}", "label": f"vLLM · {m['id']}"})
    except LLMProviderError:
        pass
    return found


def create_app(runs_dir: str | Path = "runs", catalog_size: int = 20,
               web_dir: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Blackboard PXP", version="0.2.0")
    runs = Path(runs_dir)
    store = JsonStore(runs / "sessions", fsync=False)
    manager = SessionManager()
    providers: dict[str, LLMProvider] = {}
    cache_path = runs / "cache" / "llm.sqlite"

    def provider_for(spec: str) -> LLMProvider:
        if spec not in providers:
            providers[spec] = make_provider(spec, cache=None if spec == "mock" else cache_path)
        return providers[spec]

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/catalog")
    def catalog() -> dict[str, Any]:
        benchmarks = []
        for name in registry.names():
            bench = registry.get_benchmark(name)
            try:
                tasks = bench.load(catalog_size, seed=0)
            except (FileNotFoundError, OSError) as exc:
                benchmarks.append({"name": name, "available": False, "reason": str(exc),
                                   "tasks": []})
                continue
            if name == "synthetic":
                tasks = [bench.get("architecture"), *tasks]
            benchmarks.append({
                "name": name, "available": True,
                "tasks": [{"task_id": t.task_id, "question": t.question,
                           "options": list(t.options), "domain": t.domain,
                           "roles": [r.role for r in prompts.roles(t.domain)]}
                          for t in tasks],
            })
        return {"benchmarks": benchmarks, "providers": _model_providers()}

    @app.post("/api/sessions", status_code=201)
    def start_session(body: StartSession) -> dict[str, Any]:
        try:
            bench = registry.get_benchmark(body.benchmark)
            task = bench.get(body.task_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        try:
            provider = provider_for(body.provider)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        team = build_team(task, provider)
        config = SessionConfig(
            scheduler=SchedulerConfig(max_messages=body.max_messages,
                                      max_concurrent_agents=body.max_concurrent_agents,
                                      pace=body.pace),
            reject_after=body.reject_after,
            counterfactual=CounterfactualConfig(apply=body.apply),
        )
        try:
            session = Session(task, team, body.cf_agents, config, store=store, benchmark=bench)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if body.start_paused:
            session.control.pause()
        live = LiveSession(session, meta={
            "benchmark": body.benchmark, "task_id": task.task_id, "question": task.question,
            "options": list(task.options), "provider": body.provider,
            "agents": [a.agent_id for a in team], "cf_agents": list(session.cf_agents),
            "config": config.to_dict(),
        }, id=session.board.session_id)
        manager.add(live).start()
        return live.summary()

    @app.get("/api/sessions")
    def list_sessions() -> list[dict[str, Any]]:
        live = [s.summary() for s in manager.all()]
        known = {s["id"] for s in live}
        stored = []
        for session_id in reversed(store.sessions()):
            if session_id in known:
                continue
            meta = store.read_meta(session_id)
            if meta:
                stored.append({"id": session_id, "state": "stored", "status": meta.get("status"),
                               "task_id": meta.get("task", {}).get("task_id"),
                               "question": meta.get("task", {}).get("question"),
                               "cf_agents": meta.get("cf_agents", [])})
        return live + stored

    def board_for(session_id: str) -> Blackboard:
        try:
            return manager.get(session_id).session.board
        except KeyError:
            pass
        try:
            return Blackboard.load(store, session_id)
        except StoreError as exc:
            raise HTTPException(404, f"Unknown session '{session_id}'") from exc

    @app.get("/api/sessions/{session_id}")
    def session_summary(session_id: str) -> dict[str, Any]:
        try:
            live = manager.get(session_id)
        except KeyError:
            board = board_for(session_id)
            return {"id": session_id, "state": "stored", **store.read_meta(session_id),
                    "version": board.version}
        return {**live.summary(), "result": live.result}

    @app.get("/api/sessions/{session_id}/events")
    def session_events(session_id: str, since: int = Query(0, ge=0)) -> list[dict[str, Any]]:
        return [e.to_dict() for e in board_for(session_id).get_events(since)]

    @app.get("/api/sessions/{session_id}/state")
    def session_state(session_id: str, at: int | None = Query(None, ge=0)) -> dict[str, Any]:
        board = board_for(session_id)
        try:
            state = board.get_state() if at is None else board.state_at(at)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return state.to_dict()

    @app.post("/api/sessions/{session_id}/control")
    def control(session_id: str, body: Control) -> dict[str, Any]:
        try:
            live = manager.get(session_id)
        except KeyError as exc:
            raise HTTPException(404, f"No live session '{session_id}'") from exc
        live.control(body.action)
        return live.summary()

    @app.websocket("/ws/sessions/{session_id}")
    async def stream(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        try:
            live = manager.get(session_id)
        except KeyError:
            try:
                board = Blackboard.load(store, session_id)
            except StoreError:
                await websocket.close(code=4404, reason="unknown session")
                return
            for event in board.get_events():
                await websocket.send_json({"type": "board", "event": event.to_dict()})
            await websocket.send_json({"type": "end", "result": None, "stored": True})
            await websocket.close()
            return
        sub, backlog = live.subscribe(asyncio.get_running_loop())
        try:
            for message in backlog:
                await websocket.send_json(message)
            while True:
                message = await sub.queue.get()
                await websocket.send_json(message)
        except WebSocketDisconnect:
            pass
        finally:
            live.unsubscribe(sub)

    web = Path(web_dir) if web_dir else Path(__file__).resolve().parents[3] / "web" / "dist"
    if web.is_dir():
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        root = web.resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (root / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
            return FileResponse(root / "index.html")

    return app
