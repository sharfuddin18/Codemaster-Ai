import os

import requests
r = requests.post(
	f"{os.getenv('CODEMASTER_API_BASE_URL', 'http://localhost:8000').rstrip('/')}/activate",
	headers={"x-api-key": os.environ["CODEMASTER_API_KEY"]} if os.getenv("CODEMASTER_API_KEY") else {},
	timeout=10,
)
r.raise_for_status()
print(r.json())
