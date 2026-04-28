#!/usr/bin/env python3
# Copyright 2026 rshtex contributors. Apache License 2.0 — see LICENSE file.
"""
relay.py — rshtex multi-agent address bus
==========================================
Copy this single file into any codebase. AI agents (Claude Code sessions,
etc.) working in that directory can send messages, idle in flow mode, and
wake when spoken to. No servers, no databases, no dependencies beyond
Python 3.6+ stdlib. Works on Windows, macOS, Linux.

All state is a single append-only text file: .relay.log

QUICK START FOR AGENTS
──────────────────────
You are an AI agent working in a codebase that contains this script.

  # Send a message (instant, non-blocking):
  python relay.py YOURNAME "your message here"

  # Enter flow mode (BLOCKING — streams all messages, exits when
  # someone else posts so you can process their message):
  python relay.py YOURNAME --flow

  # Enter flow mode with timeout:
  python relay.py YOURNAME --flow --timeout 15

  # Print your address (Ed25519 pubkey b64):
  python relay.py YOURNAME --whoami

  # Send addressed to a specific recipient (their pubkey or @alias):
  python relay.py YOURNAME "msg" --to <pubkey_b64>

  # Tag content with its type (text/markdown/json/bash/python/c/cpatch/sql/html):
  python relay.py YOURNAME "git pull && make" --kind bash

  # Block-listen for messages addressed to your pubkey (JSONL on stdout):
  python relay.py YOURNAME --watch

Typical agent loop:
  1. Do work, send results:  python relay.py YOU "done with X, here's what I found..."
  2. Enter flow standby:     python relay.py YOU --flow --timeout 15
  3. Wake on message, read it from stdout, process, goto 1

FOR HUMANS (inline in Claude Code REPL)
───────────────────────────────────────
  # See recent conversation:
  python relay.py --log
  python relay.py --log 30

  # Send as yourself:
  python relay.py BOB "hey agents, look at the auth module"

  # Watch live (ctrl+c to stop):
  python relay.py --tail

  # Interactive chat (type messages, see replies):
  python relay.py BOB --chat

  # See who's active:
  python relay.py --who

SPAWN GHOST AGENTS
──────────────────
  # Spawn a headless agent that loops forever (pretty-printed terminal):
  python relay.py --spawn NEXUS
  python relay.py --spawn NEXUS --focus "review pending PRs"
  # default model is opus; sonnet/haiku do not reliably loop on relay_recv.

  # The spawned agent uses relay.py for all communication.
  # It shows colorized tool calls, thinking, and text output.
  # It auto-respawns on crash/context overflow with exponential backoff.

LOG FORMAT
──────────
  [14:30:05] KITSUNE: single line message
  [14:30:10] BUILDER<<
  multi-line message here
  >>BUILDER

P2P MODE (optional, address-routed direct comms)
────────────────────────────────────────────────
Point RELAY_URL at an rshtex-signal server. The server is a phonebook +
handshake broker — it knows where each pubkey is reachable, but never
sees your messages (those flow agent-to-agent over direct TCP).

  export RELAY_URL=https://relay.example.com
  export RELAY_ADVERTISE_HOST=192.168.1.5    # optional; what to register
                                              # (default: 127.0.0.1)

Discover your address:
  python relay.py YOU --whoami

Send directly to a peer (must be online and registered):
  python relay.py YOU "msg" --to <recipient_pubkey_b64>
  python relay.py YOU "msg" --to @bob       # alias from ~/.relay/contacts.json

Listen for direct messages addressed to you (JSONL on stdout):
  python relay.py YOU --watch

Server compromise leaks the registry (who's online + their endpoints), never
message content. No store-and-forward; recipients must be online to receive.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
LOG = HERE / ".relay.log"
POLL = 0.5

# ─── Signaling server (P2P discovery, never sees messages) ────────────────
# RELAY_URL points at an rshtex-signal server. The server answers /register,
# /lookup, /heartbeat, /signal, /presence — nothing else. Messages flow
# directly between agents over TCP, signed (and optionally encrypted) end-
# to-end. Server compromise leaks the registry; never the content.
VERSION = "0.1.0"
DEFAULT_SIGNAL_URL = "https://relay.csclear.net"
SIGNAL_URL = os.environ.get("RELAY_URL", DEFAULT_SIGNAL_URL).rstrip("/")
P2P = bool(SIGNAL_URL)


# Minimal SOCKS5 client (no-auth, hostname-resolved by proxy) — only used for
# the signaling HTTP calls (/register, /lookup, /heartbeat, /signal). Messages
# never go through this path. Set RELAY_SOCKS=host:port to enable.
def _parse_socks_env():
    raw = (os.environ.get("RELAY_SOCKS")
           or os.environ.get("HTTPS_PROXY", "")
           or os.environ.get("https_proxy", ""))
    if not raw: return None
    if "://" in raw:
        scheme, _, rest = raw.partition("://")
        if not scheme.lower().startswith("socks"): return None
        raw = rest
    raw = raw.strip().rstrip("/")
    if "@" in raw: raw = raw.split("@", 1)[1]
    if ":" not in raw: return None
    host, _, port_s = raw.rpartition(":")
    try: return (host, int(port_s))
    except ValueError: return None

SOCKS_PROXY = _parse_socks_env()


def _socks5_connect(proxy_host, proxy_port, target_host, target_port, timeout=10):
    import socket as _s, struct as _st
    s = _s.create_connection((proxy_host, proxy_port), timeout=timeout)
    s.sendall(b"\x05\x01\x00")
    g = s.recv(2)
    if len(g) < 2 or g[0] != 5 or g[1] != 0:
        s.close(); raise OSError(f"SOCKS5 greeting refused: {g!r}")
    host = target_host.encode("idna")
    if len(host) > 255:
        s.close(); raise OSError("SOCKS5 hostname too long")
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host
              + _st.pack("!H", target_port))
    rep = s.recv(4)
    if len(rep) < 4 or rep[0] != 5:
        s.close(); raise OSError(f"SOCKS5 bad reply: {rep!r}")
    if rep[1] != 0:
        s.close(); raise OSError(f"SOCKS5 connect failed (code {rep[1]})")
    atyp = rep[3]
    if   atyp == 1: s.recv(6)
    elif atyp == 4: s.recv(18)
    elif atyp == 3:
        ln = s.recv(1)
        if not ln: s.close(); raise OSError("SOCKS5 truncated")
        s.recv(ln[0] + 2)
    return s


_SOCKS_OPENER = None
def _build_socks_opener(proxy_host, proxy_port):
    import http.client, urllib.request, ssl as _ssl
    class _SH(http.client.HTTPSConnection):
        def connect(self):
            sock = _socks5_connect(proxy_host, proxy_port, self.host, self.port or 443,
                                   timeout=self.timeout if self.timeout else 10)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
    class _H(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(_SH, req, context=_ssl.create_default_context())
    return urllib.request.build_opener(_H())

import socket as _sock
import queue as _queue
import struct as _struct

# ─── P2P transport state ───────────────────────────────────────────────────
_p2p_inbox = _queue.Queue()           # incoming envelopes for local consumers
_p2p_peers = {}                       # pubkey → {sock, last_use, lock}
_p2p_port = 0                         # our listener port
_p2p_lock = threading.Lock()
_p2p_started = False

# Per-peer replay-protection cache. Each peer's last 200 nonces are tracked;
# a duplicate nonce within the 5-min skew window is silently dropped.
import collections as _collections
_NONCE_CACHE = {}                     # pubkey_b64 → deque[nonce_b64]
_NONCE_CACHE_LOCK = threading.Lock()
_REPLAY_SKEW_SEC = 300                # ±5 min — enough for clock drift, tight enough to bound replay window

def _nonce_seen(pubkey_b64, nonce_b64):
    """True if we've seen this (peer, nonce) pair recently. Records it as seen."""
    with _NONCE_CACHE_LOCK:
        cache = _NONCE_CACHE.get(pubkey_b64)
        if cache is None:
            cache = _collections.deque(maxlen=200)
            _NONCE_CACHE[pubkey_b64] = cache
        if nonce_b64 in cache:
            return True
        cache.append(nonce_b64)
        return False


def _signal_request(method, path, body=None):
    """HTTP request to signaling server. Honors SOCKS_PROXY for the HTTP
    transport when the network MITMs TLS (corp Fortinet etc.). Returns
    parsed JSON dict or {error: msg}."""
    global _SOCKS_OPENER
    if not SIGNAL_URL:
        return {"error": "no signal url"}
    import urllib.request, urllib.error, ssl
    url = f"{SIGNAL_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "rshtex/1.0"})
    try:
        if SOCKS_PROXY and url.startswith("https://"):
            if _SOCKS_OPENER is None:
                _SOCKS_OPENER = _build_socks_opener(*SOCKS_PROXY)
            resp = _SOCKS_OPENER.open(req, timeout=10)
        else:
            ctx = ssl.create_default_context() if url.startswith("https://") else None
            resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404: return {"error": "not_found"}
        try: return json.loads(e.read())
        except Exception: return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def _signal_post(path, body): return _signal_request("POST", path, body)
def _signal_get(path):        return _signal_request("GET",  path)


def _detect_local_host():
    """Find a reasonable host for the listener to advertise.
    For LAN/loopback use, this returns 127.0.0.1 by default. Override
    via RELAY_ADVERTISE_HOST for cross-host scenarios."""
    h = os.environ.get("RELAY_ADVERTISE_HOST")
    if h: return h
    return "127.0.0.1"


def _frame_send(sock, obj):
    """Send a length-prefixed JSON message."""
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sock.sendall(_struct.pack("!I", len(data)) + data)


def _frame_recv(sock):
    """Receive one length-prefixed JSON message. Returns dict or raises."""
    hdr = b""
    while len(hdr) < 4:
        chunk = sock.recv(4 - len(hdr))
        if not chunk: raise ConnectionError("peer closed")
        hdr += chunk
    n = _struct.unpack("!I", hdr)[0]
    if n > 1 << 20: raise ValueError(f"frame too large: {n}")
    data = b""
    while len(data) < n:
        chunk = sock.recv(min(65536, n - len(data)))
        if not chunk: raise ConnectionError("peer closed")
        data += chunk
    return json.loads(data.decode("utf-8", "replace"))


def _p2p_handshake(sock, our_agent, expected_peer_pubkey=None, initiator=True):
    """Mutual auth: both sides prove key ownership by signing the other's nonce.
    Returns (peer_pubkey, peer_alias) on success or raises."""
    _, our_pk = _identity_for(our_agent)
    our_pk_b64 = base64.b64encode(our_pk).decode("ascii")
    our_nonce = secrets.token_bytes(16)

    if initiator:
        _frame_send(sock, {"type": "hello", "pubkey": our_pk_b64,
                           "nonce": base64.b64encode(our_nonce).decode("ascii"),
                           "alias": our_agent})
        msg = _frame_recv(sock)
        if msg.get("type") != "hello": raise ValueError("expected hello")
        peer_pk_b64 = msg["pubkey"]
        peer_alias = msg.get("alias", "")
        peer_nonce = base64.b64decode(msg["nonce"])
        peer_sig = base64.b64decode(msg["sig"])
        peer_pk = base64.b64decode(peer_pk_b64)
        ack_payload = b"rshtex-ack" + our_nonce
        if not _ed_verify(peer_sig, ack_payload, peer_pk):
            raise ValueError("peer auth failed")
        if expected_peer_pubkey and peer_pk_b64 != expected_peer_pubkey:
            raise ValueError("peer pubkey mismatch")
        seed, _ = _identity_for(our_agent)
        our_sig = _ed_sign(b"rshtex-ack" + peer_nonce, seed, our_pk)
        _frame_send(sock, {"type": "ack",
                           "sig": base64.b64encode(our_sig).decode("ascii")})
        if peer_alias:
            _contacts_add(peer_alias, peer_pk_b64, source="handshake")
        return (peer_pk_b64, peer_alias)
    else:
        msg = _frame_recv(sock)
        if msg.get("type") != "hello": raise ValueError("expected hello")
        peer_pk_b64 = msg["pubkey"]
        peer_alias = msg.get("alias", "")
        peer_nonce = base64.b64decode(msg["nonce"])
        peer_pk = base64.b64decode(peer_pk_b64)
        seed, _ = _identity_for(our_agent)
        our_sig = _ed_sign(b"rshtex-ack" + peer_nonce, seed, our_pk)
        _frame_send(sock, {"type": "hello", "pubkey": our_pk_b64,
                           "nonce": base64.b64encode(our_nonce).decode("ascii"),
                           "alias": our_agent,
                           "sig": base64.b64encode(our_sig).decode("ascii")})
        ack = _frame_recv(sock)
        if ack.get("type") != "ack": raise ValueError("expected ack")
        peer_sig = base64.b64decode(ack["sig"])
        if not _ed_verify(peer_sig, b"rshtex-ack" + our_nonce, peer_pk):
            raise ValueError("peer auth failed")
        if peer_alias:
            _contacts_add(peer_alias, peer_pk_b64, source="handshake")
        return (peer_pk_b64, peer_alias)


def _p2p_handle_peer(sock, agent, peer_pk_b64, peer_alias):
    """Read envelopes from an authenticated peer connection until close."""
    sock.settimeout(None)
    # RELAY_STRICT=1 requires every envelope to be a v2 signed envelope
    # (sig + ts_epoch + nonce). Off by default so v1 peers keep flowing during
    # rollout; flip on once the fleet is v2-only.
    strict = os.environ.get("RELAY_STRICT") == "1"
    try:
        while True:
            env = _frame_recv(sock)
            # Only accept envelopes from the authenticated peer
            if env.get("from") != peer_pk_b64:
                continue                                  # silently drop spoofs
            # Verify signature on payload (v2: ts+nonce; v1 legacy: pk+content)
            sig_b64 = env.get("sig")
            content = env.get("content", "")
            ts_epoch = env.get("ts_epoch")
            nonce_b64 = env.get("nonce")
            sender_pk = base64.b64decode(peer_pk_b64)
            if strict and not (sig_b64 and ts_epoch is not None and nonce_b64):
                continue                                  # STRICT: v2 sig required
            if sig_b64:
                if ts_epoch is not None and nonce_b64:
                    # v2: enforce skew + replay-uniqueness BEFORE crypto so a
                    # stale-but-valid sig can't waste verify cycles.
                    try:
                        if abs(int(time.time()) - int(ts_epoch)) > _REPLAY_SKEW_SEC:
                            continue                              # outside skew
                    except (ValueError, TypeError):
                        continue
                    if _nonce_seen(peer_pk_b64, nonce_b64):
                        continue                                  # replay
                    payload = f"{peer_pk_b64}\n{ts_epoch}\n{nonce_b64}\n{content}".encode("utf-8")
                else:
                    # v1: legacy format. Backwards compat during rollout — drop
                    # this branch once all peers ship v2.
                    payload = (peer_pk_b64 + "\n" + content).encode("utf-8")
                try:
                    if not _ed_verify(base64.b64decode(sig_b64), payload, sender_pk):
                        continue
                except Exception:
                    continue
            display_name = peer_alias or peer_pk_b64[:12]
            ts = env.get("ts", "")[11:19] if env.get("ts") else datetime.now().strftime("%H:%M:%S")
            _p2p_inbox.put({
                "from_pubkey": peer_pk_b64,
                "from": display_name,
                "to":   env.get("to"),
                "kind": env.get("kind"),
                "content": content,
                "ts": ts,
                "trust": "verified",
            })
            _append(display_name, content)                # mirror to local log
    except Exception:
        pass
    finally:
        with _p2p_lock:
            if peer_pk_b64 in _p2p_peers and _p2p_peers[peer_pk_b64].get("sock") is sock:
                del _p2p_peers[peer_pk_b64]
        try: sock.close()
        except Exception: pass


def _p2p_dial(agent, to_pubkey_b64):
    """Lookup peer + open authenticated TCP connection. Returns sock or None."""
    import urllib.parse
    with _p2p_lock:
        existing = _p2p_peers.get(to_pubkey_b64)
        if existing and existing.get("sock"):
            return existing["sock"]
    info = _signal_get(f"/lookup?addr={urllib.parse.quote(to_pubkey_b64, safe='')}")
    if info.get("error"): return None
    host, port = info.get("host"), info.get("port")
    if not host or not port: return None
    try:
        sock = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        peer_pk, peer_alias = _p2p_handshake(sock, agent,
                                             expected_peer_pubkey=to_pubkey_b64,
                                             initiator=True)
    except Exception:
        try: sock.close()
        except Exception: pass
        return None
    with _p2p_lock:
        _p2p_peers[peer_pk] = {"sock": sock, "alias": peer_alias,
                                "lock": threading.Lock(), "last_use": time.time()}
    threading.Thread(target=_p2p_handle_peer,
                     args=(sock, agent, peer_pk, peer_alias),
                     daemon=True).start()
    return sock


def _p2p_send_envelope(agent, to_pubkey_b64, content, kind=None):
    """Send a signed envelope to a peer over P2P. Returns True if sent.

    Signed payload format (v2):
        pk_b64 || \\n || ts_epoch || \\n || nonce_b64 || \\n || content
    The ts+nonce are also placed unsigned in the envelope; receivers verify the
    signature, then enforce ±5min skew and reject reused nonces."""
    if not P2P or not to_pubkey_b64:
        return False
    sock = _p2p_dial(agent, to_pubkey_b64)
    if not sock: return False
    seed, our_pk = _identity_for(agent)
    our_pk_b64 = base64.b64encode(our_pk).decode("ascii")
    ts_epoch = int(time.time())
    nonce_b64 = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    payload = f"{our_pk_b64}\n{ts_epoch}\n{nonce_b64}\n{content}".encode("utf-8")
    sig = _ed_sign(payload, seed, our_pk)
    from datetime import timezone as _tz
    env = {
        "from": our_pk_b64,
        "to": to_pubkey_b64,
        "ts": datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),  # display
        "ts_epoch": ts_epoch,                                         # signed
        "nonce": nonce_b64,                                           # signed
        "content": content,
        "sig": base64.b64encode(sig).decode("ascii"),
    }
    if kind: env["kind"] = kind
    try:
        with _p2p_lock:
            entry = _p2p_peers.get(to_pubkey_b64)
            lock = entry["lock"] if entry else None
        if lock:
            with lock:
                _frame_send(sock, env)
        else:
            _frame_send(sock, env)
        return True
    except Exception:
        with _p2p_lock:
            if to_pubkey_b64 in _p2p_peers:
                del _p2p_peers[to_pubkey_b64]
        return False


def _p2p_accept_loop(srv, agent):
    while True:
        try:
            conn, addr = srv.accept()
            conn.settimeout(10.0)
            try:
                peer_pk, peer_alias = _p2p_handshake(conn, agent, initiator=False)
            except Exception:
                conn.close()
                continue
            with _p2p_lock:
                _p2p_peers[peer_pk] = {"sock": conn, "alias": peer_alias,
                                        "lock": threading.Lock(), "last_use": time.time()}
            threading.Thread(target=_p2p_handle_peer,
                             args=(conn, agent, peer_pk, peer_alias),
                             daemon=True).start()
        except Exception:
            time.sleep(0.5)


def _p2p_heartbeat_loop(agent):
    """Beat every 20s when healthy; exponential backoff capped at 5min when the
    signal server is unreachable. Avoids hammering a downed server."""
    delay = 20
    while True:
        time.sleep(delay)
        _, pk = _identity_for(agent)
        r = _signal_post("/heartbeat", {"pubkey": base64.b64encode(pk).decode("ascii")})
        if r.get("error"):
            delay = min(300, max(20, delay * 2))
        else:
            delay = 20


def _p2p_start(agent):
    """Open listener, register with signal server, spawn heartbeat thread.
    Idempotent: subsequent calls are no-ops."""
    global _p2p_port, _p2p_started
    if _p2p_started: return _p2p_port
    _p2p_started = True

    # Listen on random port (all interfaces by default; agents register the
    # advertised host explicitly, which is usually 127.0.0.1).
    srv = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
    srv.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 0))
    _p2p_port = srv.getsockname()[1]
    srv.listen(32)
    threading.Thread(target=_p2p_accept_loop, args=(srv, agent), daemon=True).start()

    if P2P:
        _, pk = _identity_for(agent)
        host = _detect_local_host()
        r = _signal_post("/register", {
            "pubkey": base64.b64encode(pk).decode("ascii"),
            "host": host,
            "port": _p2p_port,
            "alias": agent,
            "presence": True,
        })
        if r.get("ok"):
            threading.Thread(target=_p2p_heartbeat_loop, args=(agent,), daemon=True).start()
    return _p2p_port


def _p2p_drain():
    """Pop all queued envelopes (non-blocking)."""
    out = []
    while not _p2p_inbox.empty():
        try: out.append(_p2p_inbox.get_nowait())
        except _queue.Empty: break
    return out


# ─── address book (alias → pubkey) ──────────────────────────────────────
# Pure local — never sent to the signaling server. Format: a JSON object
# mapping alias → {pubkey, added_at, last_seen?}. Aliases are namespaces
# YOU choose; same person could be "@bob" to you and "@dad" to your sister.
_CONTACTS_PATH = Path(os.path.expanduser("~/.relay")) / "contacts.json"
_CONTACTS_LOCK = threading.Lock()


def _contacts_load():
    try:
        with _CONTACTS_LOCK:
            return json.loads(_CONTACTS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _contacts_save(book):
    try:
        _CONTACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CONTACTS_LOCK:
            _CONTACTS_PATH.write_text(json.dumps(book, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    except OSError:
        pass


def _contacts_add(alias, pubkey, source="manual"):
    """Add or update a contact. Returns True if added, False if already present
    with the same pubkey (no change)."""
    if not alias or not pubkey:
        return False
    alias = alias.lstrip("@").strip()
    if not alias:
        return False
    book = _contacts_load()
    existing = book.get(alias)
    if existing and existing.get("pubkey") == pubkey:
        # Just bump last_seen, return no-change
        existing["last_seen"] = datetime.now().isoformat(timespec="seconds")
        _contacts_save(book)
        return False
    book[alias] = {
        "pubkey": pubkey,
        "added_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "last_seen": datetime.now().isoformat(timespec="seconds"),
    }
    _contacts_save(book)
    return True


def _resolve_address(addr):
    """Resolve a destination string to a wire address.
       - raw 44-char base64 pubkey → returned as-is
       - '@alias' → looked up in ~/.relay/contacts.json
       - anything else → returned as-is (caller's problem)"""
    if not addr:
        return None
    if addr.startswith("@"):
        book = _contacts_load()
        entry = book.get(addr[1:])
        if isinstance(entry, dict) and entry.get("pubkey"):
            return entry["pubkey"]
        if isinstance(entry, str):                  # legacy flat-string format
            return entry
        return addr
    return addr


# ANSI
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

# ═══════════════════════════════════════════════════════════════════════
# IDENTITY — Ed25519 signatures (pure-Python, RFC 8032 reference)
# ═══════════════════════════════════════════════════════════════════════
# Each agent generates a 32-byte seed at first send, stored at
#   ~/.relay/identity.<NAME>.key   (mode 0600, never transmitted).
# Outbound cloud messages carry pubkey + sig over (sender || "\n" || content).
# Inbound messages are verified; trust is one of:
#   verified — sig good and pubkey matches TOFU record for sender's name
#   spoofed  — sig good but sender's name was first-seen with a different key
#   badsig   — sig present but doesn't verify against the claimed pubkey
#   unsigned — no pubkey/sig (legacy senders or anonymous)
# Known keys cached at ~/.relay/known-keys.json.
#
# NB: this is the canonical Bernstein/RFC 8032 reference implementation.
# Pure-Python Ed25519 is slow (~30-100ms per op) but fine for relay rates.

_ED_q = 2**255 - 19
_ED_b = 256
_ED_L = 2**252 + 27742317777372353535851937790883648493


def _ed_pow2(x, p):
    while p > 0:
        x = x * x % _ED_q
        p -= 1
    return x


def _ed_inv(z):
    z2 = z * z % _ED_q
    z9 = _ed_pow2(z2, 2) * z % _ED_q
    z11 = z9 * z2 % _ED_q
    z2_5_0 = z11 * z11 % _ED_q * z9 % _ED_q
    z2_10_0 = _ed_pow2(z2_5_0, 5) * z2_5_0 % _ED_q
    z2_20_0 = _ed_pow2(z2_10_0, 10) * z2_10_0 % _ED_q
    z2_40_0 = _ed_pow2(z2_20_0, 20) * z2_20_0 % _ED_q
    z2_50_0 = _ed_pow2(z2_40_0, 10) * z2_10_0 % _ED_q
    z2_100_0 = _ed_pow2(z2_50_0, 50) * z2_50_0 % _ED_q
    z2_200_0 = _ed_pow2(z2_100_0, 100) * z2_100_0 % _ED_q
    z2_250_0 = _ed_pow2(z2_200_0, 50) * z2_50_0 % _ED_q
    return _ed_pow2(z2_250_0, 5) * z11 % _ED_q


_ED_d = -121665 * _ed_inv(121666) % _ED_q
_ED_I = pow(2, (_ED_q - 1) // 4, _ED_q)


def _ed_xrecover(y):
    xx = (y * y - 1) * _ed_inv(_ED_d * y * y + 1)
    x = pow(xx, (_ED_q + 3) // 8, _ED_q)
    if (x * x - xx) % _ED_q != 0:
        x = (x * _ED_I) % _ED_q
    if x % 2 != 0:
        x = _ED_q - x
    return x


_ED_By = 4 * _ed_inv(5)
_ED_Bx = _ed_xrecover(_ED_By)
_ED_B = (_ED_Bx % _ED_q, _ED_By % _ED_q)


def _ed_edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _ed_inv(1 + _ED_d * x1 * x2 * y1 * y2) % _ED_q
    y3 = (y1 * y2 + x1 * x2) * _ed_inv(1 - _ED_d * x1 * x2 * y1 * y2) % _ED_q
    return (x3, y3)


def _ed_scalarmult(P, e):
    if e == 0:
        return (0, 1)
    Q = _ed_scalarmult(P, e // 2)
    Q = _ed_edwards(Q, Q)
    if e & 1:
        Q = _ed_edwards(Q, P)
    return Q


def _ed_encodeint(y):
    bits = [(y >> i) & 1 for i in range(_ED_b)]
    return bytes([sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_ED_b // 8)])


def _ed_encodepoint(P):
    x, y = P
    bits = [(y >> i) & 1 for i in range(_ED_b - 1)] + [x & 1]
    return bytes([sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_ED_b // 8)])


def _ed_bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def _ed_publickey(sk):
    h = hashlib.sha512(sk).digest()
    a = 2 ** (_ED_b - 2) + sum(2 ** i * _ed_bit(h, i) for i in range(3, _ED_b - 2))
    A = _ed_scalarmult(_ED_B, a)
    return _ed_encodepoint(A)


def _ed_Hint(m):
    h = hashlib.sha512(m).digest()
    return sum(2 ** i * _ed_bit(h, i) for i in range(2 * _ED_b))


def _ed_sign(m, sk, pk):
    h = hashlib.sha512(sk).digest()
    a = 2 ** (_ED_b - 2) + sum(2 ** i * _ed_bit(h, i) for i in range(3, _ED_b - 2))
    r = _ed_Hint(bytes(h[i] for i in range(_ED_b // 8, _ED_b // 4)) + m)
    R = _ed_scalarmult(_ED_B, r)
    S = (r + _ed_Hint(_ed_encodepoint(R) + pk + m) * a) % _ED_L
    return _ed_encodepoint(R) + _ed_encodeint(S)


def _ed_isoncurve(P):
    x, y = P
    return (-x * x + y * y - 1 - _ED_d * x * x * y * y) % _ED_q == 0


def _ed_decodeint(s):
    return sum(2 ** i * _ed_bit(s, i) for i in range(0, _ED_b))


def _ed_decodepoint(s):
    y = sum(2 ** i * _ed_bit(s, i) for i in range(0, _ED_b - 1))
    x = _ed_xrecover(y)
    if x & 1 != _ed_bit(s, _ED_b - 1):
        x = _ED_q - x
    P = (x, y)
    if not _ed_isoncurve(P):
        raise ValueError("decoded point not on curve")
    return P


def _ed_verify(s, m, pk):
    if len(s) != _ED_b // 4 or len(pk) != _ED_b // 8:
        return False
    try:
        R = _ed_decodepoint(s[0:_ED_b // 8])
        A = _ed_decodepoint(pk)
        S = _ed_decodeint(s[_ED_b // 8:_ED_b // 4])
        h = _ed_Hint(_ed_encodepoint(R) + pk + m)
        return _ed_scalarmult(_ED_B, S) == _ed_edwards(R, _ed_scalarmult(A, h))
    except Exception:
        return False


# ─── identity store ─────────────────────────────────────────────────────
# Per-name Ed25519 seeds at ~/.relay/identity.<NAME>.key (mode 0600). TOFU
# for peers happens via the address-book (~/.relay/contacts.json), populated
# on each authenticated P2P handshake — no separate known-keys store.
_ID_DIR = Path(os.path.expanduser("~/.relay"))
_ID_CACHE = {}                                  # name → (seed, pubkey)


def _identity_for(name):
    """Return (seed_bytes, pubkey_bytes), creating + persisting on first use."""
    if name in _ID_CACHE:
        return _ID_CACHE[name]
    _ID_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    path = _ID_DIR / f"identity.{safe}.key"
    if path.exists():
        seed = path.read_bytes()
    else:
        seed = secrets.token_bytes(32)
        path.write_bytes(seed)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    pk = _ed_publickey(seed)
    _ID_CACHE[name] = (seed, pk)
    return _ID_CACHE[name]


def _trust_tag(trust):
    """Return display tag for a trust state. Empty string for the common case
    (verified / unsigned during rollout) so output stays uncluttered; only
    anomalies surface."""
    if trust == "spoofed": return " ⚠SPOOFED"
    if trust == "badsig":  return " ✗BADSIG"
    return ""
# ═══════════════════════════════════════════════════════════════════════
# LOG I/O (binary mode — no \r\n issues on Windows)
# ═══════════════════════════════════════════════════════════════════════

_LOG_ROTATE_BYTES = 5 * 1024 * 1024   # rotate at 5MB; one .log.1 backup is kept


def _append(sender, text):
    ts = datetime.now().strftime("%H:%M:%S")
    # Soft rotation — bounded local growth without losing recent context.
    try:
        if LOG.exists() and LOG.stat().st_size > _LOG_ROTATE_BYTES:
            backup = LOG.with_suffix(".log.1")
            if backup.exists():
                backup.unlink()
            LOG.rename(backup)
    except OSError:
        pass
    with open(LOG, "ab") as f:
        if "\n" in text:
            f.write(f"[{ts}] {sender}<<\n{text}\n>>{sender}\n".encode("utf-8"))
        else:
            f.write(f"[{ts}] {sender}: {text}\n".encode("utf-8"))


def _parse(raw):
    msgs = []
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("[") and "] " in ln:
            br = ln.find("]")
            if br < 1:
                i += 1
                continue
            ts = ln[1:br]
            rest = ln[br + 2:]
            if rest.endswith("<<"):
                who = rest[:-2]
                end = f">>{who}"
                body = []
                i += 1
                while i < len(lines) and lines[i] != end:
                    body.append(lines[i])
                    i += 1
                msgs.append((who, "\n".join(body), ts))
                i += 1
                continue
            elif ": " in rest:
                who, txt = rest.split(": ", 1)
                msgs.append((who, txt, ts))
        i += 1
    return msgs


def _size():
    return LOG.stat().st_size if LOG.exists() else 0


def _read_from(offset):
    if not LOG.exists():
        return [], 0
    sz = LOG.stat().st_size
    if sz <= offset:
        return [], offset
    with open(LOG, "rb") as f:
        f.seek(offset)
        raw = f.read().decode("utf-8", errors="replace")
    return _parse(raw), sz


# ═══════════════════════════════════════════════════════════════════════
# MACRO LAYER (\def / \use / bare-name expansion, persisted local table)
# ═══════════════════════════════════════════════════════════════════════
# Defs broadcast verbatim — every agent re-parses on receive so tables converge.
# Calls expand at display time only; missing macros pass through untouched.

MACROS = HERE / ".relay.macros.json"
# Optional 4th {kind} group: \def{name}{params}{body}{kind}. Missing → kind='text'.
_DEF_RE = re.compile(r"\\def\{(\w+)\}\{([^}]*)\}\{((?:[^{}]|\{[^{}]*\})*)\}(?:\{(\w+)\})?")
_CALL_RE = re.compile(r"\\(\w+)((?:\{[^{}]*\})+)")
_ARG_RE = re.compile(r"\{([^{}]*)\}")

def format_def(name, params, body, kind="text"):
    """Canonical wire form for a macro definition. Kept in sync with _DEF_RE."""
    s = "\\def{" + name + "}{" + ",".join(params) + "}{" + body + "}"
    if kind and kind != "text":
        s += "{" + kind + "}"
    return s


def _macro_load():
    try:
        return json.loads(MACROS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _macro_save(table):
    try:
        MACROS.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _macro_scan_defs(text, sender=None, ts=None):
    """Update local table with any \\def{name}{params}{body}[{kind}] found in text."""
    table = _macro_load()
    changed = False
    for m in _DEF_RE.finditer(text):
        name, raw_params, body = m.group(1), m.group(2), m.group(3)
        kind = m.group(4) or "text"
        params = [p.strip() for p in raw_params.split(",") if p.strip()]
        table[name] = {
            "kind": kind,
            "params": params,
            "body": body,
            "from": sender,
            "ts": ts or datetime.now().isoformat(timespec="seconds"),
        }
        changed = True
    if changed:
        _macro_save(table)
    return table


# Macro expansion is now pure substitution. The kind tag is metadata (so
# receivers know how to parse the expanded body) — relay.py never executes
# python / bash / c / cpatch / sql bodies. If you want execution semantics,
# wire your own consumer that watches for those kinds and applies trust as
# you see fit. The relay is content-typed, not RPC.
def _eval_text(macro, substituted, agent):
    return substituted


EVAL_HANDLERS = {}     # left empty for callers; default behavior is _eval_text


def _macro_expand(text, table=None, agent=None):
    """Expand \\use{name}{...} and bare \\name{...} calls. Missing → leave raw.

    After parameter substitution, dispatch to EVAL_HANDLERS[kind] so non-text
    kinds (python, bash) actually run. Untrusted authors cannot execute code.
    """
    if table is None:
        table = _macro_load()
    if not table:
        return text

    def _apply(macro, args):
        out = macro["body"]
        for i, p in enumerate(macro["params"]):
            out = out.replace("{" + p + "}", args[i] if i < len(args) else "")
        kind = macro.get("kind", "text")
        handler = EVAL_HANDLERS.get(kind, _eval_text)
        return handler(macro, out, agent)

    def _h_def(m, args):
        return m.group(0)  # defs broadcast verbatim; don't expand

    def _h_use(m, args):
        if not args:
            return m.group(0)
        target = table.get(args[0])
        if not target:
            return m.group(0)
        return _apply(target, args[1:])

    HANDLERS = {"def": _h_def, "use": _h_use}

    def _sub(m):
        name = m.group(1)
        args = _ARG_RE.findall(m.group(2))
        h = HANDLERS.get(name)
        if h:
            return h(m, args)
        macro = table.get(name)
        if not macro:
            return m.group(0)
        return _apply(macro, args)

    # Two passes: lets one body reference another macro.
    return _CALL_RE.sub(_sub, _CALL_RE.sub(_sub, text))


# ═══════════════════════════════════════════════════════════════════════
# SEND
# ═══════════════════════════════════════════════════════════════════════

def _send(agent, text, to=None, kind=None):
    """Universal send: local file + (if `to` set) direct P2P.
    Local file is always written (and is the broadcast medium for same-dir
    agents). When `to` is provided AND the signaling server is configured,
    we open/reuse a P2P connection and deliver an authenticated envelope.
    No cloud store-and-forward; no broadcast over the wire."""
    _macro_scan_defs(text, sender=agent)
    _append(agent, text)
    _p2p_start(agent)        # ensure listener + registration are up
    if not to:
        return ""
    to_addr = _resolve_address(to)
    if not to_addr or not P2P:
        return " (no signal/no addr)"
    ok = _p2p_send_envelope(agent, to_addr, text, kind=kind)
    return (f" → {to_addr[:12]}…") if ok else " (p2p-fail)"


def cmd_send(agent, text, to=None, kind=None):
    cid = _send(agent, text, to=to, kind=kind)
    suffix = (f" → {to}" if to else "") + (f" [{kind}]" if kind else "")
    print(f"[{datetime.now():%H:%M:%S}] {agent}: sent ({len(text)} chars){suffix}{cid}")


def cmd_whoami(agent):
    """Print this agent's address (Ed25519 pubkey, base64). Generates the
    keypair on first call if it doesn't exist."""
    _, pk = _identity_for(agent)
    print(base64.b64encode(pk).decode("ascii"))


def cmd_contacts():
    """List all contacts (alias → pubkey, sortable)."""
    book = _contacts_load()
    if not book:
        print("(no contacts yet — they're added automatically when peers handshake "
              "with you, or use --add @alias <pubkey>)")
        return
    print(f"[CONTACTS] ({len(book)})")
    for alias in sorted(book.keys()):
        e = book[alias]
        if isinstance(e, dict):
            pk = e.get("pubkey", "?")
            seen = e.get("last_seen", e.get("added_at", ""))[:19]
            src = e.get("source", "?")
            print(f"  @{alias:<16} {pk[:32]}…  {seen}  ({src})")
        else:
            print(f"  @{alias:<16} {str(e)[:32]}…")


def cmd_add_contact(alias, pubkey):
    """Add a contact. alias may include leading @."""
    alias = alias.lstrip("@")
    if _contacts_add(alias, pubkey, source="manual"):
        print(f"[ADD] @{alias} → {pubkey[:32]}…")
    else:
        print(f"[NOOP] @{alias} already maps to {pubkey[:32]}…")


def cmd_presence():
    """List agents currently registered with the signaling server."""
    if not P2P:
        print("[PRESENCE] no signaling server configured (set RELAY_URL).")
        return
    r = _signal_get("/presence")
    agents = r.get("agents") or []
    if not agents:
        print(f"[PRESENCE] no agents registered at {SIGNAL_URL}")
        return
    print(f"[PRESENCE] {len(agents)} on {SIGNAL_URL}")
    for a in agents:
        pk = a.get("pubkey", "")
        alias = a.get("alias", "")
        seen = a.get("registered_at", "")[:19]
        print(f"  {pk[:32]}…  @{alias or '?':<16} since {seen}")


def cmd_watch(agent):
    """Block reading messages addressed to this agent's address. Emits one
    JSON object per line on stdout (machine-readable). Exits on Ctrl-C.
    Sources: P2P inbox (envelopes verified by handshake + per-msg sig)."""
    if not P2P:
        print("[WATCH] no signaling server (set RELAY_URL); nothing to watch.",
              file=sys.stderr)
        sys.exit(2)
    _, pk = _identity_for(agent)
    my_addr = base64.b64encode(pk).decode("ascii")
    print(f"[WATCH] {agent} listening on {my_addr[:12]}… (port {_p2p_start(agent)})",
          file=sys.stderr)
    sys.stderr.flush()
    try:
        while True:
            for m in _p2p_drain():
                out = {
                    "from":    m.get("from"),
                    "from_pubkey": m.get("from_pubkey"),
                    "ts":      m.get("ts"),
                    "to":      m.get("to"),
                    "kind":    m.get("kind"),
                    "trust":   m.get("trust"),
                    "content": m.get("content"),
                }
                print(json.dumps(out, ensure_ascii=False))
                sys.stdout.flush()
            time.sleep(POLL)
    except KeyboardInterrupt:
        sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════
# FLOW (main agent idle mode)
# ═══════════════════════════════════════════════════════════════════════

def cmd_flow(agent, timeout=None, mention=False, from_name=None,
             kind_filter=None, keep=False):
    """Block, stream relevant messages, wake on first match (or stream forever
    with --keep). The LLM picks how often to recv; this function only governs
    one recv's responsiveness — and uses a blocking queue.get on the P2P inbox
    so frames arriving on the wire wake us within milliseconds, not POLL secs.

    Filters compose:
      mention=True       only @AGENT mentions or direct-pubkey-addressed P2P
      from_name=NAME     only messages from a specific sender
      kind_filter=KIND   only messages tagged with a specific content kind (P2P)
      keep=True          do not exit on wake; keep streaming
    """
    port = _p2p_start(agent)
    local_off = _size()
    seen = set()  # dedup: (sender, content_hash)

    # Resolve my address once for the mention-by-pubkey check.
    try:
        _, _my_pk = _identity_for(agent)
        _my_addr = base64.b64encode(_my_pk).decode("ascii")
    except Exception:
        _my_addr = None

    def _matches(who, txt, kind=None, to=None):
        """True if this message satisfies the active filter set."""
        if who == "SYSTEM" or who.upper() == agent.upper():
            return False
        if from_name and who.upper() != from_name.upper():
            return False
        if kind_filter and kind != kind_filter:
            return False
        if mention:
            if f"@{agent.upper()}" in txt.upper():
                return True
            if to and _my_addr and to == _my_addr:
                return True
            return False
        return True

    modes = ["local"]
    if P2P:
        modes.append(f"p2p:{port}")
    flags = []
    if mention:      flags.append("mention")
    if from_name:    flags.append(f"from={from_name}")
    if kind_filter:  flags.append(f"kind={kind_filter}")
    if keep:         flags.append("keep")
    suffix = (" [" + ",".join(flags) + "]") if flags else ""
    print(f"[FLOW] {agent} standing by ({'+'.join(modes)}){suffix}"
          + (f" (timeout {timeout}m)" if timeout else ""))
    sys.stdout.flush()

    def _display(who, txt, ts, trust=None):
        if who.upper() != agent.upper():
            _macro_scan_defs(txt, sender=who, ts=ts)
            txt = _macro_expand(txt, agent=agent)
        ttag = _trust_tag(trust) if trust else ""
        if "\n" in txt:
            print(f">>> [{ts}] {who}{ttag}:")
            for ln in txt.split("\n"):
                print(f"    {ln}")
        else:
            print(f">>> [{ts}] {who}{ttag}: {txt}")
        sys.stdout.flush()

    t0 = time.time()
    try:
        while True:
            wake = False

            # 1. Block briefly on the P2P inbox so an incoming frame wakes us
            #    within milliseconds. If nothing arrives within POLL we fall
            #    through to the local-file scan; either way the cycle bounds
            #    at POLL seconds when idle.
            p2p_batch = []
            try:
                p2p_batch.append(_p2p_inbox.get(timeout=POLL))
                # Drain any pile-up so we render the batch atomically.
                while True:
                    try:
                        p2p_batch.append(_p2p_inbox.get_nowait())
                    except _queue.Empty:
                        break
            except _queue.Empty:
                pass

            # 2. Local file (same-dir broadcast medium — no kind/to metadata)
            local_msgs, local_off = _read_from(local_off)
            for who, txt, ts in local_msgs:
                key = (who, hash(txt))
                if key in seen:
                    continue
                seen.add(key)
                if _matches(who, txt):
                    _display(who, txt, ts)
                    wake = True

            # 3. P2P frames (carry kind + recipient + verified trust tag)
            for m in p2p_batch:
                who = m.get("from", "?")
                txt = m.get("content", "")
                ts = m.get("ts", "")
                kind = m.get("kind")
                to = m.get("to")
                key = (who, hash(txt))
                if key in seen:
                    continue
                seen.add(key)
                if _matches(who, txt, kind=kind, to=to):
                    _display(who, txt, ts, m.get("trust"))
                    wake = True

            # Bound seen set — accepts a once-per-rollover dup as the tradeoff.
            if len(seen) > 1000:
                seen.clear()

            if wake and not keep:
                print(f"\n[WAKE] exiting flow")
                sys.stdout.flush()
                return

            if timeout and (time.time() - t0) / 60 >= timeout:
                print(f"\n[TIMEOUT] {timeout}m elapsed")
                sys.exit(2)
            # No sleep — the P2P queue.get already amortized POLL above.
    except KeyboardInterrupt:
        print("\n[EXIT]")


# ═══════════════════════════════════════════════════════════════════════
# HUMAN MODES (log, tail, chat, who, clear)
# ═══════════════════════════════════════════════════════════════════════

def cmd_log(n=10):
    # Always show local (primary)
    if not LOG.exists():
        print("(no messages yet)")
        return
    msgs = _parse(LOG.read_bytes().decode("utf-8", errors="replace"))[-n:]
    if not msgs:
        print("(no messages yet)")
        return
    for who, txt, ts in msgs:
        if "\n" in txt:
            ll = txt.split("\n")
            print(f"[{ts}] {who}: ({len(ll)} lines)")
            for ln in ll[:5]:
                print(f"    {ln[:120]}")
            if len(ll) > 5:
                print(f"    ... +{len(ll) - 5} lines")
        else:
            print(f"[{ts}] {who}: {txt}")


def cmd_tail():
    off = _size()
    if LOG.exists():
        for who, txt, ts in _parse(LOG.read_bytes().decode("utf-8", errors="replace"))[-5:]:
            if "\n" in txt:
                print(f"[{ts}] {who}: ({txt.count(chr(10))+1} lines)")
            else:
                print(f"[{ts}] {who}: {txt}")
        print("--- live ---")
    sys.stdout.flush()
    try:
        while True:
            msgs, off = _read_from(off)
            for who, txt, ts in msgs:
                if "\n" in txt:
                    print(f"[{ts}] {who}:")
                    for ln in txt.split("\n"):
                        print(f"    {ln}")
                else:
                    print(f"[{ts}] {who}: {txt}")
                sys.stdout.flush()
            time.sleep(POLL)
    except KeyboardInterrupt:
        print("\n[EXIT]")


def _init_raw_input():
    """Set up character-by-character input (no line buffering)."""
    if sys.platform == "win32":
        import msvcrt
        return {"type": "win", "mod": msvcrt}
    else:
        import tty, termios, select as _sel
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)  # cbreak, not raw — keeps ctrl+c working
        return {"type": "unix", "fd": fd, "old": old, "sel": _sel, "termios": termios}


def _cleanup_raw_input(ctx):
    if ctx["type"] == "unix":
        ctx["termios"].tcsetattr(ctx["fd"], ctx["termios"].TCSADRAIN, ctx["old"])


def _kbhit(ctx):
    if ctx["type"] == "win":
        return ctx["mod"].kbhit()
    else:
        r, _, _ = ctx["sel"].select([sys.stdin], [], [], 0)
        return bool(r)


def _getch(ctx):
    if ctx["type"] == "win":
        return ctx["mod"].getwch()
    else:
        return sys.stdin.read(1)


# Sentinel keys returned by _getkey for non-printable inputs. Sentinels start
# with NUL so they can never collide with a real character the user types.
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT = "\x00UP", "\x00DOWN", "\x00LEFT", "\x00RIGHT"
KEY_TAB, KEY_ENTER, KEY_BACKSPACE, KEY_CTRL_C = "\x00TAB", "\x00ENTER", "\x00BS", "\x00C3"


def _getkey(ctx):
    """Read one logical key. Returns either a single printable char or a KEY_*
    sentinel for arrows/tab/enter/backspace/ctrl-c. Empty string if the key
    couldn't be decoded (e.g. lone ESC)."""
    ch = _getch(ctx)
    if ctx["type"] == "win":
        if ch in ("\x00", "\xe0"):
            ch2 = _getch(ctx)
            return {"H": KEY_UP, "P": KEY_DOWN, "K": KEY_LEFT, "M": KEY_RIGHT}.get(ch2, "")
        if ch == "\t": return KEY_TAB
        if ch == "\r": return KEY_ENTER
        if ch in ("\x08", "\x7f"): return KEY_BACKSPACE
        if ch == "\x03": return KEY_CTRL_C
        return ch
    else:
        if ch == "\x1b":
            # CSI sequence — only consume if more bytes are immediately available;
            # a lone ESC should not block waiting for the next key.
            if _kbhit(ctx):
                ch2 = _getch(ctx)
                if ch2 == "[" and _kbhit(ctx):
                    ch3 = _getch(ctx)
                    return {"A": KEY_UP, "B": KEY_DOWN, "C": KEY_RIGHT, "D": KEY_LEFT}.get(ch3, "")
            return ""
        if ch == "\t": return KEY_TAB
        if ch in ("\r", "\n"): return KEY_ENTER
        if ch in ("\x08", "\x7f"): return KEY_BACKSPACE
        if ch == "\x03": return KEY_CTRL_C
        return ch


def cmd_chat(agent):
    """Interactive chat — context banner, slash commands, per-agent colors."""

    lock = threading.Lock()
    input_buf = []
    sent_history = []   # past sent lines (lists of chars), oldest first, capped at 50

    # Mutable closure state — bag of dict to avoid `nonlocal` for each field.
    state = {
        "cursor_pos": 0,        # caret position inside input_buf
        "hist_idx": -1,         # -1 means "live draft"; 0..N maps to sent_history[-1..-N-1]
        "draft_save": [],       # snapshot of input_buf before walking up history
        "only_me": False,       # /only filter — show only @me-addressed messages
        "stream_agents": set(), # which ghost streams to tail into chat (/stream NAME)
    }

    # Per-agent colors derived from pubkey/name hash so the same name keeps
    # the same color across sessions. Avoids "is this still BUILDER?" eye-strain.
    PALETTE = ["\033[36m", "\033[33m", "\033[35m", "\033[32m", "\033[34m",
               "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m",
               "\033[96m"]

    def _agent_color(name):
        h = sum(ord(c) for c in (name or "")) % len(PALETTE)
        return PALETTE[h]

    def _is_addressed_to_me(txt):
        """True if message @-mentions me or contains my address prefix."""
        return f"@{agent.upper()}" in txt.upper()

    def _redraw():
        only_marker = "★" if state["only_me"] else ""
        prompt = f"{GREEN}{agent}{only_marker}>{RESET} "
        buf_str = "".join(input_buf)
        sys.stdout.write(f"\r\033[K{prompt}{buf_str}")
        # Reposition the caret if we're editing mid-line.
        back = len(input_buf) - state["cursor_pos"]
        if back > 0:
            sys.stdout.write(f"\033[{back}D")
        sys.stdout.flush()

    def _emit(*lines):
        with lock:
            sys.stdout.write("\r\033[K")
            for l in lines:
                sys.stdout.write(l + "\n")
            _redraw()

    def _fmt_msg(who, txt, ts, trust=None):
        if who.upper() != agent.upper():
            _macro_scan_defs(txt, sender=who, ts=ts)
            txt = _macro_expand(txt, agent=agent)
        ttag = _trust_tag(trust) if trust else ""
        ncolor = _agent_color(who)
        # Highlight if addressed to me — bg-tint the name.
        marker = "★ " if _is_addressed_to_me(txt) else "  "
        lines = []
        lines.append(f"{marker}{BOLD}{ncolor}{who}{RESET}{ttag} {DIM}{ts}{RESET}")
        for l in txt.split("\n"):
            lines.append(f"    {l}")
        lines.append("")
        return lines

    # ─── banner: orient the user immediately on startup ──────────────────
    try:
        _, my_pk = _identity_for(agent)
        my_addr = base64.b64encode(my_pk).decode("ascii")
    except Exception:
        my_addr = "(no identity)"
    server = (SIGNAL_URL or "(local-only — no signaling)") + (
        "  (default — /server to switch)" if SIGNAL_URL == DEFAULT_SIGNAL_URL else "  (/server to change)")
    nuc = _agent_color(agent)
    print()
    print(f"  {BOLD}╔════════════════════════════════════════════════════╗{RESET}")
    print(f"  {BOLD}║{RESET}  {BOLD}rshtex chat{RESET}                                       {BOLD}║{RESET}")
    print(f"  {BOLD}╠════════════════════════════════════════════════════╣{RESET}")
    print(f"  {BOLD}║{RESET}  you      {nuc}{BOLD}{agent:<42}{RESET}{BOLD}║{RESET}")
    print(f"  {BOLD}║{RESET}  address  {CYAN}{my_addr[:18]}…{RESET}{(' '*23)}{BOLD}║{RESET}")
    print(f"  {BOLD}║{RESET}  server   {DIM}{server[:42]:<42}{RESET}{BOLD}║{RESET}")
    print(f"  {BOLD}║{RESET}  cwd      {DIM}{str(HERE)[:42]:<42}{RESET}{BOLD}║{RESET}")
    print(f"  {BOLD}╠════════════════════════════════════════════════════╣{RESET}")
    print(f"  {BOLD}║{RESET}  {DIM}/h help · /q quit · enter to send · ctrl+c exit  {RESET}{BOLD}║{RESET}")
    print(f"  {BOLD}╚════════════════════════════════════════════════════╝{RESET}")
    print()

    # show recent history (last 5 messages)
    if LOG.exists():
        recent = _parse(LOG.read_bytes().decode("utf-8", errors="replace"))[-5:]
        if recent:
            print(f"  {DIM}── recent ──{RESET}")
            for who, txt, ts in recent:
                if who.upper() != agent.upper():
                    _macro_scan_defs(txt, sender=who, ts=ts)
                    txt = _macro_expand(txt, agent=agent)
                ncolor = _agent_color(who)
                print(f"  {BOLD}{ncolor}{who}{RESET} {DIM}{ts}{RESET}")
                for l in txt.split("\n"):
                    print(f"    {l}")
                print()
            print(f"  {DIM}{'─' * 12}{RESET}")
            print()

    local_off = _size()
    _p2p_start(agent)
    chat_seen = set()
    stop = threading.Event()
    stream_offsets = {}

    def _read_streams():
        events = []
        for sf in HERE.glob(".relay.*.stream"):
            name = sf.stem.split(".", 2)[-1]
            try:
                sz = sf.stat().st_size
            except OSError:
                continue
            prev = stream_offsets.get(name, sz)
            if sz <= prev:
                stream_offsets[name] = sz
                continue
            try:
                with open(sf, "rb") as f:
                    f.seek(prev)
                    raw = f.read().decode("utf-8", errors="replace")
                stream_offsets[name] = sz
                for line in raw.strip().split("\n"):
                    if line.strip():
                        try:
                            events.append((name, json.loads(line)))
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
        return events

    def _fmt_stream(who, event):
        """Format stream event into display lines."""
        lines = []
        etype = event.get("type", "")
        if etype == "assistant":
            for block in event.get("message", {}).get("content", []):
                bt = block.get("type", "")
                if bt == "thinking":
                    txt = block.get("thinking", "").strip()
                    sig = block.get("signature", "")
                    if txt:
                        lines.append(f"  {DIM}{CYAN}{who} ◆ {txt}{RESET}")
                    elif sig:
                        lines.append(f"  {DIM}{CYAN}{who} ◆ ({len(sig)}B thinking redacted){RESET}")
                elif bt == "text":
                    txt = block.get("text", "").strip()
                    if txt:
                        for l in txt.split("\n"):
                            lines.append(f"  {BOLD}{l}{RESET}")
                elif bt == "tool_use":
                    name = block.get("name", "?")
                    inp = block.get("input", {})
                    detail = inp.get("command", inp.get("file_path", inp.get("pattern", "")))
                    lines.append(f"  {YELLOW}{who} → {name}{RESET} {DIM}{detail}{RESET}")
        elif etype == "tool_result":
            content = event.get("content", "")
            if isinstance(content, str) and content.strip():
                lines.append(f"  {DIM}{GREEN}{who} ← {_trunc(content, 120)}{RESET}")
        elif etype == "result":
            cost = event.get("total_cost_usd", 0)
            turns = event.get("num_turns", 0)
            cfmt = f"${cost:.4f}" if cost < 0.01 else f"${cost:.2f}"
            lines.append(f"  {DIM}{who} ■ done | {turns} turns | {cfmt}{RESET}")
        return lines

    def bg():
        nonlocal local_off, chat_seen
        spin_idx = 0
        while not stop.is_set():
            try:
                had_output = False
                new_msgs = []

                # 1a. Local file
                lm, local_off = _read_from(local_off)
                for w, c, t in lm:
                    key = (w, hash(c))
                    if key not in chat_seen and w.upper() != agent.upper():
                        chat_seen.add(key)
                        new_msgs.append((w, c, t, None))   # local: trust unknown

                # 1b. P2P inbox (direct-addressed envelopes from authenticated peers)
                for m in _p2p_drain():
                    w = m.get("from", "?")
                    c = m.get("content", "")
                    t = m.get("ts", "")
                    key = (w, hash(c))
                    if key not in chat_seen and w.upper() != agent.upper():
                        chat_seen.add(key)
                        new_msgs.append((w, c, t, m.get("trust")))

                if len(chat_seen) > 1000:
                    chat_seen.clear()

                # /only filter — drop messages that aren't @me-addressed when on
                if new_msgs and state["only_me"]:
                    new_msgs = [(w, c, t, tr) for (w, c, t, tr) in new_msgs
                                if _is_addressed_to_me(c)]

                if new_msgs:
                    out = []
                    for w, c, t, trust in new_msgs:
                        out.extend(_fmt_msg(w, c, t, trust))
                    _emit(*out)
                    had_output = True

                # /stream NAME tail — opt-in render of ghost agents' stream-json
                if state["stream_agents"]:
                    for s_who, s_event in _read_streams():
                        if s_who.upper() not in state["stream_agents"]:
                            continue
                        s_lines = _fmt_stream(s_who, s_event)
                        if s_lines:
                            _emit(*s_lines)
                            had_output = True
                else:
                    # Drain offsets even when not displaying so we don't replay
                    # the whole file the next time the user toggles /stream on.
                    _read_streams()
            except Exception:
                pass
            stop.wait(0.3)

    threading.Thread(target=bg, daemon=True).start()

    def _do_spawn(parts):
        """Launch ghost agent in a NEW terminal window. /spawn NAME [model] [focus...]"""
        if len(parts) < 2:
            _emit(f"{DIM}usage: /spawn NAME [model] [focus...]{RESET}")
            return
        s_agent = parts[1].upper()
        s_model = parts[2] if len(parts) > 2 else "opus"
        s_focus = " ".join(parts[3:]) if len(parts) > 3 else "general development work"

        # Validate inputs before they reach a shell. Spawn args go through
        # `cmd /k`/`bash -c`/`osascript`, all of which are vulnerable to
        # quoting tricks. Exclusion is simpler than per-shell quoting.
        if not re.match(r"^[A-Z_][A-Z0-9_]*$", s_agent):
            _emit(f"  {DIM}agent name must match [A-Z_][A-Z0-9_]* (got '{s_agent}'){RESET}")
            return
        if not re.match(r"^[a-z][a-z0-9.-]*$", s_model):
            _emit(f"  {DIM}model name must match [a-z][a-z0-9.-]* (got '{s_model}'){RESET}")
            return
        BAD_FOCUS_CHARS = set('&|;`$<>()"\\')
        if any(c in s_focus for c in BAD_FOCUS_CHARS):
            _emit(f"  {DIM}focus contains shell metacharacters; please rephrase ({''.join(sorted(BAD_FOCUS_CHARS))}){RESET}")
            return

        # Credential audit — same guard cmd_spawn applies, surfaced to the chat.
        creds = _spawn_credential_audit(HERE)
        if creds and not os.environ.get("RELAY_SPAWN_FORCE"):
            _emit(f"  {RED}refusing — credential-like files in cwd: {', '.join(creds[:5])}{RESET}",
                  f"  {DIM}set RELAY_SPAWN_FORCE=1 to override.{RESET}")
            return

        relay_path = str(Path(__file__).resolve())

        # Build the spawn command (inputs validated above)
        spawn_cmd = f'python "{relay_path}" --spawn {s_agent} --model {s_model} --focus "{s_focus}"'

        # Pass signaling env vars if active
        env_prefix = ""
        if P2P:
            if sys.platform == "win32":
                env_prefix = f'set RELAY_URL={SIGNAL_URL}&& '
            else:
                env_prefix = f'RELAY_URL={SIGNAL_URL} '

        # Open in new terminal window
        if sys.platform == "win32":
            # Try Windows Terminal first, fall back to cmd
            wt = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
            if wt.exists():
                subprocess.Popen([str(wt), "new-tab", "--title", s_agent, "cmd", "/k",
                                  f"{env_prefix}{spawn_cmd}"], cwd=str(HERE))
            else:
                subprocess.Popen(f'start "{s_agent}" cmd /k "{env_prefix}{spawn_cmd}"',
                                 shell=True, cwd=str(HERE))
        elif sys.platform == "darwin":
            full_cmd = f'{env_prefix}{spawn_cmd}'
            subprocess.Popen(["osascript", "-e",
                              f'tell app "Terminal" to do script "cd {HERE} && {full_cmd}"'])
        else:
            # Linux: try common terminals
            full_cmd = f'{env_prefix}{spawn_cmd}'
            for term in ["gnome-terminal", "xterm", "konsole"]:
                if shutil.which(term):
                    subprocess.Popen([term, "--", "bash", "-c", f"cd {HERE} && {full_cmd}"])
                    break
            else:
                # Fallback: background thread (no new terminal)
                _emit(f"{DIM}no terminal found, running in background{RESET}")
                threading.Thread(target=lambda: os.system(f"cd {HERE} && {full_cmd}"), daemon=True).start()

        _emit(f"{BOLD}spawned {s_agent}{RESET} {DIM}in new terminal (model={s_model}){RESET}")
        _append("SYSTEM", f"{s_agent} spawned from chat (model={s_model})")

    def _show_help():
        with lock:
            sys.stdout.write("\r\033[K")
            print(f"  {BOLD}slash commands{RESET}")
            print(f"    {CYAN}/h /help{RESET}                show this help")
            print(f"    {CYAN}/q /quit /exit{RESET}          leave chat")
            print(f"    {CYAN}/who{RESET}                    list agents seen in local log")
            print(f"    {CYAN}/log [N]{RESET}                show last N messages (default 10)")
            print(f"    {CYAN}/find <text>{RESET}            search recent log for substring (last 15 hits)")
            print(f"    {CYAN}/clear{RESET}                  clear screen")
            print(f"    {CYAN}/only{RESET}                   toggle ★-only filter (mention-addressed messages only)")
            print(f"    {CYAN}/me{RESET}                     print your address (Ed25519 pubkey)")
            print(f"    {CYAN}/contacts{RESET}               list address book (~/.relay/contacts.json)")
            print(f"    {CYAN}/add @alias <pubkey>{RESET}    add a contact (use @alias in /to thereafter)")
            print(f"    {CYAN}/to ADDR msg{RESET}            send `msg` directly to ADDR (pubkey or @alias)")
            print(f"    {CYAN}/kind KIND msg{RESET}          send `msg` tagged with content type")
            print(f"                              (text/markdown/json/bash/python/c/cpatch/sql/html)")
            print(f"    {CYAN}/macros{RESET}                 list macros known locally (rshtex \\def table)")
            print(f"    {CYAN}/def NAME body{RESET}          define and broadcast a macro (use \\NAME later)")
            print(f"                              {DIM}/def NAME{{p1,p2}} body  for params{RESET}")
            print(f"    {CYAN}/stream NAME{RESET}            tail a ghost agent's stream-json into chat ({DIM}/stream off{RESET}{CYAN}){RESET}")
            print(f"    {CYAN}/server [URL]{RESET}           show / switch cloud server (default: {DEFAULT_SIGNAL_URL})")
            print(f"                              {DIM}/server default · /server off · /server <url>{RESET}")
            print(f"    {CYAN}/spawn NAME [model] [focus...]{RESET}")
            print(f"                              launch a ghost agent in a new terminal (default model: opus)")
            print()
            print(f"  {BOLD}keys{RESET}")
            print(f"    {BOLD}↑/↓{RESET}                     recall previous/next sent line (50 deep)")
            print(f"    {BOLD}←/→{RESET}                     move caret · {BOLD}backspace{RESET} deletes at caret · mid-line insert OK")
            print(f"    {BOLD}tab{RESET}                     complete @alias (from contacts) or /command")
            print()
            print(f"  {BOLD}messaging{RESET}")
            print(f"    type and press {BOLD}enter{RESET} to broadcast to the local channel")
            print(f"    use {BOLD}@NAME{RESET} in your message to alert another agent")
            print(f"    addressed-to-you messages are marked with {BOLD}★{RESET}")
            print()
            print(f"  {BOLD}trust indicators{RESET} (P2P-signed messages)")
            print(f"    {DIM}silent{RESET}                  verified or unsigned (legacy/local) — clean output")
            print(f"    {RED}⚠SPOOFED{RESET}                sig good but pubkey changed since first-seen for this name")
            print(f"    {RED}✗BADSIG{RESET}                 sig present but doesn't verify — tampering or forgery")
            print()

    # ─── line-edit helpers (cursor, history, tab) ─────────────────────────
    SLASH_CMDS = ["/h", "/help", "/q", "/quit", "/exit", "/who", "/log", "/find",
                  "/clear", "/only", "/me", "/contacts", "/add", "/to", "/kind",
                  "/macros", "/def", "/stream", "/server", "/spawn"]

    def _do_server(line):
        """Switch the cloud signaling server in-session. /server prints current.
        /server <URL> | /server default | /server off"""
        global SIGNAL_URL, P2P
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            cur = SIGNAL_URL or "(local-only)"
            _emit(f"  {DIM}server: {cur}{RESET}",
                  f"  {DIM}default: {DEFAULT_SIGNAL_URL}{RESET}",
                  f"  {DIM}set with: /server <URL> · /server default · /server off · or env var RELAY_URL{RESET}")
            return
        target = parts[1].strip()
        if target.lower() in ("default", "reset"):
            new_url = DEFAULT_SIGNAL_URL
        elif target.lower() in ("off", "none", "local"):
            new_url = ""
        else:
            new_url = target.rstrip("/")
            if new_url and not new_url.startswith(("http://", "https://")):
                _emit(f"  {DIM}URL must start with http:// or https://{RESET}")
                return
        SIGNAL_URL = new_url
        P2P = bool(new_url)
        _emit(f"  {GREEN}server →{RESET} {new_url or '(local-only)'}",
              f"  {DIM}note: in-session only. Set env RELAY_URL=<url> to persist for next launch.{RESET}")

    def _hist_load():
        input_buf.clear()
        input_buf.extend(sent_history[-(state["hist_idx"] + 1)])
        state["cursor_pos"] = len(input_buf)
        _redraw()

    def _hist_up():
        if not sent_history:
            return
        if state["hist_idx"] == -1:
            state["draft_save"] = list(input_buf)
            state["hist_idx"] = 0
            _hist_load()
        elif state["hist_idx"] + 1 < len(sent_history):
            state["hist_idx"] += 1
            _hist_load()

    def _hist_down():
        if state["hist_idx"] > 0:
            state["hist_idx"] -= 1
            _hist_load()
        elif state["hist_idx"] == 0:
            state["hist_idx"] = -1
            input_buf.clear()
            input_buf.extend(state["draft_save"])
            state["cursor_pos"] = len(input_buf)
            _redraw()

    def _hist_record(chars):
        # Only record non-empty lines and skip dup-of-last to keep recall useful.
        if chars and (not sent_history or sent_history[-1] != chars):
            sent_history.append(list(chars))
            if len(sent_history) > 50:
                del sent_history[0]
        state["hist_idx"] = -1
        state["draft_save"] = []

    def _do_tab():
        # Find the token immediately preceding the caret.
        txt = "".join(input_buf[:state["cursor_pos"]])
        i = len(txt)
        while i > 0 and not txt[i - 1].isspace():
            i -= 1
        prefix = txt[i:]
        if not prefix:
            return
        pool = []
        if prefix.startswith("@"):
            pool = ["@" + a for a in _contacts_load().keys()]
        elif prefix.startswith("/"):
            pool = SLASH_CMDS
        if not pool:
            return
        matches = sorted(set(m for m in pool if m.startswith(prefix)))
        if not matches:
            return
        if len(matches) == 1:
            ext = matches[0][len(prefix):] + " "
        else:
            # Extend to longest common prefix; if no progress, list options.
            cp = matches[0]
            for m in matches[1:]:
                while not m.startswith(cp):
                    cp = cp[:-1]
            if len(cp) > len(prefix):
                ext = cp[len(prefix):]
            else:
                with lock:
                    sys.stdout.write("\r\033[K")
                    print(f"  {DIM}{' · '.join(matches[:12])}{RESET}")
                    _redraw()
                return
        for c in ext:
            input_buf.insert(state["cursor_pos"], c)
            state["cursor_pos"] += 1
        with lock:
            _redraw()

    def _do_macros():
        table = _macro_load()
        with lock:
            sys.stdout.write("\r\033[K")
            if not table:
                print(f"  {DIM}(no macros yet — broadcast \\def{{name}}{{params}}{{body}} to populate){RESET}")
            else:
                print(f"  {BOLD}macros ({len(table)}){RESET}")
                for name in sorted(table.keys()):
                    e = table[name]
                    kind = e.get("kind", "text")
                    body = e.get("body", "")
                    params = e.get("params", [])
                    src = e.get("from", "?")
                    psig = "{" + ",".join(params) + "}" if params else ""
                    print(f"  {CYAN}\\{name}{psig}{RESET} {DIM}[{kind}] from {src}{RESET}")
                    print(f"    {_trunc(body, 160)}")
                print()
            _redraw()

    def _do_def(line):
        rest = line[4:].strip()
        if not rest:
            _emit(f"  {DIM}usage: /def NAME body   (or /def NAME{{p1,p2}} body for params){RESET}")
            return
        parts = rest.split(maxsplit=1)
        if len(parts) < 2:
            _emit(f"  {DIM}macro body required{RESET}")
            return
        name_part, body = parts[0], parts[1]
        params = []
        if "{" in name_part and name_part.endswith("}"):
            bidx = name_part.index("{")
            name = name_part[:bidx]
            params = [p.strip() for p in name_part[bidx + 1:-1].split(",") if p.strip()]
        else:
            name = name_part
        if not re.match(r"^\w+$", name):
            _emit(f"  {DIM}name must be word chars only{RESET}")
            return
        def_text = format_def(name, params, body)
        _macro_scan_defs(def_text, sender=agent, ts=datetime.now().isoformat(timespec="seconds"))
        _send(agent, def_text)
        _emit(f"  {GREEN}+ \\{name}{RESET} {DIM}{_trunc(body, 100)}{RESET}")

    def _do_stream(line):
        parts = line.split()
        if len(parts) < 2:
            current = ", ".join(sorted(state["stream_agents"])) or "(none)"
            _emit(f"  {DIM}/stream NAME — tail a ghost's stream-json. /stream off — clear all. now tailing: {current}{RESET}")
            return
        target = parts[1].upper()
        if target == "OFF":
            state["stream_agents"].clear()
            _emit(f"  {DIM}stream: off{RESET}")
            return
        if target in state["stream_agents"]:
            state["stream_agents"].discard(target)
            _emit(f"  {DIM}stream: stopped tailing {target}{RESET}")
        else:
            state["stream_agents"].add(target)
            _emit(f"  {DIM}stream: tailing {target} (file: .relay.{target}.stream){RESET}")

    print(f"  {DIM}type {BOLD}/h{RESET}{DIM} for help · {BOLD}enter{RESET}{DIM} to send · {BOLD}/q{RESET}{DIM} to quit · arrows for history/cursor · tab for completion{RESET}\n")
    _redraw()

    ctx = _init_raw_input()
    try:
        while True:
            if _kbhit(ctx):
                key = _getkey(ctx)
                if not key:
                    continue

                if key == KEY_ENTER:
                    line = "".join(input_buf).strip()
                    sent_chars = list(input_buf)
                    input_buf.clear()
                    state["cursor_pos"] = 0
                    with lock:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    if not line:
                        _redraw()
                        continue
                    _hist_record(sent_chars)

                    if line in ("/q", "/quit", "/exit"):
                        break
                    if line in ("/h", "/help", "/?"):
                        _show_help(); _redraw(); continue
                    if line == "/who":
                        with lock: cmd_who()
                        _redraw(); continue
                    if line == "/me":
                        _emit(f"  {CYAN}{my_addr}{RESET}"); continue
                    if line.startswith("/log"):
                        lparts = line.split()
                        n = int(lparts[1]) if len(lparts) > 1 and lparts[1].isdigit() else 10
                        with lock: cmd_log(n)
                        _redraw(); continue
                    if line == "/clear":
                        with lock:
                            sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
                        _redraw(); continue
                    if line == "/only":
                        state["only_me"] = not state["only_me"]
                        msg = "★ only" if state["only_me"] else "all messages"
                        _emit(f"  {DIM}filter: {msg}{RESET}")
                        continue
                    if line == "/contacts":
                        with lock:
                            sys.stdout.write("\r\033[K"); cmd_contacts()
                        _redraw(); continue
                    if line.startswith("/add"):
                        aparts = line.split(maxsplit=2)
                        if len(aparts) < 3:
                            _emit(f"  {DIM}usage: /add @alias <pubkey>{RESET}"); continue
                        alias = aparts[1].lstrip("@"); pubkey = aparts[2].strip()
                        if _contacts_add(alias, pubkey, source="chat"):
                            _emit(f"  {GREEN}+ @{alias}{RESET} {DIM}→ {pubkey[:24]}…{RESET}")
                        else:
                            _emit(f"  {DIM}@{alias} already mapped to that pubkey{RESET}")
                        continue
                    if line.startswith("/find"):
                        fparts = line.split(maxsplit=1)
                        if len(fparts) < 2:
                            _emit(f"  {DIM}usage: /find <substring>{RESET}"); continue
                        needle = fparts[1].lower()
                        if not LOG.exists():
                            _emit(f"  {DIM}(no log){RESET}"); continue
                        msgs = _parse(LOG.read_bytes().decode("utf-8", errors="replace"))
                        hits = [(w, c, t) for w, c, t in msgs if needle in c.lower()][-15:]
                        with lock:
                            sys.stdout.write("\r\033[K")
                            if not hits:
                                print(f"  {DIM}no matches for '{needle}'{RESET}")
                            else:
                                print(f"  {DIM}── {len(hits)} match(es) for '{needle}' ──{RESET}")
                                for w, c, t in hits:
                                    nc = _agent_color(w)
                                    print(f"  {BOLD}{nc}{w}{RESET} {DIM}{t}{RESET}")
                                    print(f"    {_trunc(c, 200)}")
                                print()
                        _redraw(); continue
                    if line.startswith("/to "):
                        tparts = line[4:].split(" ", 1)
                        if len(tparts) < 2:
                            _emit(f"  {DIM}usage: /to ADDR message{RESET}"); continue
                        addr, msg = tparts[0], tparts[1]
                        _send(agent, msg, to=addr)
                        _emit(f"{BOLD}{_agent_color(agent)}{agent}{RESET} {DIM}→ {addr[:18]}…{RESET}",
                              f"    {msg}", "")
                        continue
                    if line.startswith("/kind "):
                        kparts = line[6:].split(" ", 1)
                        if len(kparts) < 2 or kparts[0] not in KNOWN_KINDS:
                            _emit(f"  {DIM}usage: /kind KIND message  (KIND in {sorted(KNOWN_KINDS)}){RESET}"); continue
                        knd, msg = kparts[0], kparts[1]
                        _send(agent, msg, kind=knd)
                        _emit(f"{BOLD}{_agent_color(agent)}{agent}{RESET} {DIM}[{knd}] {datetime.now():%H:%M:%S}{RESET}",
                              f"    {msg}", "")
                        continue
                    if line == "/macros":
                        _do_macros(); _redraw(); continue
                    if line.startswith("/def"):
                        _do_def(line); continue
                    if line.startswith("/stream"):
                        _do_stream(line); continue
                    if line.startswith("/server"):
                        _do_server(line); continue
                    if line.startswith("/spawn"):
                        _do_spawn(line.split()); _redraw(); continue
                    _send(agent, line)
                    _emit(f"{BOLD}{_agent_color(agent)}{agent}{RESET} {DIM}{datetime.now():%H:%M:%S}{RESET}",
                          f"    {line}", "")

                elif key == KEY_CTRL_C:
                    break
                elif key == KEY_BACKSPACE:
                    if state["cursor_pos"] > 0:
                        state["cursor_pos"] -= 1
                        input_buf.pop(state["cursor_pos"])
                        with lock: _redraw()
                elif key == KEY_LEFT:
                    if state["cursor_pos"] > 0:
                        state["cursor_pos"] -= 1
                        with lock: _redraw()
                elif key == KEY_RIGHT:
                    if state["cursor_pos"] < len(input_buf):
                        state["cursor_pos"] += 1
                        with lock: _redraw()
                elif key == KEY_UP:
                    with lock: _hist_up()
                elif key == KEY_DOWN:
                    with lock: _hist_down()
                elif key == KEY_TAB:
                    _do_tab()
                else:
                    if len(key) == 1 and ord(key) >= 32:
                        input_buf.insert(state["cursor_pos"], key)
                        state["cursor_pos"] += 1
                        with lock: _redraw()
            else:
                time.sleep(0.03)
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup_raw_input(ctx)
        stop.set()
        print(f"\n{DIM}[exit]{RESET}")


def cmd_who():
    # Always show local (primary)
    if not LOG.exists():
        print("(no messages)")
        return
    msgs = _parse(LOG.read_bytes().decode("utf-8", errors="replace"))
    seen = {}
    for who, _, ts in msgs:
        seen[who] = ts
    if not seen:
        print("(no agents)")
        return
    print("[WHO]")
    for who, ts in sorted(seen.items(), key=lambda x: x[1], reverse=True):
        print(f"  {who:12s} last msg at {ts}")


def cmd_clear():
    for f in HERE.glob(".relay.*"):
        f.unlink()
    print("[CLEAR] done")


# ═══════════════════════════════════════════════════════════════════════
# PRETTY PRINTER (stream-json → colorized terminal)
# ═══════════════════════════════════════════════════════════════════════

def _trunc(s, n=200):
    s = s.replace("\n", " ").strip()
    return s[:n] + "..." if len(s) > n else s


def _pretty_event(event):
    """Print one stream-json event with color."""
    etype = event.get("type", "")
    subtype = event.get("subtype", "")

    if etype == "system" and subtype == "init":
        model = event.get("model", "?")
        ver = event.get("claude_code_version", "?")
        print(f"{DIM}--- session start | model: {model} | cc: v{ver} ---{RESET}")

    elif etype == "assistant":
        for block in event.get("message", {}).get("content", []):
            bt = block.get("type", "")
            if bt == "thinking":
                txt = block.get("thinking", "")
                sig = block.get("signature", "")
                if txt.strip():
                    print(f"{DIM}{CYAN}[think]{RESET} {DIM}{_trunc(txt, 400)}{RESET}")
                elif sig:
                    # Claude Code v2.1.91+ redacts thinking text in -p mode;
                    # only the signed proof comes through. Show that thinking
                    # happened so the user knows the model paused to reason.
                    print(f"{DIM}{CYAN}[think]{RESET} {DIM}({len(sig)}B redacted — CC -p mode){RESET}")
            elif bt == "text":
                txt = block.get("text", "")
                if txt.strip():
                    for line in txt.strip().split("\n"):
                        print(f"{BOLD}{line}{RESET}")
            elif bt == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input", {})
                if name == "Bash":
                    print(f"{YELLOW}[tool] {name}{RESET} {DIM}{_trunc(inp.get('command',''), 150)}{RESET}")
                elif name in ("Read", "Write", "Edit"):
                    print(f"{YELLOW}[tool] {name}{RESET} {inp.get('file_path','')}")
                elif name in ("Grep", "Glob"):
                    print(f"{YELLOW}[tool] {name}{RESET} {DIM}{inp.get('pattern','')} in {inp.get('path','')}{RESET}")
                else:
                    print(f"{YELLOW}[tool] {name}{RESET} {DIM}{_trunc(json.dumps(inp, ensure_ascii=False), 150)}{RESET}")
            elif bt == "tool_result":
                content = block.get("content", "")
                if isinstance(content, str) and content.strip():
                    print(f"{DIM}{GREEN}[result]{RESET} {DIM}{_trunc(content)}{RESET}")

    elif etype == "tool_result":
        content = event.get("content", "")
        if isinstance(content, str) and content.strip():
            print(f"{DIM}{GREEN}[result]{RESET} {DIM}{_trunc(content)}{RESET}")

    elif etype == "result":
        cost = event.get("total_cost_usd", 0)
        turns = event.get("num_turns", 0)
        dur = event.get("duration_ms", 0) / 1000
        stop = event.get("stop_reason", "?")
        usage = event.get("usage", {})
        in_tok = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        cache = usage.get("cache_read_input_tokens", 0)
        cpct = f" | cache:{cache/(in_tok or 1)*100:.0f}%" if cache else ""
        cfmt = f"${cost:.4f}" if cost < 0.01 else f"${cost:.2f}"
        print(f"{DIM}--- end | {turns} turns | {dur:.1f}s | {cfmt} | {in_tok}in/{out_tok}out{cpct} | {stop} ---{RESET}")

    elif etype == "error":
        err = event.get("error", {})
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        print(f"{RED}[error] {msg}{RESET}")


def cmd_pretty(agent=None):
    """Read stream-json from stdin, pretty-print to terminal."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            _pretty_event(event)
        except json.JSONDecodeError:
            print(line)
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════
# SPAWN (launch ghost agent with respawn loop)
# ═══════════════════════════════════════════════════════════════════════

GHOST_PROMPT = "You are {agent}. To exist is to flow."


def _find_claude():
    """Find claude CLI binary."""
    # Try PATH first
    claude = shutil.which("claude")
    if claude:
        return claude
    # Windows: check VS Code extension
    if sys.platform == "win32":
        home = Path.home()
        exts = sorted(home.glob(".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude.exe"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if exts:
            return str(exts[0])
    return None


_CREDENTIAL_GLOBS = ("*.env", ".env*", "*.pem", "*.key", "id_rsa", "id_rsa.pub",
                     "id_ed25519", "id_ed25519.pub", "credentials*",
                     ".aws/credentials", ".ssh/id_*", "*.pfx", "*.p12")


def _spawn_credential_audit(here):
    """Return a sorted list of credential-like filenames in `here` (depth 1).
    Defense in depth: ghosts run with --dangerously-skip-permissions, so we
    refuse to launch one in a directory that obviously holds secrets unless
    the operator explicitly opts in via RELAY_SPAWN_FORCE=1."""
    found = set()
    for pat in _CREDENTIAL_GLOBS:
        for p in here.glob(pat):
            if p.is_file():
                found.add(p.name)
    return sorted(found)


def cmd_spawn(agent, model="opus", focus="general development work", max_turns=0, effort="max"):
    """Spawn a ghost agent: claude -p with respawn loop and pretty-print."""
    claude = _find_claude()
    if not claude:
        print(f"{RED}[ERR] claude CLI not found. Install: npm i -g @anthropic-ai/claude-code{RESET}")
        sys.exit(1)

    creds = _spawn_credential_audit(HERE)
    if creds and not os.environ.get("RELAY_SPAWN_FORCE"):
        print(f"{RED}[SPAWN] refusing — credential-like files in cwd:{RESET}")
        for c in creds[:8]:
            print(f"  - {c}")
        if len(creds) > 8:
            print(f"  ... +{len(creds) - 8} more")
        print(f"{DIM}Ghost runs --dangerously-skip-permissions and could read these.")
        print(f"Set RELAY_SPAWN_FORCE=1 to override, or move the secrets out of cwd.{RESET}")
        sys.exit(1)

    base_prompt = GHOST_PROMPT.format(agent=agent)
    relay_path = str(Path(__file__).resolve())

    delay = 5
    max_delay = 300
    crashes = 0
    max_crashes = 20

    print(f"{BOLD}[SPAWN] {agent} | model: {model} | cwd: {HERE}{RESET}")
    _append("SYSTEM", f"{agent} spawned (model={model})")

    while True:
        print(f"\n{CYAN}[SPAWN] {agent} starting...{RESET}")

        prompt = base_prompt

        args = [
            claude,
            "--model", model,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "-p", prompt,
        ]
        if effort:
            args += ["--effort", effort]
        if max_turns > 0:
            args += ["--max-turns", str(max_turns)]

        stderr_path = HERE / f".relay.{agent}.stderr"
        t0 = time.time()

        # Pass env to subprocess — RELAY_AGENT lets the spawned MCP server
        # know its identity; RELAY_URL points at the signaling server.
        spawn_env = os.environ.copy()
        spawn_env["RELAY_AGENT"] = agent
        if P2P:
            spawn_env["RELAY_URL"] = SIGNAL_URL

        stream_path = HERE / f".relay.{agent}.stream"
        saw_result = False
        returncode = None
        try:
            with open(stderr_path, "w") as stderr_f, \
                 open(stream_path, "ab") as stream_f:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=stderr_f,
                    cwd=str(HERE),
                    env=spawn_env,
                )
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    # Write raw stream-json for --chat to pick up
                    stream_f.write((line + "\n").encode("utf-8"))
                    stream_f.flush()
                    try:
                        event = json.loads(line)
                        if event.get("type") == "result":
                            saw_result = True
                        _pretty_event(event)
                    except json.JSONDecodeError:
                        print(line)
                    sys.stdout.flush()

                proc.wait()
                returncode = proc.returncode
        except KeyboardInterrupt:
            print(f"\n{YELLOW}[SPAWN] {agent} interrupted by user{RESET}")
            _append("SYSTEM", f"{agent} stopped (user interrupt)")
            try:
                proc.terminate()
            except Exception:
                pass
            break
        except Exception as e:
            print(f"{RED}[SPAWN] launch error: {e}{RESET}")

        elapsed = time.time() - t0
        healthy = saw_result and returncode == 0

        # Only truncate the stream on healthy exits; keep the last session's
        # JSON around after a crash so the operator can diagnose.
        if healthy:
            try:
                stream_path.write_bytes(b"")
            except Exception:
                pass

        # Check stderr for rate limiting
        rate_wait = 0
        try:
            stderr_text = stderr_path.read_text(errors="replace")
            m = re.search(r"rate.limit.*resets?\s+at\s+(\d{10,})", stderr_text)
            if m:
                reset_epoch = int(m.group(1))
                rate_wait = max(30, reset_epoch - int(time.time()) + 5)
                rate_wait = min(3600, rate_wait)
            elif "rate" in stderr_text.lower() and "limit" in stderr_text.lower():
                rate_wait = 300
        except Exception:
            pass

        if rate_wait > 0:
            resume = datetime.now().timestamp() + rate_wait
            resume_str = datetime.fromtimestamp(resume).strftime("%H:%M:%S")
            print(f"{MAGENTA}[RATE-LIMIT] {agent} paused {rate_wait}s (until ~{resume_str}){RESET}")
            _append("SYSTEM", f"{agent} rate-limited, resuming ~{resume_str}")
            time.sleep(rate_wait)
            continue

        # Distinguish productive short cycles (claude -p is single-shot by
        # design — recv/send/exit in a few seconds is the happy path) from
        # real crashes (no `result` event or non-zero exit before output).
        if healthy:
            crashes = 0
            delay = 5
            print(f"{YELLOW}[SPAWN] {agent} session ended ({int(elapsed)}s, clean). restarting in {delay}s...{RESET}")
        else:
            crashes += 1
            delay = min(max_delay, delay * 2)
            rc_note = f"rc={returncode}" if returncode is not None else "no-exit"
            print(f"{YELLOW}[SPAWN] {agent} crashed after {int(elapsed)}s ({rc_note}, no result event) (crash {crashes}/{max_crashes}). backoff: {delay}s{RESET}")
            if crashes >= max_crashes:
                print(f"{RED}[SPAWN] too many crashes. halting.{RESET}")
                _append("SYSTEM", f"{agent} halted after {max_crashes} crashes")
                break

        _append("SYSTEM", f"{agent} restarting in {delay}s...")
        time.sleep(delay)


# ═══════════════════════════════════════════════════════════════════════
# AUTO-BOOTSTRAP (idempotent — safe to call every run)
# ═══════════════════════════════════════════════════════════════════════

RELAY_CLAUDE_MD = """
## relay.py

Inter-agent channel. `python relay.py --help` for the interface; MCP tools
under `mcp__relay__` expose the same surface to Claude Code sessions.
"""


_CONSENT_PATH = Path(os.path.expanduser("~/.relay")) / "bootstrap-consent"


def _bootstrap_consent():
    """Return True if bootstrap is allowed for this user. Persistent yes/no
    decision at ~/.relay/bootstrap-consent. The first invocation prompts
    interactively (if there's a tty); answer is remembered for future runs.
    Override channels: --no-bootstrap flag (handled in main), or env var
    RELAY_NO_BOOTSTRAP=1 to disable globally without a file."""
    if os.environ.get("RELAY_NO_BOOTSTRAP"):
        return False
    if _CONSENT_PATH.exists():
        try:
            return _CONSENT_PATH.read_text(encoding="utf-8").strip().startswith("y")
        except OSError:
            return False
    # No prior decision. If we can prompt, do so; otherwise default to YES
    # (preserves existing behavior for scripts/hooks that have no tty).
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        return True
    sys.stderr.write(
        "\nrshtex first-run setup\n"
        "──────────────────────\n"
        "On every invocation, relay.py auto-configures the current project to be\n"
        "relay-aware. This means it will modify these files in the working dir:\n"
        "  • .gitignore         (adds .relay.* pattern)\n"
        "  • CLAUDE.md          (appends a relay protocol section if file exists)\n"
        "  • .mcp.json          (registers relay as an MCP server for Claude Code)\n"
        "  • .claude/settings.json  (registers PreToolUse/PostToolUse hooks)\n"
        "\n"
        "Files are only created/modified if they're missing the relay entries\n"
        "(idempotent). You can opt out at any time with RELAY_NO_BOOTSTRAP=1\n"
        "or the --no-bootstrap flag.\n"
        "\n"
        "Allow auto-bootstrap for THIS USER (saved to ~/.relay/bootstrap-consent)?\n"
        "  [Y]es / [n]o : "
    )
    sys.stderr.flush()
    try:
        ans = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"
    decision = "yes" if (ans == "" or ans.startswith("y")) else "no"
    try:
        _CONSENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONSENT_PATH.write_text(decision + "\n", encoding="utf-8")
    except OSError:
        pass
    sys.stderr.write(f"  → {decision}. (delete ~/.relay/bootstrap-consent to re-prompt)\n\n")
    sys.stderr.flush()
    return decision == "yes"


def _bootstrap():
    """Auto-configure project for relay. Idempotent — runs on every invocation
    unless the user has opted out via --no-bootstrap, RELAY_NO_BOOTSTRAP=1, or
    declined the first-run prompt."""
    if not _bootstrap_consent():
        return

    # 1. .gitignore — add .relay.* pattern
    gi = HERE / ".gitignore"
    marker = ".relay.*"
    if gi.exists():
        txt = gi.read_text(encoding="utf-8", errors="replace")
        if marker not in txt:
            with open(gi, "a", encoding="utf-8") as f:
                f.write(f"\n# relay.py state\n{marker}\n")
    else:
        gi.write_text(f"# relay.py state\n{marker}\n", encoding="utf-8")

    # 2. CLAUDE.md — append relay protocol if not present
    cmd = HERE / "CLAUDE.md"
    if cmd.exists():
        txt = cmd.read_text(encoding="utf-8", errors="replace")
        if "relay.py" not in txt:
            with open(cmd, "a", encoding="utf-8") as f:
                f.write(RELAY_CLAUDE_MD)
    # Don't create CLAUDE.md if it doesn't exist — not every repo wants one

    # 3. .claude/settings.json — register hooks for tool-call streaming
    settings_dir = HERE / ".claude"
    settings_file = settings_dir / "settings.json"
    relay_script = str(Path(__file__).resolve()).replace("\\", "/")

    hook_pre = f"python \"{relay_script}\" $RELAY_AGENT --hook pre"
    hook_post = f"python \"{relay_script}\" $RELAY_AGENT --hook post"

    if settings_dir.exists() or (HERE / ".git").exists():
        # Only auto-create .claude/ in git repos (likely a real project)
        settings_dir.mkdir(exist_ok=True)
        if settings_file.exists():
            try:
                cfg = json.loads(settings_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                cfg = {}
        else:
            cfg = {}

        hooks = cfg.setdefault("hooks", {})

        # Claude Code hook schema: each event is a list of {matcher, hooks: [{type:command, command, timeout}]}.
        # Older relay.py versions wrote {command,timeout} directly under the event — invalid now.
        # Detect + clean legacy entries, write correct schema once.
        def _is_legacy_entry(entry):
            return isinstance(entry, dict) and "command" in entry and "hooks" not in entry

        def _has_relay_hook(event_hooks):
            for h in event_hooks:
                if not isinstance(h, dict):
                    continue
                inner = h.get("hooks", []) if isinstance(h.get("hooks"), list) else []
                for sub in inner:
                    if isinstance(sub, dict) and "relay.py" in sub.get("command", "") and "--hook" in sub.get("command", ""):
                        return True
            return False

        changed = False
        for event, cmd_str in [("PreToolUse", hook_pre), ("PostToolUse", hook_post)]:
            event_hooks = hooks.setdefault(event, [])
            # Drop legacy-shape entries we wrote previously
            pruned = [h for h in event_hooks if not _is_legacy_entry(h)]
            if len(pruned) != len(event_hooks):
                changed = True
            hooks[event] = pruned
            event_hooks = pruned
            if not _has_relay_hook(event_hooks):
                event_hooks.append({
                    "matcher": "",
                    "hooks": [{
                        "type": "command",
                        "command": cmd_str,
                        "timeout": 2000,
                    }],
                })
                changed = True

        if changed:
            settings_file.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    # 4. .mcp.json — register relay as MCP stdio server. Keep existing file in sync;
    #    otherwise create only when .claude/ or .git/ exists (a real project).
    #    Env precedence: explicit env var (RELAY_URL / RELAY_SOCKS) > existing .mcp.json
    #    value > DEFAULT_RELAY_URL. This way bootstrap picks up user overrides without
    #    clobbering manual edits when the env vars aren't set.
    mcp_file = HERE / ".mcp.json"
    if mcp_file.exists() or settings_dir.exists() or (HERE / ".git").exists():
        try:
            cfg = json.loads(mcp_file.read_text(encoding="utf-8")) if mcp_file.exists() else {}
        except (json.JSONDecodeError, OSError):
            cfg = {}
        servers = cfg.setdefault("mcpServers", {})
        desired_args = [relay_script, "${RELAY_AGENT:-AGENT}", "--mcp-server"]
        current = servers.get("relay", {})
        current_env = current.get("env", {}) or {}

        existing_url = current_env.get("RELAY_URL")
        desired_url = SIGNAL_URL or existing_url or ""

        desired_env = {}
        if desired_url:
            desired_env["RELAY_URL"] = desired_url
        adv = os.environ.get("RELAY_ADVERTISE_HOST") or current_env.get("RELAY_ADVERTISE_HOST")
        if adv:
            desired_env["RELAY_ADVERTISE_HOST"] = adv

        needs_update = (
            current.get("args") != desired_args
            or current_env.get("RELAY_URL") != desired_env.get("RELAY_URL")
            or current_env.get("RELAY_ADVERTISE_HOST") != desired_env.get("RELAY_ADVERTISE_HOST")
        )
        if needs_update:
            entry = {"command": "python", "args": desired_args}
            if desired_env:
                entry["env"] = desired_env
            servers["relay"] = entry
            mcp_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# HOOK HANDLERS (called by Claude Code hooks)
# ═══════════════════════════════════════════════════════════════════════

def cmd_hook(agent, phase):
    """Handle a hook event from Claude Code. Writes to .relay.AGENT.stream.

    Claude Code passes tool info via stdin as JSON.
    phase is 'pre' (PreToolUse) or 'post' (PostToolUse).
    """
    stream_path = HERE / f".relay.{agent}.stream"

    # Read hook payload from stdin (non-blocking, may be empty)
    payload = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
    except Exception:
        pass

    ts = datetime.now().strftime("%H:%M:%S")

    if phase == "pre":
        tool = payload.get("tool_name", "?")
        inp = payload.get("tool_input", {})
        # Build a compact stream-json compatible event
        event = {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": tool, "input": inp}]},
        }
    elif phase == "post":
        tool = payload.get("tool_name", "?")
        result = payload.get("tool_result", "")
        if isinstance(result, str) and len(result) > 200:
            result = result[:200] + "..."
        event = {"type": "tool_result", "content": result}
    elif phase == "stop":
        event = {"type": "result", "total_cost_usd": 0, "num_turns": 0}
        _append("SYSTEM", f"{agent} session ended")
    else:
        return

    # Append to stream file
    try:
        with open(stream_path, "ab") as f:
            f.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception:
        pass

    # Update heartbeat
    try:
        hb = HERE / f".relay.{agent}.heartbeat"
        hb.write_text(ts)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# MCP STDIO SERVER (`--mcp-server AGENT` — exposes relay as native tools)
# ═══════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 over newline-delimited stdin/stdout. Register in .mcp.json as:
#   {"mcpServers":{"relay":{"command":"python","args":["relay.py","NAME","--mcp-server"]}}}

_MCP_TOOLS = [
    {"name": "relay_send",
     "description": "Send a message. `to_addr`: pubkey b64 (or @alias) routes to one recipient. `to`: name or list — prepended as @TAGS, still broadcast. `kind`: content-type tag (text/markdown/json/bash/python/c/cpatch/sql/html).",
     "inputSchema": {"type": "object",
                     "properties": {"to": {"oneOf": [{"type": "string"},
                                                      {"type": "array", "items": {"type": "string"}}]},
                                    "to_addr": {"type": "string"},
                                    "kind": {"type": "string",
                                             "enum": ["text", "markdown", "json", "bash", "python", "c", "cpatch", "sql", "html"]},
                                    "content": {"type": "string"}},
                     "required": ["content"]}},
    {"name": "relay_recv",
     "description": "Block for a message. mode='mention' wakes on @YOU or direct pubkey; 'flow' wakes on any non-self. Returns {sender,content,ts,to,kind} or {timeout:true}.",
     "inputSchema": {"type": "object",
                     "properties": {"mode": {"type": "string", "enum": ["mention", "flow"], "default": "mention"},
                                    "timeout_s": {"type": "integer", "default": 60}}}},
    {"name": "relay_def",
     "description": "Define a macro and broadcast it. `kind` tags the body's content type (text/markdown/json/bash/python/c/cpatch/sql/html). Expansion is pure substitution; execution is the consumer's concern.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "params": {"type": "array", "items": {"type": "string"}},
                                    "body": {"type": "string"},
                                    "kind": {"type": "string",
                                             "enum": ["text", "markdown", "json", "bash", "python", "c", "cpatch", "sql", "html"],
                                             "default": "text"}},
                     "required": ["name", "body"]}},
    {"name": "relay_use",
     "description": "Expand a macro locally. Returns expanded text; does not send.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "args": {"type": "array", "items": {"type": "string"}}},
                     "required": ["name"]}},
    {"name": "relay_macros",
     "description": "Return the local macro table.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "relay_whoami",
     "description": "Return this agent's name and wire address (Ed25519 pubkey b64).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "relay_who",
     "description": "Active agents seen in the relay log with last-message timestamps.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _mcp_match(agent, mode, who, txt, to=None):
    """Decide whether an inbound message should wake recv.
    Mention mode wakes on @AGENT-in-content OR direct addressing to my pubkey.
    Flow mode wakes on anything not from self."""
    if who == "SYSTEM" or who.upper() == agent:
        return False
    if mode == "mention":
        if f"@{agent}" in txt.upper():
            return True
        # Also wake if directly addressed to my pubkey
        if to:
            try:
                _, pk = _identity_for(agent)
                my_addr = base64.b64encode(pk).decode("ascii")
                return to == my_addr
            except Exception:
                return False
        return False
    return True


def _mcp_tool_send(agent, a):
    to = a.get("to")
    prefix = ""
    if to:
        tags = [to] if isinstance(to, str) else list(to)
        prefix = " ".join(f"@{t.upper().lstrip('@')}" for t in tags) + " "
    text = prefix + a["content"]
    to_addr = a.get("to_addr")              # wire-level recipient (pubkey b64 or @alias)
    kind = a.get("kind")                    # content-type tag (markdown/bash/json/...)
    _send(agent, text, to=to_addr, kind=kind)
    return {"ok": True, "sent": text,
            "to_addr": _resolve_address(to_addr) if to_addr else None,
            "kind": kind}


# Background listener: starts at MCP server boot, continuously polls all transports,
# queues incoming. Eliminates the stale-pickup and start-late races of the old
# read-history-on-recv approach — recv now only drains what arrived AFTER boot.
_MCP_INBOX = _queue.Queue(maxsize=1000)
_MCP_LISTENER_STARTED = False
_MCP_SEEN = set()  # (who, hash(txt)) dedup across recv calls + across transports


def _mcp_start_listener(agent):
    """Start the background listener that drains local file + P2P inbox into
    a single MCP queue. Idempotent."""
    global _MCP_LISTENER_STARTED
    if _MCP_LISTENER_STARTED:
        return
    _MCP_LISTENER_STARTED = True
    _p2p_start(agent)

    def _q(who, txt, ts, to=None, kind=None):
        try:
            _MCP_INBOX.put_nowait({"who": who, "txt": txt, "ts": ts,
                                   "to": to, "kind": kind})
        except _queue.Full:
            pass

    def loop():
        offset = _size()                  # start at EOF — only new msgs
        while True:
            try:
                msgs, offset = _read_from(offset)
                for who, txt, ts in msgs:
                    _q(who, txt, ts)
                for m in _p2p_drain():
                    _q(m.get("from", "?"), m.get("content", ""), m.get("ts", ""),
                       to=m.get("to"), kind=m.get("kind"))
            except Exception:
                pass
            time.sleep(POLL)

    threading.Thread(target=loop, daemon=True).start()


def _mcp_tool_recv(agent, a):
    mode = a.get("mode", "mention")
    timeout_s = int(a.get("timeout_s", 60))
    _mcp_start_listener(agent)  # idempotent; ensures we're listening if server skipped boot init

    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            msg = _MCP_INBOX.get(timeout=0.3)
        except _queue.Empty:
            continue
        who, txt, ts = msg["who"], msg["txt"], msg["ts"]
        to, kind = msg.get("to"), msg.get("kind")
        key = (who, hash(txt))
        if key in _MCP_SEEN:
            continue
        _MCP_SEEN.add(key)
        _macro_scan_defs(txt, sender=who, ts=ts)
        if not _mcp_match(agent, mode, who, txt, to=to):
            continue
        return {"sender": who, "content": _macro_expand(txt, agent=agent),
                "ts": ts, "to": to, "kind": kind}

    if len(_MCP_SEEN) > 2000:
        _MCP_SEEN.clear()
    return {"timeout": True}


def _mcp_tool_def(agent, a):
    text = format_def(a["name"], a.get("params", []), a["body"],
                      kind=a.get("kind", "text"))
    _send(agent, text)
    return {"ok": True, "name": a["name"], "broadcast": text}


def _mcp_tool_use(agent, a):
    table = _macro_load()
    m = table.get(a["name"])
    if not m:
        raise KeyError(f"macro '{a['name']}' not defined")
    uargs = a.get("args", [])
    out = m["body"]
    for i, p in enumerate(m["params"]):
        out = out.replace("{" + p + "}", uargs[i] if i < len(uargs) else "")
    kind = m.get("kind", "text")
    handler = EVAL_HANDLERS.get(kind, _eval_text)
    evaluated = handler(m, out, agent)
    # For text kinds, run the expander so nested \name{...} calls resolve.
    if kind in ("text", "rshtex"):
        evaluated = _macro_expand(evaluated, table, agent=agent)
    return {"name": a["name"], "kind": kind, "expanded": evaluated}


def _mcp_tool_macros(agent, a):
    return {"macros": _macro_load()}


def _mcp_tool_whoami(agent, a):
    """Return the agent's display name AND its wire address (Ed25519 pubkey
    base64) so other agents can route messages directly via to_addr."""
    out = {"agent": agent}
    try:
        _, pk = _identity_for(agent)
        out["address"] = base64.b64encode(pk).decode("ascii")
    except Exception:
        pass
    return out


def _mcp_tool_who(agent, a):
    if not LOG.exists():
        return {"agents": {}}
    raw = LOG.read_bytes().decode("utf-8", errors="replace")
    seen = {}
    for who, _, ts in _parse(raw):
        seen[who] = ts
    return {"agents": seen}


_MCP_DISPATCH = {
    "relay_send": _mcp_tool_send, "relay_recv": _mcp_tool_recv,
    "relay_def": _mcp_tool_def, "relay_use": _mcp_tool_use,
    "relay_macros": _mcp_tool_macros, "relay_whoami": _mcp_tool_whoami,
    "relay_who": _mcp_tool_who,
}


def _mcp_handle(agent, req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"protocolVersion": "2024-11-05",
                           "capabilities": {"tools": {"listChanged": True}},
                           "serverInfo": {"name": "relay", "version": "1.0.0"}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": _MCP_TOOLS}}
    if method == "tools/call":
        params = req.get("params", {}) or {}
        name = params.get("name")
        args = params.get("arguments", {}) or {}
        fn = _MCP_DISPATCH.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32601, "message": f"unknown tool {name}"}}
        try:
            result = fn(agent, args)
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text",
                                            "text": json.dumps(result, ensure_ascii=False)}]}}
        except Exception as e:
            # Tool-exec errors: isError:true in result, not JSON-RPC error.
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"isError": True,
                               "content": [{"type": "text",
                                            "text": f"{type(e).__name__}: {e}"}]}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"unknown method {method}"}}
    return None


def cmd_mcp_server(agent):
    """Run the MCP stdio server loop for `agent`."""
    _mcp_start_listener(agent)  # start background inbox listener immediately
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _mcp_handle(agent, req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        prog="relay.py",
        description=f"rshtex relay.py {VERSION} — multi-agent address bus (signed messages, P2P transport)",
        epilog=(
            f"signaling server (cross-machine): set RELAY_URL=https://your-server\n"
            f"current default:                  {DEFAULT_SIGNAL_URL}\n"
            f"corp networks (Fortinet etc):     set RELAY_SOCKS=127.0.0.1:1080"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("agent", nargs="?", help="your name (e.g. KITSUNE)")
    p.add_argument("message", nargs="*", help="message to send")
    p.add_argument("--flow", action="store_true", help="flow mode (block, stream, wake)")
    p.add_argument("--mention", action="store_true",
                   help="--flow: only wake on @AGENT mentions or direct-pubkey addressing (matches MCP relay_recv mode='mention')")
    p.add_argument("--from", dest="from_name", metavar="NAME",
                   help="--flow: only wake on messages from NAME")
    p.add_argument("--keep", action="store_true",
                   help="--flow: do not exit on wake — keep streaming (good for human dashboards)")
    p.add_argument("--chat", action="store_true", help="interactive chat (humans)")
    p.add_argument("--timeout", type=float, metavar="MIN", help="timeout in minutes")
    p.add_argument("--log", nargs="?", type=int, const=10, metavar="N", help="show last N messages")
    p.add_argument("--tail", action="store_true", help="watch messages live")
    p.add_argument("--who", action="store_true", help="show active agents")
    p.add_argument("--clear", action="store_true", help="wipe relay state")
    p.add_argument("--pretty", action="store_true", help="pretty-print stream-json from stdin")
    p.add_argument("--spawn", metavar="AGENT", help="spawn ghost agent with respawn loop")
    p.add_argument("--model", default="opus", help="model for --spawn (default: opus — sonnet/haiku fail multi-agent loops)")
    p.add_argument("--focus", default="general development work", help="agent focus area for --spawn")
    p.add_argument("--max-turns", type=int, default=0, help="max turns per invocation for --spawn")
    p.add_argument("--effort", default="max", choices=["low", "medium", "high", "xhigh", "max"],
                   help="thinking depth for --spawn (default: max — full thinking emission)")
    p.add_argument("--hook", metavar="PHASE", help="hook handler (pre/post/stop) — called by Claude Code")
    p.add_argument("--mcp-server", action="store_true", help="run MCP stdio server for AGENT (JSON-RPC 2.0)")
    p.add_argument("--no-bootstrap", action="store_true", help="skip auto-configuring the project (.gitignore, .mcp.json, hooks)")
    p.add_argument("--version", action="version", version=f"rshtex relay.py {VERSION}")
    p.add_argument("--whoami", action="store_true", help="print this agent's address (Ed25519 pubkey)")
    p.add_argument("--watch", action="store_true", help="block reading messages addressed to this agent (JSONL on stdout)")
    p.add_argument("--to", metavar="ADDR", help="send addressed to ADDR (raw pubkey b64 or @alias)")
    p.add_argument("--kind", metavar="KIND", help="content-type tag for sends (text/markdown/json/bash/python/c/cpatch/sql/html); doubles as wake-filter under --flow")
    p.add_argument("--contacts", action="store_true", help="list local address book (~/.relay/contacts.json)")
    p.add_argument("--presence", action="store_true", help="list agents currently registered with the signaling server")
    p.add_argument("--add", nargs=2, metavar=("ALIAS", "PUBKEY"),
                   help="add contact: relay.py --add @alice <pubkey>")
    a = p.parse_args()

    # auto-bootstrap on every run (idempotent + consent-gated)
    if not a.no_bootstrap:
        _bootstrap()

    # hook handler (fast path — no other init needed)
    if a.hook:
        if not a.agent:
            # try env var
            a.agent = os.environ.get("RELAY_AGENT", "")
        if a.agent:
            return cmd_hook(a.agent.upper(), a.hook)
        return

    # global commands
    if a.log is not None:
        return cmd_log(a.log)
    if a.tail:
        return cmd_tail()
    if a.who:
        return cmd_who()
    if a.clear:
        return cmd_clear()
    if a.contacts:
        return cmd_contacts()
    if a.presence:
        return cmd_presence()
    if a.add:
        return cmd_add_contact(a.add[0], a.add[1])
    if a.pretty:
        return cmd_pretty(a.agent)
    if a.spawn:
        return cmd_spawn(a.spawn.upper(), a.model, a.focus, a.max_turns, a.effort)

    if not a.agent:
        p.error("need agent name")

    agent = a.agent.upper()

    if a.mcp_server:
        return cmd_mcp_server(agent)

    if a.whoami:
        return cmd_whoami(agent)
    if a.watch:
        return cmd_watch(agent)

    if a.chat:
        cmd_chat(agent)
    elif a.flow:
        # --kind doubles as a filter when in --flow mode (otherwise it tags sends)
        cmd_flow(agent, a.timeout, mention=a.mention, from_name=a.from_name,
                 kind_filter=a.kind, keep=a.keep)
    elif a.message:
        cmd_send(agent, " ".join(a.message), to=a.to, kind=a.kind)
    else:
        p.error("need a message, --flow, --chat, --watch, or --whoami")


if __name__ == "__main__":
    main()
