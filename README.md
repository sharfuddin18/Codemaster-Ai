Codemaster-AI 🚀

I built Codemaster-AI because I wanted a coding assistant that didn't just feel like another wrapper around an API. I needed something that lived in my terminal, respected my privacy by running locally, and actually understood the context of my project.

Whether you're debugging a stubborn script or need to scaffold a new feature, this tool is designed to work with your flow, not interrupt it.

What’s Under the Hood?
I’ve structured this project with a modular, agent-based architecture. It’s not just a chat bot; it’s an engine designed to grow.

Agentic Power: I've separated logic into specialized agents—Code Reviewer, Explainer, and Generator—so it can handle complex tasks without getting confused.

Privacy-First: It runs entirely on your machine via Ollama. Your code never leaves your local environment.

CLI-Centric: I created native scripts (ai-generate, ai-fix) because I hate leaving my terminal to interact with an AI.

Context-Aware: It uses a local vector engine (all-MiniLM-L6-v2) to index your codebase, meaning it actually understands the files you're working on.

Tech Stack
I chose tools that are fast, robust, and easy to maintain:

Core: Python 3.12, FastAPI, Pydantic (V2)

AI/LLM: Ollama (for local inference)

Search: Sentence-Transformers for semantic code indexing

Automation: PowerShell 7 for the heavy lifting

How to Get Going
Make sure you've got Docker Desktop and Ollama running first.

Grab the code:

Bash
git clone https://github.com/sharfuddin18/codemaster-ai.git
cd Codemaster-Ai
Point it to your local LLM:

Bash
export LLM_PROVIDER=ollama
export OLLAMA_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434
Fire up the backend:

Bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
Using it
Once the server is running, you can test it with a quick curl request:

Generate a function:

Bash
curl -X POST http://localhost:8000/generate-code \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Write a Python function to calculate Fibonacci numbers"}'
Let's Connect
I’m actively building this out, and I’d love to see where it goes. If you’ve got ideas for new agents, better prompt handling, or just want to report a bug, open an issue or drop a PR.

Happy coding!

Author: Sharfuddin Ahmed (@sharfuddin18)

Licensed under MIT.
