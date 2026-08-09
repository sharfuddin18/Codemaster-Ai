import os
import json
from typing import Any

import httpx
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    TextArea,
    Tree,
)

BACKEND_URL = os.getenv("CODEMASTER_AI_BACKEND", "http://localhost:8000")


class CodeOutputView(Static):
    """Displays generated or fixed code with syntax highlighting."""

    def update_code(self, code: str, language: str = "python"):
        if not code:
            self.update(Panel("No code output yet.", title="Code Output"))
            return

        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.update(Panel(syntax, title="Code Output"))


class ProvenanceView(Static):
    """Displays provenance metadata and retrieved source chunks."""

    def update_provenance(self, provenance: dict[str, Any] | None):
        if not provenance:
            self.update(Panel("No provenance metadata available.", title="Provenance"))
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Index", justify="center", width=6)
        table.add_column("File", min_width=20)
        table.add_column("Snippet", min_width=40, overflow="fold")

        for idx in provenance.get("cited_indices", []):
            source = provenance.get("sources", {}).get(str(idx), {})
            snippet = source.get("snippet", "").replace("\n", " ")
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            table.add_row(str(idx), source.get("file", "unknown"), snippet)

        status = provenance.get("verification_status", "unknown")
        summary = f"Verification: [bold green]{status}[/bold green] | Cited Indices: {provenance.get('cited_indices', [])}"
        self.update(Panel(table, title="Provenance", subtitle=summary))


class TerminalDashboard(App):
    """Interactive terminal dashboard for Codemaster-AI."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 3fr;
        grid-rows: 1fr 1fr;
    }

    #sidebar {
        row-span: 2;
        padding: 1 1;
        border: solid green;
        background: $panel;
    }

    #control-pane {
        border: solid blue;
        padding: 1 1;
        height: 100%;
    }

    #output-pane {
        border: solid yellow;
        padding: 1 1;
        height: 100%;
    }

    #provenance-pane {
        border: solid magenta;
        padding: 1 1;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="sidebar"):
            yield Static("📁 Codemaster-AI Dashboard", classes="bold")
            tree = Tree("Repository Explorer")
            tree.root.expand()
            backend_node = tree.root.add("backend")
            backend_node.add_leaf("app/main.py")
            backend_node.add_leaf("app/routes/generation.py")
            backend_node.add_leaf("app/models.py")
            backend_node.add_leaf("tui_app.py")
            yield tree

        with Vertical(id="control-pane"):
            yield Static("🧠 Enter a prompt to generate or fix code.", classes="bold")
            yield Input(placeholder="Write a code prompt...", id="prompt-input")
            yield Input(placeholder="Language (optional)", id="language-input")
            yield TextArea(placeholder="Paste code to fix here...", id="code-input", height=8)
            yield Input(placeholder="Fix instructions (optional)", id="instructions-input")
            with Horizontal():
                yield Button("Generate Code", id="generate-btn", variant="primary")
                yield Button("Fix Code", id="fix-btn", variant="warning")
            yield RichLog(id="activity-log", highlight=True, markup=True)

        with Vertical(id="output-pane"):
            yield Static("🔍 Generated / Fixed Code", classes="bold")
            yield CodeOutputView(id="code-view")

        with Vertical(id="provenance-pane"):
            yield Static("📚 Provenance & Retrieved Chunks", classes="bold")
            yield ProvenanceView(id="provenance-view")

        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#activity-log", RichLog).write(
            f"[bold cyan]Backend URL:[/bold cyan] {BACKEND_URL}\n"
            "[bold yellow]Press Generate Code or Fix Code to send a request.[/bold yellow]\n"
        )
        self.query_one("#provenance-view", ProvenanceView).update_provenance(None)
        self.query_one("#code-view", CodeOutputView).update_code("", language="text")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate-btn":
            await self.handle_generate()
        elif event.button.id == "fix-btn":
            await self.handle_fix()

    async def handle_generate(self) -> None:
        prompt_widget = self.query_one("#prompt-input", Input)
        lang_widget = self.query_one("#language-input", Input)
        log = self.query_one("#activity-log", RichLog)

        prompt = prompt_widget.value.strip()
        language = lang_widget.value.strip() or "python"
        if not prompt:
            log.write("[bold red]Provide a prompt before generating code.[/bold red]\n")
            return

        payload = {"prompt": prompt, "language": language}
        log.write(f"[bold green]→ Sending generate request for prompt:[/bold green] {prompt}\n")
        await self.send_request("/generate-code", payload, language)

    async def handle_fix(self) -> None:
        code_widget = self.query_one("#code-input", TextArea)
        instructions_widget = self.query_one("#instructions-input", Input)
        log = self.query_one("#activity-log", RichLog)

        file_code = code_widget.value.strip()
        instructions = instructions_widget.value.strip()
        if not file_code:
            log.write("[bold red]Paste code to fix before submitting.[/bold red]\n")
            return

        payload = {"file_code": file_code, "instructions": instructions}
        log.write("[bold green]→ Sending fix request for pasted code.[/bold green]\n")
        await self.send_request("/fix-code", payload, "python")

    async def send_request(self, path: str, payload: dict[str, Any], language: str) -> None:
        log = self.query_one("#activity-log", RichLog)
        code_view = self.query_one("#code-view", CodeOutputView)
        provenance_view = self.query_one("#provenance-view", ProvenanceView)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{BACKEND_URL}{path}", json=payload)
                response.raise_for_status()
                result = response.json()

            code = result.get("code", "")
            provenance = result.get("provenance")
            explanation = result.get("explanation", "")
            model_used = result.get("model_used", "unknown")
            elapsed_ms = result.get("elapsed_ms", 0)

            log.write(
                f"[bold blue]← Received response:[/bold blue] {explanation}\n"
                f"[dim]model={model_used} elapsed_ms={elapsed_ms}[/dim]\n"
            )
            code_view.update_code(code, language)
            provenance_view.update_provenance(provenance)

            if provenance and provenance.get("verification_status") != "verified":
                log.write("[bold yellow]⚠️ Response was not fully verified by provenance metadata.[/bold yellow]\n")
        except httpx.HTTPStatusError as exc:
            log.write(f"[bold red]HTTP error:[/bold red] {exc.response.status_code} {exc.response.text}\n")
            code_view.update_code("", language="text")
            provenance_view.update_provenance(None)
        except Exception as exc:
            log.write(f"[bold red]Request failed:[/bold red] {exc}\n")
            code_view.update_code("", language="text")
            provenance_view.update_provenance(None)


if __name__ == "__main__":
    app = TerminalDashboard()
    app.run()
