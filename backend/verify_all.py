from backend.app.utils.vector_engine import CodeVectorEngine
from database.db import db

print("✅ Dependencies verified.")

# Test 1: Persistence
table = db.table('state')
print(f"✅ Persistence check: Current state {table.all()}")

# Test 2: RAG Engine
print("Testing RAG Engine initialization...")
engine = CodeVectorEngine()
print("✅ RAG Engine initialized successfully.")

print("\n--- ALL SYSTEMS NOMINAL ---")
