"""One validated tool registry shared by HTTP, Function Calling and MCP."""

from .cache import ToolCache
from .knowledge import Knowledge
from .models import RouteArguments, SearchArguments
from .retrieval import Retriever
from .routing import Router


class Tools:
    def __init__(self, knowledge=None, retriever=None, cache=None):
        self.kb = knowledge or Knowledge.load()
        self.router = Router(self.kb)
        self.retriever = retriever or Retriever(self.kb)
        self.cache = cache or ToolCache()
        # Model configuration is part of cache identity, avoiding cross-configuration L2 hits.
        self.version = self.kb.version + ":" + getattr(self.retriever, "profile", "offline-bm25-v1")

    @staticmethod
    def schemas() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": model.model_json_schema(),
                },
            }
            for name, description, model in [
                (
                    "route_plan",
                    "Plan a route on the synthetic metro graph, not a live timetable.",
                    RouteArguments,
                ),
                (
                    "knowledge_search",
                    "Search synthetic FAQ evidence with source and page.",
                    SearchArguments,
                ),
            ]
        ]

    def call(self, name: str, arguments: dict) -> dict:
        if name == "route_plan":
            parsed = RouteArguments.model_validate(arguments).model_dump()
            parsed["origin"] = self.kb.station_id(parsed["origin"])
            parsed["destination"] = self.kb.station_id(parsed["destination"])
        elif name == "knowledge_search":
            parsed = SearchArguments.model_validate(arguments).model_dump()
        else:
            raise ValueError(f"Unknown tool: {name}")
        key = ToolCache.key(self.version, name, parsed)
        cached = self.cache.get(key)
        if cached is not None:
            return {"result": cached, "cache_hit": True}
        if name == "route_plan":
            result = self.router.route(**parsed)
        else:
            result = {"evidence": self.retriever.search(**parsed)}
        self.cache.set(key, result)
        return {"result": result, "cache_hit": False}
