import asyncio

import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.app.main import app


class FakeRetriever:
    def search(self, query, top_k=5, alpha=0.5, min_score=0.0):
        return [
            {
                "id": "1",
                "content": "File: src/example.py\ndef answer(): return 42",
                "hybrid_score": 0.9,
                "bm25_score": 0.8,
                "dense_score": 0.7,
            }
        ][:top_k]


def test_streamable_http_client_discovers_and_calls_tools(monkeypatch):
    monkeypatch.setattr("backend.app.mcp_server.get_hybrid_retriever", FakeRetriever)

    async def run_client():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as http_client:
                async with streamable_http_client(
                    "http://127.0.0.1:8000/mcp-protocol/",
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        response = await session.call_tool(
                            "retrieve_context",
                            {"query": "answer function", "top_k": 1},
                        )
                        return tools, response

    tools, response = asyncio.run(run_client())

    tool_names = {tool.name for tool in tools.tools}
    assert tool_names == {
        "retrieve_context",
        "generate_code",
        "fix_code",
        "review_code",
        "explain_code",
    }
    assert response.isError is not True
    assert response.structuredContent["count"] == 1
    assert response.structuredContent["results"][0]["file"] == "src/example.py"
