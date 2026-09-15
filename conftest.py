import sys
from pathlib import Path

# Automatically add workspace root and backend paths to sys.path
root_dir = Path(__file__).parent.absolute()
backend_dir = root_dir / "backend"
app_dir = backend_dir / "app"

for p in [str(root_dir), str(backend_dir), str(app_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)
