from pathlib import Path

from tinydb import Query, TinyDB

DB_DIR = Path(__file__).resolve().parent.parent / "database"
DB_PATH = DB_DIR / "state.json"

DB_DIR.mkdir(parents=True, exist_ok=True)

db = TinyDB(DB_PATH)
state_table = db.table("state")
StateQuery = Query()


def get_state() -> dict:
    """Return the persisted state document, creating a default one if needed."""
    record = state_table.get(StateQuery.key == "agent")
    if record is None:
        state_table.insert({"key": "agent", "activated": False})
        return {"activated": False}
    return {"activated": bool(record.get("activated", False))}


def set_state(activated: bool) -> dict:
    """Persist the activation state and return the current state."""
    state_table.upsert({"key": "agent", "activated": bool(activated)}, StateQuery.key == "agent")
    return get_state()


def is_activated() -> bool:
    """Return whether the agent is currently marked as active."""
    return bool(get_state().get("activated", False))
