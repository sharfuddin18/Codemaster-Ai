import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.provider_manager import ProviderManager
from backend.session_memory import SessionMemory

def main():
    print("🌐 Verifying Phase 6 Ecosystem & Tooling Manager...\n")

    # Verify Multi-Provider
    pm = ProviderManager("ollama")
    print(f"Active Provider: {pm.active_provider.upper()} -> Endpoint: {pm.get_endpoint()}")
    pm.set_provider("lm_studio")
    print(f"Switched Provider: {pm.active_provider.upper()} -> Endpoint: {pm.get_endpoint()}")

    # Verify Session Memory
    memory = SessionMemory()
    memory.set_goal("Refactor Codemaster-AI core pipeline for Phase 6")
    memory.add_turn("How is context retrieved?", "Context is retrieved using hybrid BM25 + Vector Search.")
    
    print("\nSession Memory State:")
    print(f"  {memory.get_summary()}")
    print("\n✅ Phase 6 Ecosystem components initialized successfully!")

if __name__ == "__main__":
    main()
