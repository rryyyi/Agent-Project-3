"""Bounded orchestration: understand -> tools -> grounded response -> trace."""

import logging
import threading
import time
import uuid

from .cache import TTLCache
from .models import ChatRequest
from .tools import Tools
from .understanding import understand

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
        self, tools=None, llm=None, session_ttl=1800, max_sessions=256, clock=time.monotonic
    ):
        self.tools = tools or Tools()
        self.kb = self.tools.kb
        self.llm = llm
        self.sessions = TTLCache(capacity=max_sessions, ttl=session_ttl, clock=clock)
        # Bounded striped locks serialize a session's turns without an unbounded lock registry.
        self._locks = [threading.RLock() for _ in range(64)]

    def _lock(self, session_id):
        return self._locks[hash(session_id) % len(self._locks)]

    def delete_session(self, session_id: str) -> bool:
        with self._lock(session_id):
            return self.sessions.delete(session_id)

    def chat(self, message: str, session_id: str | None = None) -> dict:
        request = ChatRequest(message=message, session_id=session_id)
        session_id = request.session_id or uuid.uuid4().hex
        with self._lock(session_id):
            return self._turn(request.message.strip(), session_id)

    def _turn(self, message, session_id):
        started = time.perf_counter()
        trace = []
        context = self.sessions.get(session_id) or {}
        decision = understand(message, self.kb, context)
        trace.append(
            {
                "step": "understand",
                "intent": decision["intent"],
                "context_used": bool(context),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
        result = {
            "session_id": session_id,
            "request_id": uuid.uuid4().hex,
            "intent": decision["intent"],
            "rewritten_query": decision["query"],
            "status": "answered",
            "answer": "",
            "route": None,
            "evidence": [],
            "citations": [],
            "mode": "offline",
            "trace": trace,
            "knowledge_version": self.kb.version,
        }
        if "clarification" in decision:
            result.update(status="clarification", answer=decision["clarification"])
        elif decision["intent"] == "route":
            try:
                tool_started = time.perf_counter()
                response = self.tools.call(
                    "route_plan",
                    {key: decision[key] for key in ("origin", "destination", "objective")},
                )
                route = response["result"]
                trace.append(
                    {
                        "step": "tool",
                        "name": "route_plan",
                        "cache_hit": response["cache_hit"],
                        "elapsed_ms": round((time.perf_counter() - tool_started) * 1000, 3),
                    }
                )
                result.update(route=route, citations=route["citations"])
                result["answer"] = self._route_answer(route, message)
                context = {"origin": route["origin"], "destination": route["destination"]}
            except ValueError:
                result.update(status="unsupported", answer="示例網絡中沒有可用路線。")
        else:
            tool_started = time.perf_counter()
            response = self.tools.call("knowledge_search", {"query": decision["query"]})
            hits = response["result"]["evidence"]
            result["evidence"] = hits
            trace.append(
                {
                    "step": "tool",
                    "name": "knowledge_search",
                    "cache_hit": response["cache_hit"],
                    "evidence_count": len(hits),
                    "elapsed_ms": round((time.perf_counter() - tool_started) * 1000, 3),
                }
            )
            result["citations"] = [
                {key: hit[key] for key in ("document_id", "chunk_id", "source", "page")}
                for hit in hits
            ]
            if not hits:
                result.update(
                    status="unsupported",
                    answer=(
                        "未找到足夠證據 / No supporting evidence in the demo knowledge base. "
                        "請提供站點或查閱港鐵官方資料。"
                    ),
                )
            else:
                result["answer"] = "\n".join(
                    f"{hit['text']} [{hit['document_id']}, p.{hit['page']}]" for hit in hits
                )
                if self.llm:
                    try:
                        result["answer"] = self.llm.generate(message, hits)
                        result["mode"] = "llm-assisted"
                    except Exception:
                        # No endpoint, response, message or credentials are logged.
                        logger.warning("llm_synthesis_failed; using extractive evidence")
                        trace.append({"step": "fallback", "reason": "llm_unavailable"})
        # Persist only route slots; no raw user message or full response retained.
        self.sessions.set(session_id, context)
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        trace.append({"step": "answer", "status": result["status"], "elapsed_ms": elapsed})
        return result

    def _route_answer(self, route, message):
        english = message.isascii()
        if english:
            stations = " -> ".join(self.kb.stations[s].en for s in route["stations"])
            return (
                f"Demo route: {stations}. Transfers: {route['transfers']}; "
                f"synthetic duration: {route['minutes']:g} min. "
                "Not live travel advice. [SYNTHETIC-NETWORK-v1]"
            )
        return (
            f"示例路線：{' → '.join(route['station_names'])}。"
            f"換乘 {route['transfers']} 次，合成示例時間 {route['minutes']:g} 分鐘。"
            "不代表實際班次或行程時間。[SYNTHETIC-NETWORK-v1]"
        )
