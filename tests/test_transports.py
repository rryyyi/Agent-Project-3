"""Cross-process smoke checks: real loopback HTTP and official stdio JSON-RPC."""

import asyncio
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest


def clean_env():
    env = os.environ.copy()
    for name in (
        "MTR_API_KEY",
        "MTR_DENSE_MODEL",
        "MTR_RERANK_MODEL",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_API_KEY",
        "REDIS_URL",
    ):
        env.pop(name, None)
    return env


def test_real_http_process():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "mtr_agent.cli", "serve", "--port", str(port)],
        env=clean_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False
        ) as client:
            deadline = time.monotonic() + 15
            while True:
                try:
                    assert client.get("/health").status_code == 200
                    break
                except httpx.ConnectError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        pytest.fail("HTTP process did not become ready")
                    time.sleep(0.05)
            response = client.post("/v1/chat", json={"message": "Central去紅磡"})
            assert response.status_code == 200
            assert response.json()["route"]["destination"] == "HUH"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_real_mcp_stdio_process():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def scenario():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "mtr_agent.cli", "mcp"], env=clean_env()
        )
        with open(os.devnull, "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    discovered = await session.list_tools()
                    assert {t.name for t in discovered.tools} == {"route_plan", "knowledge_search"}
                    result = await session.call_tool(
                        "route_plan", {"origin": "Central", "destination": "Hung Hom"}
                    )
                    assert result.isError is False
                    assert "HUH" in str(result.content)

    asyncio.run(asyncio.wait_for(scenario(), timeout=20))
