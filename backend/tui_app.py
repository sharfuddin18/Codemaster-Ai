import difflib
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree, RichLog, Button
from textual.containers import Horizontal, Vertical, Container
from rich.syntax import Syntax

from backend.model_orchestrator import ModelOrchestrator

class CodeDiffView(Static):
    """
    Renders side-by-side or inline code diff previews.
    """
    def update_diff(self, old_code: str, new_code: str):
        diff = list(difflib.unified_diff(
            old_code.splitlines(keepends=True),
            new_code.splitlines(keepends=True),
            fromfile="Original (main)",
            tofile="Proposed (Sam)"
        ))
        diff_text = "".join(diff) if diff else "No changes detected."
        syntax = Syntax(diff_text, "diff", theme="github-dark", line_numbers=True)
        self.update(syntax)

class TerminalDashboard(App):
    """
    Interactive Phase 5 Terminal UI (TUI) Dashboard.
    """
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 3fr;
        grid-rows: 1fr 1fr;
    }
    #sidebar {
        row-span: 2;
        background: $panel;
        border: solid green;
    }
    #stream-pane {
        border: solid blue;
        height: 100%;
    }
    #diff-pane {
        border: solid yellow;
        height: 100%;
    }
    """

    def __init__(self):
        super().__init__()
        self.orchestrator = ModelOrchestrator()
        self.original_code = "def process():\n    pass\n"
        self.generated_code = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="sidebar"):
            yield Static("📁 Project Context Tree")
            tree = Tree("Codemaster-Ai")
            tree.root.expand()
            backend_node = tree.root.add("backend")
            backend_node.add_leaf("model_orchestrator.py")
            backend_node.add_leaf("tui_app.py")
            backend_node.add_leaf("requirements.txt")
            yield tree

        with Vertical(id="stream-pane"):
            yield Static("⚡ Live Model Token Stream")
            yield RichLog(id="token-stream", highlight=True, markup=True)

        with Vertical(id="diff-pane"):
            yield Static("🔍 Interactive Code Diff Preview")
            yield CodeDiffView(id="diff-view")
            with Horizontal():
                yield Button("Accept Changes", id="accept-btn", variant="success")
                yield Button("Reject Changes", id="reject-btn", variant="error")

        yield Footer()

    async def on_mount(self) -> None:
        """
        Triggers stream automatically when TUI launches.
        """
        stream_log = self.query_one("#token-stream", RichLog)
        diff_view = self.query_one("#diff-view", CodeDiffView)

        stream_log.write("[bold cyan]Initializing Model Stream...[/bold cyan]\n")
        
        async for chunk in self.orchestrator.stream_completion(
            prompt="Refactor process function", task_type="refactor"
        ):
            model_used = chunk["model"]
            token = chunk["token"]
            self.generated_code += token
            stream_log.write(f"[dim gray][{model_used}][/dim gray] {token}")

        diff_view.update_diff(self.original_code, self.generated_code)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        stream_log = self.query_one("#token-stream", RichLog)
        if event.button.id == "accept-btn":
            stream_log.write("\n[bold green]✅ Changes Accepted and Merged into Workspace![/bold green]")
        elif event.button.id == "reject-btn":
            stream_log.write("\n[bold red]❌ Changes Rejected.[/bold red]")

if __name__ == "__main__":
    app = TerminalDashboard()
    app.run()
