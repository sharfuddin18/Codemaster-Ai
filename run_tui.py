import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.tui_app import TerminalDashboard

if __name__ == "__main__":
    app = TerminalDashboard()
    app.run()
