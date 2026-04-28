"""desk.py — pure CLI writing console.

A REPL-style terminal program for the writing project. No panels, no TUI
chrome — just a `> ` prompt at the bottom and streaming output above,
shaped like Claude Code's own REPL.

What it does:
  • Manages the watcher (livereload server on :4321) as a child process
  • Pops a chromeless Chrome --app preview at the post URL
  • Manages the ghost agent (relay --spawn) — off by default to protect quota
  • Streams ghost replies into stdout above the prompt
  • Slash commands for management; bare text dispatches to the ghost

What it does not do:
  • Edit files. Use your own editor (RStudio / vim / VS Code / Notepad — any).
    The file watcher picks up your saves.

Usage:
  python tools/desk.py [posts/<slug>/post.md]
"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown


REPO = Path(__file__).resolve().parent.parent
POSTS_DIR = REPO / "posts"
RELAY = REPO / "relay.py"
WATCH = REPO / "tools" / "watch.py"
GHOST_FOCUS = REPO / "tools" / "ghost_focus.txt"

USER = "ANKHLAN"
GHOST = "ASSISTANT"
PREVIEW_PORT = 4321

console = Console(soft_wrap=True)


def out(msg: str = "", style: str = "") -> None:
    """Print above the prompt (patch_stdout keeps the input line clean)."""
    if style:
        console.print(msg, style=style)
    else:
        console.print(msg)


def find_browser() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def http_alive(url: str, timeout: float = 0.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


class Desk:
    def __init__(self, current_path: Path | None) -> None:
        self.current_path: Path | None = current_path
        self.watch_proc: subprocess.Popen | None = None
        self.ghost_proc: subprocess.Popen | None = None
        self.relay_watch_proc: asyncio.subprocess.Process | None = None
        self.relay_watch_task: asyncio.Task | None = None
        self.session: PromptSession = PromptSession(history=InMemoryHistory())
        self.preview_proc: subprocess.Popen | None = None
        self.ghost_on = False

    # ------------------------------------------------ subprocess management

    def _start_watcher(self) -> None:
        if not WATCH.exists():
            out("watch.py missing — preview won't auto-reload", style="red")
            return
        self.watch_proc = subprocess.Popen(
            [sys.executable, str(WATCH), str(PREVIEW_PORT)],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        # Wait briefly for the server to come up.
        for _ in range(40):
            if http_alive(f"http://127.0.0.1:{PREVIEW_PORT}/"):
                out(f"watcher: serving http://127.0.0.1:{PREVIEW_PORT}/", style="dim")
                return
            time.sleep(0.05)
        out("watcher: started but not yet responding on port", style="yellow")

    def _stop_watcher(self) -> None:
        if self.watch_proc and self.watch_proc.poll() is None:
            try:
                self.watch_proc.terminate()
            except Exception:
                pass

    def _start_preview(self) -> None:
        if self.current_path is None:
            return
        try:
            rel = self.current_path.parent.relative_to(REPO)
            url = f"http://127.0.0.1:{PREVIEW_PORT}/{rel.as_posix()}/"
        except ValueError:
            url = f"http://127.0.0.1:{PREVIEW_PORT}/"
        browser = find_browser()
        if browser is None:
            out(f"preview: open this in any browser → {url}", style="dim")
            return
        try:
            self.preview_proc = subprocess.Popen(
                [
                    str(browser),
                    f"--app={url}",
                    "--window-size=1100,1400",
                    f"--user-data-dir={os.environ.get('LOCALAPPDATA','')}\\rshtex-desk-profile",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            out(f"preview: {browser.name} --app at {url}", style="dim")
        except Exception as e:
            out(f"preview launch failed: {e}", style="red")

    async def _start_ghost(self) -> None:
        if self.ghost_proc and self.ghost_proc.poll() is None:
            out("ghost already running", style="yellow")
            return
        if not RELAY.exists():
            out("relay.py missing — ghost disabled", style="red")
            return
        focus = GHOST_FOCUS.read_text(encoding="utf-8") if GHOST_FOCUS.exists() else (
            "You are the writing assistant. Listen via relay_recv, respond via relay_send only."
        )
        self.ghost_proc = subprocess.Popen(
            [sys.executable, str(RELAY), "--spawn", GHOST, "--model", "opus", "--focus", focus],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        self.ghost_on = True
        out(f"ghost: spawning {GHOST} (Claude Code subprocess; ~10–20s warmup)…", style="dim")

    def _stop_ghost(self) -> None:
        if self.ghost_proc and self.ghost_proc.poll() is None:
            try:
                self.ghost_proc.terminate()
            except Exception:
                pass
        self.ghost_proc = None
        self.ghost_on = False
        out("ghost: stopped", style="dim")

    async def _start_relay_watch(self) -> None:
        if not RELAY.exists():
            return
        self.relay_watch_proc = await asyncio.create_subprocess_exec(
            sys.executable, str(RELAY), USER, "--watch",
            cwd=str(REPO),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.relay_watch_task = asyncio.create_task(self._read_relay_watch())

    async def _read_relay_watch(self) -> None:
        if self.relay_watch_proc is None or self.relay_watch_proc.stdout is None:
            return
        try:
            async for raw in self.relay_watch_proc.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    sender = obj.get("from") or obj.get("sender") or "?"
                    body = obj.get("text") or obj.get("body") or obj.get("content") or line
                except Exception:
                    sender, body = "relay", line
                if sender == USER:
                    continue  # don't echo our own outgoing
                style = "cyan" if sender == GHOST else "white"
                out(f"\n[{sender}]", style=f"bold {style}")
                # Render markdown if it looks like markdown; else plain.
                if any(t in body for t in ("```", "**", "- ", "##")):
                    console.print(Markdown(body))
                else:
                    console.print(body)
                out("")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            out(f"relay watch error: {e}", style="red")

    async def _send_to_ghost(self, msg: str) -> None:
        if not RELAY.exists():
            out("relay.py missing", style="red")
            return
        if not self.ghost_on:
            out("ghost is off — type /ghost on to start it (uses opus quota)", style="yellow")
            return
        await asyncio.create_subprocess_exec(
            sys.executable, str(RELAY), USER, msg, "--to", f"@{GHOST}",
            cwd=str(REPO),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    # ----------------------------------------------------------- commands

    async def cmd_help(self, _: str) -> None:
        out("commands:", style="bold")
        out("  /edit [path]      — open the current (or given) file in $EDITOR")
        out("  /new <slug>       — create posts/YYYY-MM-DD-<slug>/post.md and open it")
        out("  /open <path>      — set current article (used by /preview, /show)")
        out("  /show             — print current article to stdout")
        out("  /tree             — list posts/")
        out("  /preview          — pop chromeless Chrome at the current article")
        out("  /url              — print the preview URL")
        out("  /ghost on|off     — toggle the ghost agent (uses opus quota)")
        out("  /build            — run python tools/build.py")
        out("  /publish          — run build, then git commit + push")
        out("  /clear            — clear the screen")
        out("  /quit  or  /q     — exit")
        out("any other input is sent as a message to the ghost.")
        out("")
        out("$EDITOR is read from your environment; defaults to notepad on Windows.", style="dim")

    async def cmd_open(self, arg: str) -> None:
        if not arg:
            out("usage: /open <path>", style="yellow")
            return
        p = Path(arg.strip())
        if not p.is_absolute():
            p = (REPO / p).resolve()
        if not p.exists():
            out(f"not found: {p}", style="red")
            return
        self.current_path = p
        out(f"current: {p.relative_to(REPO)}", style="dim")

    async def cmd_show(self, _: str) -> None:
        if self.current_path is None:
            out("no current article — /open first", style="yellow")
            return
        try:
            text = self.current_path.read_text(encoding="utf-8")
        except Exception as e:
            out(f"read error: {e}", style="red")
            return
        out(f"--- {self.current_path.relative_to(REPO)} ---", style="dim")
        console.print(text)
        out("--- end ---", style="dim")

    async def cmd_tree(self, _: str) -> None:
        if not POSTS_DIR.exists():
            out("no posts/ directory", style="yellow")
            return
        for entry in sorted(POSTS_DIR.iterdir()):
            if entry.is_dir():
                main = entry / "post.md"
                marker = " *" if main.exists() else ""
                out(f"  {entry.name}{marker}")

    async def cmd_preview(self, _: str) -> None:
        self._start_preview()

    async def cmd_url(self, _: str) -> None:
        if self.current_path:
            try:
                rel = self.current_path.parent.relative_to(REPO)
                out(f"http://127.0.0.1:{PREVIEW_PORT}/{rel.as_posix()}/")
                return
            except ValueError:
                pass
        out(f"http://127.0.0.1:{PREVIEW_PORT}/")

    async def cmd_ghost(self, arg: str) -> None:
        a = arg.strip().lower()
        if a == "on":
            await self._start_ghost()
        elif a in ("off", "stop", "kill"):
            self._stop_ghost()
        else:
            state = "on" if (self.ghost_proc and self.ghost_proc.poll() is None) else "off"
            out(f"ghost: {state}    (use /ghost on or /ghost off)", style="dim")

    async def cmd_build(self, _: str) -> None:
        out("building…", style="dim")
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(REPO / "tools" / "build.py"),
            cwd=str(REPO),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        text = stdout.decode("utf-8", errors="replace").rstrip()
        if text:
            console.print(text)
        out(f"build {'ok' if proc.returncode == 0 else 'failed'}", style="green" if proc.returncode == 0 else "red")

    async def cmd_publish(self, _: str) -> None:
        out("publish: build + git commit + push", style="dim")
        # Build first.
        await self.cmd_build("")
        # Then git commit + push.
        msg = "Publish"
        if self.current_path:
            try:
                msg = f"Update {self.current_path.relative_to(REPO).as_posix()}"
            except ValueError:
                pass
        for cmd in (
            ["git", "add", "-A"],
            ["git", "commit", "-m", msg],
            ["git", "push", "origin", "main"],
        ):
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(REPO),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            text = stdout.decode("utf-8", errors="replace").rstrip()
            if text:
                console.print(text)
            if proc.returncode != 0 and cmd[1] != "commit":
                # commit may fail on no-op ("nothing to commit") and that's fine
                out(f"{cmd[0]} {cmd[1]} failed", style="red")
                return
        out("publish: ok — GitHub Pages deploys in ~30–90s", style="green")

    async def cmd_clear(self, _: str) -> None:
        os.system("cls" if os.name == "nt" else "clear")

    def _resolve_editor(self) -> list[str]:
        """Return argv prefix for the user's editor. Respects $EDITOR / $VISUAL."""
        env = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if env:
            try:
                return shlex.split(env, posix=(os.name != "nt"))
            except Exception:
                return [env]
        # Sensible defaults: try VS Code (with --wait so we block until close), then Windows notepad, else vi.
        for guess in ("code --wait", "nvim", "vim", "nano"):
            exe = guess.split()[0]
            try:
                if subprocess.run(["where" if os.name == "nt" else "which", exe], capture_output=True).returncode == 0:
                    return guess.split()
            except Exception:
                continue
        return ["notepad"] if os.name == "nt" else ["vi"]

    async def cmd_edit(self, arg: str) -> None:
        if arg.strip():
            p = Path(arg.strip())
            if not p.is_absolute():
                p = (REPO / p).resolve()
            path = p
        else:
            if self.current_path is None:
                out("no current article — /open <path> first, or /edit <path>", style="yellow")
                return
            path = self.current_path
        path.parent.mkdir(parents=True, exist_ok=True)
        editor_argv = self._resolve_editor()
        out(f"editing {path.relative_to(REPO) if str(path).startswith(str(REPO)) else path} in {editor_argv[0]}…", style="dim")
        try:
            proc = await asyncio.create_subprocess_exec(
                *editor_argv, str(path),
                cwd=str(REPO),
            )
            await proc.wait()
            out("editor closed", style="dim")
            self.current_path = path
        except FileNotFoundError:
            out(f"editor not found: {editor_argv[0]} — set $EDITOR to your editor's command", style="red")
        except Exception as e:
            out(f"editor error: {e}", style="red")

    async def cmd_new(self, arg: str) -> None:
        slug = arg.strip()
        if not slug:
            out("usage: /new <slug>    (creates posts/YYYY-MM-DD-<slug>/post.md)", style="yellow")
            return
        # Sanitize slug: lower, replace spaces with hyphens.
        slug = "-".join(slug.lower().split())
        date = time.strftime("%Y-%m-%d")
        folder = POSTS_DIR / f"{date}-{slug}"
        post = folder / "post.md"
        if post.exists():
            out(f"already exists: {post.relative_to(REPO)} — opening", style="yellow")
        else:
            folder.mkdir(parents=True, exist_ok=True)
            template = (
                f"---\n"
                f"title: \"{slug.replace('-', ' ').title()}\"\n"
                f"date: {date}\n"
                f"tags: []\n"
                f"summary: \"\"\n"
                f"---\n"
                f"\n"
                f"Draft.\n"
            )
            post.write_text(template, encoding="utf-8")
            out(f"created {post.relative_to(REPO)}", style="green")
        self.current_path = post
        await self.cmd_edit("")

    # ------------------------------------------------------------ main loop

    async def run(self) -> None:
        out(f"desk · writing console for {REPO.name}", style="bold")
        out(f"current: {self.current_path.relative_to(REPO) if self.current_path else '(none)'}", style="dim")
        out("type /help for commands · bare text → ghost · Ctrl+D to quit", style="dim")
        out("")

        self._start_watcher()
        await self._start_relay_watch()
        if self.current_path:
            self._start_preview()

        commands = {
            "help": self.cmd_help, "h": self.cmd_help, "?": self.cmd_help,
            "edit": self.cmd_edit, "e": self.cmd_edit,
            "new": self.cmd_new, "n": self.cmd_new,
            "open": self.cmd_open, "o": self.cmd_open,
            "show": self.cmd_show,
            "tree": self.cmd_tree, "ls": self.cmd_tree,
            "preview": self.cmd_preview,
            "url": self.cmd_url,
            "ghost": self.cmd_ghost, "g": self.cmd_ghost,
            "build": self.cmd_build, "b": self.cmd_build,
            "publish": self.cmd_publish, "p": self.cmd_publish,
            "clear": self.cmd_clear, "cls": self.cmd_clear,
        }

        try:
            while True:
                with patch_stdout():
                    line = await self.session.prompt_async("> ")
                line = (line or "").strip()
                if not line:
                    continue
                if line in ("/quit", "/q", "/exit", ":q", ":quit", "exit", "quit"):
                    break
                if line.startswith("/") or line.startswith(":"):
                    parts = line.lstrip("/:").split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1] if len(parts) > 1 else ""
                    handler = commands.get(cmd)
                    if handler is None:
                        out(f"unknown command: /{cmd}    (try /help)", style="yellow")
                    else:
                        await handler(arg)
                else:
                    await self._send_to_ghost(line)
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        out("\nshutting down…", style="dim")
        self._stop_watcher()
        self._stop_ghost()
        if self.relay_watch_task:
            self.relay_watch_task.cancel()
        if self.relay_watch_proc:
            try:
                self.relay_watch_proc.terminate()
            except Exception:
                pass


def main(argv: list[str]) -> int:
    path: Path | None = None
    if argv:
        candidate = Path(argv[0])
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        if candidate.exists():
            path = candidate
        else:
            print(f"warning: {candidate} not found, starting with no current article", file=sys.stderr)
    asyncio.run(Desk(path).run())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
