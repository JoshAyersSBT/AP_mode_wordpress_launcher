#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import posixpath
import re
import shlex
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import paramiko


# ---------------------------
# SSH helpers
# ---------------------------

@dataclass
class RunResult:
    code: int
    out: str
    err: str

def ssh_connect(host: str, user: str, port: int, key: str | None, password: str | None) -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = dict(hostname=host, username=user, port=port, timeout=12)
    if key:
        kwargs["key_filename"] = key
    if password:
        kwargs["password"] = password
    cli.connect(**kwargs)
    return cli

def ssh_run(ssh: paramiko.SSHClient, cmd: str) -> RunResult:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return RunResult(code=code, out=out, err=err)

def sftp_read_text(sftp: paramiko.SFTPClient, path: str, max_bytes: int = 512_000) -> str:
    # Read at most max_bytes to avoid huge binaries
    with sftp.open(path, "rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="replace")


# ---------------------------
# Endpoint discovery
# ---------------------------

ASSET_EXTS = {
    ".html", ".htm", ".css", ".js", ".mjs",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".json", ".txt", ".map", ".woff", ".woff2", ".ttf", ".eot",
}

TEXT_EXTS = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".txt", ".map"}

def is_asset(path: str) -> bool:
    ext = os.path.splitext(path.lower())[1]
    return ext in ASSET_EXTS

def is_text(path: str) -> bool:
    ext = os.path.splitext(path.lower())[1]
    return ext in TEXT_EXTS

def norm_web_path(p: str) -> str:
    # normalize to URL path; ensure leading slash
    p = p.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    # collapse // and remove /./
    p = re.sub(r"/{2,}", "/", p)
    p = p.replace("/./", "/")
    return p

def discover_files(ssh: paramiko.SSHClient, root_dir: str) -> List[str]:
    # Robust: use find and print null-delimited
    cmd = f"find {shlex.quote(root_dir)} -type f -print"
    r = ssh_run(ssh, cmd)
    if r.code != 0:
        raise RuntimeError(f"find failed: {r.err.strip()}")
    files = [line.strip() for line in r.out.splitlines() if line.strip()]
    return files

def rel_from_root(root_dir: str, abs_path: str) -> str:
    # abs_path and root_dir are posix paths
    if abs_path.startswith(root_dir.rstrip("/") + "/"):
        return abs_path[len(root_dir.rstrip("/")) + 1 :]
    return abs_path

HREF_RE = re.compile(r"""(?is)\b(?:href|src)\s*=\s*["']([^"']+)["']""")
FORM_ACTION_RE = re.compile(r"""(?is)\baction\s*=\s*["']([^"']+)["']""")
FETCH_RE = re.compile(r"""(?is)\bfetch\s*\(\s*["']([^"']+)["']""")
XHR_RE = re.compile(r"""(?is)\bopen\s*\(\s*["'](?:GET|POST|PUT|DELETE|PATCH)["']\s*,\s*["']([^"']+)["']""")

def extract_candidate_paths(text: str) -> Set[str]:
    out: Set[str] = set()

    for m in HREF_RE.finditer(text):
        out.add(m.group(1).strip())
    for m in FORM_ACTION_RE.finditer(text):
        out.add(m.group(1).strip())
    for m in FETCH_RE.finditer(text):
        out.add(m.group(1).strip())
    for m in XHR_RE.finditer(text):
        out.add(m.group(1).strip())

    # Filter out obvious external urls, anchors, mailto, data
    cleaned: Set[str] = set()
    for u in out:
        if not u or u.startswith("#"):
            continue
        if u.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:")):
            continue
        # strip query/fragment (we can still keep base)
        u = u.split("#", 1)[0]
        cleaned.add(u)
    return cleaned

def urlify_static(rel_path: str) -> str:
    # If captive-portal is DocumentRoot, then rel_path maps to "/rel_path".
    # Special-case index.html -> "/"
    rp = rel_path.replace("\\", "/")
    if rp.lower() == "index.html":
        return "/"
    return norm_web_path(rp)

def build_endpoint_set(
    ssh: paramiko.SSHClient,
    root_dir: str,
    *,
    parse_linked: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Returns (static_endpoints, discovered_routes_from_html_js)
    static_endpoints: url paths for every file under root_dir
    discovered_routes: additional candidate URL paths found inside HTML/JS
    """
    files = discover_files(ssh, root_dir)
    assets = [f for f in files if is_asset(f)]
    rels = [rel_from_root(root_dir, f) for f in assets]

    static_eps: Set[str] = set(urlify_static(rp) for rp in rels)

    linked: Set[str] = set()
    if parse_linked:
        sftp = ssh.open_sftp()
        try:
            for abs_path in assets:
                if not is_text(abs_path):
                    continue
                # only parse "reasonable sized" text files
                try:
                    txt = sftp_read_text(sftp, abs_path)
                except Exception:
                    continue
                cands = extract_candidate_paths(txt)
                for u in cands:
                    # make relative urls look like absolute root paths
                    # - "./page.html" -> "/page.html"
                    # - "page.html" -> "/page.html"
                    # - "/api/status" stays
                    if u.startswith("/"):
                        linked.add(norm_web_path(u))
                    else:
                        u2 = u.lstrip("./")
                        linked.add(norm_web_path(u2))
        finally:
            sftp.close()

    # Remove anything that looks like a file that isn't in our tree (still testable, but noisy)
    # We'll keep both: static endpoints always; linked endpoints only if it doesn't look like a file missing.
    static_list = sorted(static_eps)
    linked_list = sorted(linked - static_eps)

    return static_list, linked_list


# ---------------------------
# Monitor service discovery
# ---------------------------

PORT_RE = re.compile(r"(?i)\bport\b\s*[:=]\s*(\d{2,5})")
FLASK_RUN_RE = re.compile(r"(?i)\b--port\s+(\d{2,5})")
LISTEN_RE = re.compile(r":(\d{2,5})\b")

def guess_monitor_port_from_unit_text(unit_text: str) -> Optional[int]:
    # Common patterns:
    #   --port 5050
    #   PORT=5050
    #   port: 5050
    m = FLASK_RUN_RE.search(unit_text)
    if m:
        return int(m.group(1))
    m = PORT_RE.search(unit_text)
    if m:
        return int(m.group(1))
    return None

def get_unit_text(ssh: paramiko.SSHClient, service_name: str) -> str:
    r = ssh_run(ssh, f"systemctl cat {shlex.quote(service_name)} 2>/dev/null || true")
    return r.out or ""

def find_listening_ports(ssh: paramiko.SSHClient) -> List[int]:
    # Look at listening TCP ports and return a unique list (ints).
    # This is a fallback: we’ll later probe likely monitor ports.
    r = ssh_run(ssh, "ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null || true")
    ports: Set[int] = set()
    for line in r.out.splitlines():
        for m in LISTEN_RE.finditer(line):
            p = int(m.group(1))
            if 1 <= p <= 65535:
                ports.add(p)
    return sorted(ports)

def choose_monitor_ports(ssh: paramiko.SSHClient) -> List[int]:
    candidates: List[int] = []

    # Try common service names you’ve used (“monitor”, “lms-monitor”, “flask” etc.)
    service_names = ["monitor.service", "lms-monitor.service", "lms_monitor.service", "lms.service"]
    for svc in service_names:
        txt = get_unit_text(ssh, svc)
        if not txt.strip():
            continue
        p = guess_monitor_port_from_unit_text(txt)
        if p and p not in candidates:
            candidates.append(p)

    # If nothing found, fall back to common ports and “what’s listening”
    common = [5000, 5050, 8000, 8080, 8888]
    for p in common:
        if p not in candidates:
            candidates.append(p)

    listening = find_listening_ports(ssh)
    # Prefer interesting non-privileged ports that are actually listening
    for p in listening:
        if p >= 1024 and p not in candidates:
            candidates.append(p)

    # Limit to a reasonable set
    return candidates[:12]


# ---------------------------
# Test generation
# ---------------------------

TEST_TEMPLATE = r'''# AUTO-GENERATED by generate_remote_endpoint_tests.py
# Target: captive portal + monitor endpoints

from __future__ import annotations

import os
import socket
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pytest


BASE_URL = os.environ.get("CAPTIVE_BASE_URL", "{base_url_default}").rstrip("/") + "/"
# Monitor is optional; tests will probe candidate ports
MONITOR_HOST = os.environ.get("MONITOR_HOST", "{monitor_host_default}")
MONITOR_PORTS = {monitor_ports}


def _http_get(path: str, *, timeout: float = 3.5):
    url = urljoin(BASE_URL, path.lstrip("/"))
    req = Request(url, headers={{"User-Agent": "pytest-endpoint-probe"}})
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read(4096)  # small sample
        return resp.status, dict(resp.headers), body


@pytest.mark.parametrize("path", {static_endpoints})
def test_captive_portal_static_endpoints_return_200(path: str):
    status, headers, body = _http_get(path)
    assert status == 200, f"Expected 200 for {{path}} but got {{status}}"
    assert body is not None


@pytest.mark.parametrize("path", {linked_endpoints})
def test_captive_portal_linked_routes_are_reachable(path: str):
    # Linked routes may be real pages or API-style endpoints.
    # Accept 200 or 302 (redirect) to avoid false failures on login/captive flows.
    try:
        status, headers, body = _http_get(path)
    except HTTPError as e:
        # Some stacks use 401/403 for guarded endpoints; treat as reachable.
        assert e.code in (200, 301, 302, 401, 403), f"Unexpected HTTP {{e.code}} for {{path}}"
        return
    assert status in (200, 301, 302, 401, 403), f"Unexpected status {{status}} for {{path}}"


def _tcp_connectable(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.parametrize("port", MONITOR_PORTS)
def test_monitor_port_listening_or_http(port: int):
    # First: ensure port is listening
    if not _tcp_connectable(MONITOR_HOST, port, timeout=1.2):
        pytest.skip(f"Monitor not listening on {{MONITOR_HOST}}:{{port}}")

    # Second: try HTTP GET on root (many monitor UIs are Flask)
    url = f"http://{{MONITOR_HOST}}:{{port}}/"
    req = Request(url, headers={{"User-Agent": "pytest-monitor-probe"}})
    try:
        with urlopen(req, timeout=3.5) as resp:
            body = resp.read(4096)
            assert resp.status in (200, 301, 302, 401, 403), f"Unexpected status {{resp.status}} for {{url}}"
            assert body is not None
    except HTTPError as e:
        assert e.code in (301, 302, 401, 403), f"Unexpected HTTPError {{e.code}} for {{url}}"
    except URLError:
        # Some monitors might not be HTTP (rare) or require TLS; treat as "listening" only.
        pass
'''

def write_test_file(
    out_path: Path,
    *,
    static_endpoints: List[str],
    linked_endpoints: List[str],
    base_url_default: str,
    monitor_host_default: str,
    monitor_ports: List[int],
) -> None:
    # Ensure determinism
    static_eps = static_endpoints
    linked_eps = linked_endpoints

    # If linked list is huge/noisy, cap it
    if len(linked_eps) > 200:
        linked_eps = linked_eps[:200]

    rendered = TEST_TEMPLATE.format(
        base_url_default=base_url_default,
        monitor_host_default=monitor_host_default,
        monitor_ports=repr(monitor_ports),
        static_endpoints=repr(static_eps),
        linked_endpoints=repr(linked_eps),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="SSH to Pi, discover captive portal endpoints, generate pytest suite.")
    ap.add_argument("--host", required=True, help="Pi hostname/IP (e.g. 192.168.50.1)")
    ap.add_argument("--user", default="pi")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--key", default=None, help="SSH key path (recommended)")
    ap.add_argument("--password", default=None, help="SSH password (optional)")
    ap.add_argument("--root", default="/AP_mode_wordpress_launcher/www/captive-portal", help="Remote captive portal directory")
    ap.add_argument("--out", default="AP_mode_wordpress_launcher/tests/generated/test_endpoints.py", help="Local output pytest file")
    ap.add_argument("--base-url-default", default="http://127.0.0.1", help="Default base URL used by tests on the Pi")
    ap.add_argument("--monitor-host-default", default="127.0.0.1", help="Host used for monitor probing in tests (on Pi)")
    args = ap.parse_args()

    ssh = ssh_connect(args.host, args.user, args.port, args.key, args.password)
    try:
        # Preflight: ensure directory exists
        r = ssh_run(ssh, f"test -d {shlex.quote(args.root)} && echo OK || echo MISSING")
        if "OK" not in r.out:
            print(f"[ERROR] Remote directory missing: {args.root}", file=sys.stderr)
            return 2

        static_eps, linked_eps = build_endpoint_set(ssh, args.root, parse_linked=True)
        monitor_ports = choose_monitor_ports(ssh)

        out_path = Path(args.out)
        write_test_file(
            out_path,
            static_endpoints=static_eps,
            linked_endpoints=linked_eps,
            base_url_default=args.base_url_default,
            monitor_host_default=args.monitor_host_default,
            monitor_ports=monitor_ports,
        )

        print(f"[OK] Generated: {out_path}")
        print(f"     Static endpoints: {len(static_eps)}")
        print(f"     Linked routes:    {len(linked_eps)}")
        print(f"     Monitor ports:    {monitor_ports}")
        print("")
        print("Next on the Pi:")
        print("  python3 -m pip install -U pytest")
        print("  cd /AP_mode_wordpress_launcher && python3 -m pytest -q")
        print("")
        print("If apache is not on 127.0.0.1 in your runtime, set env:")
        print("  CAPTIVE_BASE_URL=http://127.0.0.1 python3 -m pytest -q")
        return 0

    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
