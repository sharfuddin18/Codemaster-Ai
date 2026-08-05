"""MCP client example for Codemaster-AI.

Demonstrates simple calls to:
 - GET  /mcp/capabilities
 - POST /mcp/retrieve
 - POST /mcp/generate
 - POST /mcp/fix

Requires `requests` (used by the project's test matrix). Run with:

    python cli_tools/mcp_client_example.py

"""

import os
import json
import requests

BASE = os.environ.get("CODEMASTER_BASE", "http://localhost:8000/mcp")


def pretty(obj):
    try:
        return json.dumps(obj, indent=2)
    except Exception:
        return str(obj)


def get_capabilities():
    resp = requests.get(f"{BASE}/capabilities")
    print("/mcp/capabilities ->", resp.status_code)
    print(pretty(resp.json()))


def retrieve(query="database connection", top_k=3):
    payload = {"query": query, "top_k": top_k}
    resp = requests.post(f"{BASE}/retrieve", json=payload)
    print("/mcp/retrieve ->", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)


def generate(prompt="Create a helper to open a DB connection", language="python"):
    payload = {"prompt": prompt, "language": language}
    resp = requests.post(f"{BASE}/generate", json=payload)
    print("/mcp/generate ->", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)


def fix(file_code="def foo():\n    pass", instructions="return 42"):
    payload = {"file_code": file_code, "instructions": instructions}
    resp = requests.post(f"{BASE}/fix", json=payload)
    print("/mcp/fix ->", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    print("Using MCP base:", BASE)
    try:
        get_capabilities()
        retrieve()
        generate()
        fix()
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the Codemaster-AI server at", BASE)
        print("Make sure the backend is running: cd backend && uvicorn app.main:app --reload")
