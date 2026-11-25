import asyncio

import pytest

pytest.importorskip('mcp')
from mtr_agent.mcp_server import create_mcp  # noqa: E402


def test_official_sdk_tool_discovery_and_execution():
    async def scenario():
        server = create_mcp()
        tools = await server.list_tools()
        assert {t.name for t in tools} == {'route_plan', 'knowledge_search'}
        response = await server.call_tool('route_plan', {
            'origin': 'Central', 'destination': 'Hung Hom'})
        assert response is not None
        assert 'HUH' in str(response)
    asyncio.run(scenario())
