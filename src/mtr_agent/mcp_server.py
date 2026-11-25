"""Official MCP SDK stdio server; stdout is reserved for JSON-RPC transport."""

from .agent import Agent


def create_mcp(agent=None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError('Install "mtr-polyglot-agent[mcp]" for the MCP server') from exc
    service = agent or Agent()
    server = FastMCP("MTR Polyglot Agent")

    @server.tool()
    def route_plan(origin: str, destination: str, objective: str = "fastest") -> dict:
        """Plan a route in the synthetic teaching graph; not a live timetable."""
        return service.tools.call(
            "route_plan", {"origin": origin, "destination": destination, "objective": objective}
        )

    @server.tool()
    def knowledge_search(query: str, limit: int = 3) -> dict:
        """Retrieve synthetic FAQ evidence with document and page citations."""
        return service.tools.call("knowledge_search", {"query": query, "limit": limit})

    return server
