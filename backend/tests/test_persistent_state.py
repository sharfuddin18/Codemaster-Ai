from fastapi.testclient import TestClient

from backend.app.main import app, set_app_state_from_db
from database.db import set_state, state_table


def test_activation_routes_persist_state_and_preserve_response_shape():
    state_table.truncate()
    client = TestClient(app)

    activate_response = client.post("/activate")
    assert activate_response.status_code == 200
    assert activate_response.json() == {"status": "activated", "message": "AI agent is active."}

    deactivate_response = client.post("/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json() == {"status": "deactivated", "message": "AI agent is inactive."}

    stored = state_table.get((lambda doc: doc.get("key") == "agent"))
    assert stored is not None
    assert stored.get("activated") is False


def test_app_startup_reads_saved_state():
    set_state(True)
    state_table.truncate()
    state_table.insert({"key": "agent", "activated": True})
    set_app_state_from_db()
    assert app.state.activated is True
