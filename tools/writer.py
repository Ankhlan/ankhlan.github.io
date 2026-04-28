"""writer.py — single-window writing TUI, v0.4

Three-pane terminal workspace:
  ┌──────────┬──────────────────────────┬──────────────┐
  │ TREE     │ EDITOR                   │ CHAT         │
  │ posts/   │ post.md                  │ ↳ ghost feed │
  │  ...     │                          │ ↳ your input │
  └──────────┴──────────────────────────┴──────────────┘

One command launches:
  - the editor (textual TUI)
  - the watcher + livereload server (as a child process)
  - the ghost agent (relay --spawn, child process, narrow context = current file)
  - a relay --watch reader so the ghost's replies appear in the chat pane

Usage:
    python tools/writer.py                              # open at posts/, start blank
    python tools/writer.py posts/<slug>/post.md         # open a specific file
"""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    TextArea,
)


REPO = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO / "posts"
RELAY = REPO / "relay.py"
WATCH = REPO / "tools" / "watch.py"
GHOST_FOCUS = REPO / "tools" / "ghost_focus.txt"

USER = "ANKHLAN"
GHOST = "ASSISTANT"
PREVIEW_PORT = 4321

AUTOSAVE_IDLE_SECONDS = 0.15
WORDCOUNT_REFRESH_SECONDS = 0.4


class StatusBar(Static):
    path = reactive("")
    saved_at = reactive(0.0)
    is_dirty = reactive(False)
    word_count = reactive(0)
    char_count = reactive(0)
    build_state = reactive("idle")
    ghost_state = reactive("offline")

    def render(self) -> str:
        if not self.path:
            file_state = "[dim]no file[/dim]"
        elif self.is_dirty:
            file_state = "[yellow]●[/yellow] modified"
        elif self.saved_at > 0:
            secs_ago = int(time.time() - self.saved_at)
            label = "just now" if secs_ago < 2 else f"{secs_ago}s ago"
            file_state = f"[green]✓[/green] saved {label}"
        else:
            file_state = "[dim]unsaved[/dim]"

        ghost_dot = {
            "offline": "[red]●[/red]",
            "starting": "[yellow]●[/yellow]",
            "online": "[green]●[/green]",
        }.get(self.ghost_state, "[dim]●[/dim]")

        return (
            f"[bold]{self.path or '—'}[/bold]   "
            f"{file_state}   "
            f"[dim]·[/dim]   build {self.build_state}   "
            f"[dim]·[/dim]   ghost {ghost_dot} {self.ghost_state}   "
            f"[dim]·[/dim]   [dim]{self.word_count}w {self.char_count}c[/dim]"
        )


class PostsTree(DirectoryTree):
    """File tree filtered to .md and .tex under posts/."""

    def filter_paths(self, paths):
        for p in paths:
            name = p.name
            if name.startswith(".") or name == "tex" or name == "build" or name == "scripts":
                continue
            if p.is_dir():
                yield p
            elif p.suffix in (".md", ".tex"):
                yield p


class Writer(App):
    """Three-pane writing workspace: tree | editor | chat."""

    CSS = """
    Screen { background: #faf8f3; color: #2b2a26; }
    Header { background: #2b2a26; color: #faf8f3; }
    #tree-pane {
        width: 24;
        background: #efece2;
        border-right: solid #d6d2c2;
    }
    PostsTree {
        background: #efece2;
        color: #4a4839;
        padding: 1 1;
    }
    #editor-pane { background: #faf8f3; }
    TextArea {
        background: #faf8f3;
        color: #2b2a26;
        border: none;
        padding: 1 2;
    }
    #chat-pane {
        width: 42;
        background: #f0ede0;
        border-left: solid #d6d2c2;
    }
    #chat-log {
        background: #f0ede0;
        color: #2b2a26;
        padding: 1 1;
    }
    #chat-input {
        background: #faf8f3;
        color: #2b2a26;
        border-top: solid #d6d2c2;
        padding: 0 1;
    }
    StatusBar {
        height: 1;
        background: #ebe7d8;
        color: #4a4839;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_now", "Save", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+e", "focus_editor", "Editor", show=False),
        Binding("ctrl+t", "focus_tree", "Tree", show=False),
        Binding("ctrl+l", "focus_chat", "Chat", show=False),
        Binding("ctrl+k", "ask_ghost", "Ask ghost", priority=True),
        Binding("ctrl+g", "toggle_ghost", "Ghost on/off", priority=True),
    ]

    def __init__(self, file_path: Path | None, ghost_on: bool = False) -> None:
        super().__init__()
        self.file_path: Path | None = file_path.resolve() if file_path else None
        self.ghost_on = ghost_on
        self._last_keystroke_at: float = 0.0
        self._last_saved_text: str = ""
        self._last_saved_mtime: float = 0.0

        # Managed child processes (started in on_mount, killed in on_unmount)
        self._watch_proc: subprocess.Popen | None = None
        self._ghost_proc: subprocess.Popen | None = None
        self._relay_watch_proc: asyncio.subprocess.Process | None = None
        self._relay_watch_reader_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Vertical(
                PostsTree(str(POSTS_DIR), id="tree"),
                id="tree-pane",
            ),
            Vertical(
                TextArea.code_editor(
                    "",
                    soft_wrap=True,
                    show_line_numbers=False,
                    id="editor",
                ),
                StatusBar(id="status"),
                id="editor-pane",
            ),
            Vertical(
                RichLog(highlight=False, markup=True, wrap=True, id="chat-log"),
                Input(placeholder="message ghost (Enter to send)", id="chat-input"),
                id="chat-pane",
            ),
        )
        yield Footer()

    # ----------------------------------------------------------------- mount

    async def on_mount(self) -> None:
        status = self.query_one("#status", StatusBar)
        if self.file_path:
            self._load_file_into_editor(self.file_path)
        else:
            status.path = ""
        self.title = "writer"
        self.sub_title = str(REPO)

        # Periodic ticks
        self.set_interval(0.05, self._autosave_tick)
        self.set_interval(0.1, self._external_change_tick)
        self.set_interval(WORDCOUNT_REFRESH_SECONDS, self._refresh_counts_tick)

        # Spawn helpers (non-blocking, asyncio).
        self._chat_log("[dim]starting watcher…[/dim]")
        await self._start_watcher()
        await self._start_relay_watch()
        if self.ghost_on:
            await self._start_ghost()
        else:
            self._chat_log("[dim]ghost: off (Ctrl+G to spawn — costs opus quota)[/dim]")

    async def on_unmount(self) -> None:
        for p in (self._watch_proc, self._ghost_proc):
            if p and p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
        if self._relay_watch_proc:
            try:
                self._relay_watch_proc.terminate()
            except Exception:
                pass
        if self._relay_watch_reader_task:
            self._relay_watch_reader_task.cancel()

    # ----------------------------------------------- editor + file management

    def _load_file_into_editor(self, path: Path) -> None:
        editor = self.query_one("#editor", TextArea)
        status = self.query_one("#status", StatusBar)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            editor.load_text(text)
            self._last_saved_text = text
            self._last_saved_mtime = path.stat().st_mtime
            status.saved_at = self._last_saved_mtime
        else:
            editor.load_text("")
            self._last_saved_text = ""
            self._last_saved_mtime = 0.0
            status.saved_at = 0.0
        self.file_path = path
        status.path = str(path.relative_to(REPO)) if str(path).startswith(str(REPO)) else str(path)
        status.is_dirty = False
        editor.language = "markdown" if path.suffix == ".md" else None
        self._refresh_counts(editor.text)

    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        new_path = Path(event.path).resolve()
        if self.file_path and new_path == self.file_path:
            return
        editor = self.query_one("#editor", TextArea)
        if editor.text != self._last_saved_text and self.file_path is not None:
            self._save(editor.text, self.file_path)
        self._load_file_into_editor(new_path)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._last_keystroke_at = time.monotonic()
        status = self.query_one("#status", StatusBar)
        status.is_dirty = (event.text_area.text != self._last_saved_text)

    def _refresh_counts_tick(self) -> None:
        self._refresh_counts(self.query_one("#editor", TextArea).text)

    def _refresh_counts(self, text: str) -> None:
        status = self.query_one("#status", StatusBar)
        status.word_count = len(text.split())
        status.char_count = len(text)

    def _autosave_tick(self) -> None:
        if self.file_path is None:
            return
        editor = self.query_one("#editor", TextArea)
        status = self.query_one("#status", StatusBar)
        if editor.text == self._last_saved_text:
            return
        if time.monotonic() - self._last_keystroke_at < AUTOSAVE_IDLE_SECONDS:
            return
        self._save(editor.text, self.file_path)
        status.is_dirty = False
        status.saved_at = time.time()

    def _external_change_tick(self) -> None:
        if self.file_path is None or not self.file_path.exists():
            return
        try:
            current_mtime = self.file_path.stat().st_mtime
        except OSError:
            return
        if current_mtime <= self._last_saved_mtime:
            return
        try:
            new_text = self.file_path.read_text(encoding="utf-8")
        except OSError:
            return
        editor = self.query_one("#editor", TextArea)
        if new_text == editor.text:
            self._last_saved_mtime = current_mtime
            return
        if editor.text != self._last_saved_text:
            # Local edits exist; don't clobber.
            return
        cursor = editor.cursor_location
        editor.load_text(new_text)
        try:
            editor.cursor_location = cursor
        except Exception:
            pass
        self._last_saved_text = new_text
        self._last_saved_mtime = current_mtime
        status = self.query_one("#status", StatusBar)
        status.saved_at = current_mtime
        status.is_dirty = False
        self._refresh_counts(new_text)

    def _save(self, text: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        self._last_saved_text = text
        self._last_saved_mtime = path.stat().st_mtime

    def action_save_now(self) -> None:
        if self.file_path is None:
            return
        editor = self.query_one("#editor", TextArea)
        status = self.query_one("#status", StatusBar)
        if editor.text != self._last_saved_text:
            self._save(editor.text, self.file_path)
            status.is_dirty = False
            status.saved_at = time.time()

    def action_focus_editor(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def action_focus_tree(self) -> None:
        self.query_one("#tree", PostsTree).focus()

    def action_focus_chat(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def action_ask_ghost(self) -> None:
        """Open a quick-dispatch popup with the editor selection prefilled as context."""
        editor = self.query_one("#editor", TextArea)
        sel = editor.selected_text or ""
        self.push_screen(AskGhost(selection=sel), self._handle_ask_ghost_result)

    def _handle_ask_ghost_result(self, result: str | None) -> None:
        if not result:
            return
        # Send via the same relay path as the chat input.
        self._chat_log(f"[bold yellow]you[/bold yellow]  {result}")
        asyncio.create_task(self._send_to_ghost(result))

    async def action_toggle_ghost(self) -> None:
        if self._ghost_proc and self._ghost_proc.poll() is None:
            try:
                self._ghost_proc.terminate()
            except Exception:
                pass
            self._ghost_proc = None
            status = self.query_one("#status", StatusBar)
            status.ghost_state = "offline"
            self._chat_log("[dim]ghost: stopped[/dim]")
            self.ghost_on = False
        else:
            self.ghost_on = True
            await self._start_ghost()

    # ------------------------------------------------------- chat / ghost wire

    def _chat_log(self, line: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(line)

    async def _start_watcher(self) -> None:
        """Run the livereload watcher as a child process."""
        if not WATCH.exists():
            self._chat_log("[red]watch.py not found; preview will not auto-reload[/red]")
            return
        try:
            self._watch_proc = subprocess.Popen(
                [sys.executable, str(WATCH), str(PREVIEW_PORT)],
                cwd=str(REPO),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            status = self.query_one("#status", StatusBar)
            status.build_state = "watching"
            self._chat_log(f"[dim]watcher: serving http://127.0.0.1:{PREVIEW_PORT}/[/dim]")
        except Exception as e:
            self._chat_log(f"[red]watcher failed to start: {e}[/red]")

    async def _start_ghost(self) -> None:
        """Spawn the article-scoped ghost agent via relay --spawn."""
        if not RELAY.exists():
            self._chat_log("[red]relay.py not found; ghost disabled[/red]")
            return
        focus = GHOST_FOCUS.read_text(encoding="utf-8") if GHOST_FOCUS.exists() else (
            "You are the writing assistant for the article currently open. "
            "Listen via relay_recv, respond via relay_send only. Loop forever."
        )
        try:
            self._ghost_proc = subprocess.Popen(
                [sys.executable, str(RELAY), "--spawn", GHOST, "--model", "opus", "--focus", focus],
                cwd=str(REPO),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            status = self.query_one("#status", StatusBar)
            status.ghost_state = "starting"
            self._chat_log(f"[dim]ghost {GHOST}: spawning (Claude Code subprocess; ~10–20s warmup)…[/dim]")
        except Exception as e:
            self._chat_log(f"[red]ghost failed to spawn: {e}[/red]")

    async def _start_relay_watch(self) -> None:
        """Tail the relay --watch JSONL stream so ghost replies appear in chat."""
        if not RELAY.exists():
            return
        try:
            self._relay_watch_proc = await asyncio.create_subprocess_exec(
                sys.executable, str(RELAY), USER, "--watch",
                cwd=str(REPO),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            self._relay_watch_reader_task = asyncio.create_task(self._read_relay_watch())
        except Exception as e:
            self._chat_log(f"[red]relay watch reader failed: {e}[/red]")

    async def _read_relay_watch(self) -> None:
        if self._relay_watch_proc is None or self._relay_watch_proc.stdout is None:
            return
        import json as _json
        status = self.query_one("#status", StatusBar)
        first_msg_seen = False
        try:
            async for raw in self._relay_watch_proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                # Try JSON; relay --watch emits JSONL.
                try:
                    obj = _json.loads(line)
                    sender = obj.get("from") or obj.get("sender") or "?"
                    body = obj.get("text") or obj.get("body") or obj.get("content") or line
                except Exception:
                    sender, body = "relay", line
                if not first_msg_seen and sender == GHOST:
                    status.ghost_state = "online"
                    first_msg_seen = True
                tag = f"[bold cyan]{sender}[/bold cyan]" if sender == GHOST else f"[bold]{sender}[/bold]"
                # Don't echo our own outgoing messages (we already log them on submit).
                if sender == USER:
                    continue
                self._chat_log(f"{tag}  {body}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._chat_log(f"[red]relay watch reader error: {e}[/red]")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = event.value.strip()
        if not msg:
            return
        event.input.value = ""
        self._chat_log(f"[bold yellow]you[/bold yellow]  {msg}")
        await self._send_to_ghost(msg)

    async def _send_to_ghost(self, msg: str) -> None:
        """Dispatch a message to the ghost via relay (fire and forget)."""
        if not RELAY.exists():
            self._chat_log("[red]relay.py not found[/red]")
            return
        try:
            await asyncio.create_subprocess_exec(
                sys.executable, str(RELAY), USER, msg, "--to", f"@{GHOST}",
                cwd=str(REPO),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except Exception as e:
            self._chat_log(f"[red]send failed: {e}[/red]")


class AskGhost(ModalScreen[str]):
    """Quick-dispatch popup: type an instruction, optional selection prefilled."""

    DEFAULT_CSS = """
    AskGhost {
        align: center middle;
    }
    #ask-box {
        width: 80;
        max-width: 90%;
        padding: 1 2;
        background: #2b2a26;
        color: #faf8f3;
        border: round #d6d2c2;
    }
    #ask-label {
        color: #d6d2c2;
        margin-bottom: 1;
    }
    #ask-selection {
        background: #1f1e1a;
        color: #c9c4ad;
        padding: 0 1;
        margin-bottom: 1;
        max-height: 6;
    }
    #ask-input {
        background: #1f1e1a;
        color: #faf8f3;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", priority=True),
    ]

    def __init__(self, selection: str = "") -> None:
        super().__init__()
        self.selection = selection.strip()

    def compose(self) -> ComposeResult:
        with Vertical(id="ask-box"):
            label = (
                f"Ask ghost about selection ({len(self.selection)} chars)"
                if self.selection else
                "Ask ghost"
            )
            yield Label(label, id="ask-label")
            if self.selection:
                preview = self.selection if len(self.selection) <= 240 else self.selection[:240] + "…"
                yield Static(preview, id="ask-selection")
            yield Input(placeholder="instruction… (Enter to send · Esc to cancel)", id="ask-input")

    def on_mount(self) -> None:
        self.query_one("#ask-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        instr = event.value.strip()
        if not instr:
            self.dismiss(None)
            return
        if self.selection:
            payload = f"{instr}\n\n--- selection ---\n{self.selection}"
        else:
            payload = instr
        self.dismiss(payload)

    def action_dismiss(self) -> None:
        self.dismiss(None)


def main(argv: list[str]) -> int:
    ghost_on = False
    file_args: list[str] = []
    for arg in argv:
        if arg == "--ghost":
            ghost_on = True
        else:
            file_args.append(arg)
    path: Path | None = None
    if file_args:
        path = Path(file_args[0])
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
    Writer(path, ghost_on=ghost_on).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
