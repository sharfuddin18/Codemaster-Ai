import json
import os
from typing import List, Dict, Any

class SessionMemory:
    """
    Tracks session history and long-term project goals across developer interactions.
    """
    def __init__(self, storage_path: str = ".codemaster_session.json"):
        self.storage_path = storage_path
        self.memory = self._load_memory()

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"project_goal": "", "history": []}

    def save_session(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.memory, f, indent=2)

    def set_goal(self, goal: str):
        self.memory["project_goal"] = goal
        self.save_session()

    def add_turn(self, user_prompt: str, ai_response: str):
        self.memory["history"].append({"user": user_prompt, "ai": ai_response})
        self.save_session()

    def get_summary(self) -> str:
        goal = self.memory.get("project_goal", "Not set")
        turns = len(self.memory.get("history", []))
        return f"Goal: {goal} | Conversational Turns: {turns}"
