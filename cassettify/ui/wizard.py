from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Label
from textual.containers import Container
from textual import on


@dataclass
class WizardResult:
    client_id: str
    client_secret: str
    output_dir: str


class WelcomeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Welcome to Cassettify[/bold]", classes="title"),
            Static(
                "Let's connect your Spotify account.\nThis takes about 2 minutes.",
                classes="subtitle",
            ),
            Button("Let's go →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def next(self) -> None:
        self.app.push_screen(InstructionsScreen())


class InstructionsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Step 1: Create a free Spotify app[/bold]\n"),
            Static(
                "1. Go to developer.spotify.com/dashboard\n"
                "2. Log in and click [bold]Create app[/bold]\n"
                "3. Set Redirect URI to: [bold]http://localhost:8888/callback[/bold]\n"
                "4. Copy your [bold]Client ID[/bold] and [bold]Client Secret[/bold]"
            ),
            Button("I've got my credentials →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def next(self) -> None:
        self.app.push_screen(CredentialsScreen())


class CredentialsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Paste your Spotify credentials[/bold]\n"),
            Label("Client ID"),
            Input(placeholder="Paste here...", id="client_id"),
            Label("Client Secret"),
            Input(placeholder="Paste here...", password=True, id="client_secret"),
            Static("", id="error", classes="error"),
            Button("Connect →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def submit(self) -> None:
        client_id = self.query_one("#client_id", Input).value.strip()
        client_secret = self.query_one("#client_secret", Input).value.strip()
        if not client_id or not client_secret:
            self.query_one("#error", Static).update("Both fields are required.")
            return
        self.app.wizard_client_id = client_id
        self.app.wizard_client_secret = client_secret
        self.app.push_screen(OutputDirScreen())


class OutputDirScreen(Screen):
    _default = str(Path.home() / "Music" / "Cassettify")

    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold]Where should songs be saved?[/bold]\n"),
            Input(value=self._default, id="output_dir"),
            Button("Finish setup →", id="next", variant="primary"),
            classes="card",
        )

    @on(Button.Pressed, "#next")
    def submit(self) -> None:
        output_dir = self.query_one("#output_dir", Input).value.strip() or self._default
        self.app.exit(WizardResult(
            client_id=self.app.wizard_client_id,
            client_secret=self.app.wizard_client_secret,
            output_dir=output_dir,
        ))


class WizardApp(App):
    CSS = """
    Screen { align: center middle; }
    .card {
        width: 64;
        height: auto;
        border: solid $primary;
        padding: 2 4;
    }
    .title { text-style: bold; margin-bottom: 1; }
    .subtitle { color: $text-muted; margin-bottom: 2; }
    .error { color: red; height: 1; margin-top: 1; }
    Button { margin-top: 2; }
    Input { margin-top: 1; margin-bottom: 1; }
    """

    wizard_client_id: str = ""
    wizard_client_secret: str = ""

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())
