'''
Query Routing & Hybrid Intent Classification for CodeMaster AI
'''
from typing import Literal

DOMAIN_KEYWORDS = [
    "editnova", "codemaster", "internal", "config", "architecture", 
    "strategy", "database", "api_key", "pipeline", "custom_module"
]

def classify_query_intent(query: str) -> Literal["LOCAL_RAG", "GENERAL_CODING"]:
    lowered_query = query.lower()
    if any(keyword in lowered_query for keyword in DOMAIN_KEYWORDS):
        return "LOCAL_RAG"
    return "GENERAL_CODING"

if __name__ == "__main__":
    test_query = "How do I fix a deadlock in token bucket rate limiter?"
    print(f"Test Query Intent: {classify_query_intent(test_query)}")
