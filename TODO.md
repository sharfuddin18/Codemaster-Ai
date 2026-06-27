# TODO

- [ ] Replace `backend/app/main.py` with a valid, properly-indented FastAPI implementation while preserving:
  - endpoints: `/activate`, `/deactivate`, `/health`, `/models`, `/generate-code`, `/fix-code`
  - activation gating behavior
  - model selection logic and chosen-model override via request.model
  - Ollama host config and options
  - logging + CORS middleware
- [ ] Run a quick syntax/import check for the module.

