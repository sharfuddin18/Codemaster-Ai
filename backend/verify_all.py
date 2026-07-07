import os
from app.utils.vector_engine import VectorEngine
from database.db import db
import tenacity
import faiss

print("✅ Dependencies verified.")

# Test 1: Persistence
table = db.table('state')
print(f"✅ Persistence check: Current state {table.all()}")

# Test 2: RAG Engine
print("Testing RAG Engine initialization...")
engine = VectorEngine(directory="./app")
print("✅ RAG Engine initialized successfully.")

print("\n--- ALL SYSTEMS NOMINAL ---")
