# pytest_endpoints_template.py
# AUTO-GENERATED – do not edit on the Pi

from __future__ import annotations

import os
import socket
import time
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pytest

# === INJECTED CONFIG (DO NOT REMOVE) ===
STATIC_ENDPOINTS = __STATIC_ENDPOINTS__
LINKED_ENDPOINTS = __LINKED_ENDPOINTS__
MONITOR_PORTS = __MONITOR_PORTS__

BASE_URL = os.environ.get("CAPTIVE_BASE_URL", "__BASE_URL__").rstrip("/") + "/"
MONITOR_HOST = os.environ.get("MONITOR_HOST", "__MONITOR_HOST__")

MAX_STATIC_MS = int(os.environ.get("MAX_STATIC_MS", "250"))
MAX_LINKED_MS = int(os.environ.get("MAX_LINKED_MS", "400"))
MAX_MONITOR_MS = int(os.environ.get("MAX_MONITOR_MS", "500"))

HTTP_RETRIES = int(os.environ.get("HTTP_RETRIES", "2"))
HTTP_TIMEOUT_S = float(os.environ.get("HTTP_TIMEOUT_S", "3.5"))


def _http_get_timed(path: str):
    url = urljoin(BASE_URL, path.lstrip("/"))
    last_exc = None

    for attempt in range(HTTP_RETRIES + 1):
        t0 = time.perf_counter()
        try:
            req = Request(url, headers={"User-Agent": "pytest-endpoint-probe"})
            with urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                body = resp.read(4096)
                ms = (time.perf_counter() - t0) * 1000.0
                return resp.status, body, ms
        except HTTPError as e:
            ms = (time.perf_counter() - t0) * 1000.0
            return e.code, b"", ms
        except URLError as e:
            last_exc = e
            if attempt >= HTTP_RETRIES:
                raise
            time.sleep(0.1 * (attempt + 1))

    raise last_exc


def _assert_latency(label: str, ms: float, limit: int):
    if limit > 0:
        assert ms <= limit, f"{label} too slow: {ms:.1f}ms > {limit}ms"


@pytest.mark.parametrize("path", STATIC_ENDPOINTS)
def test_static_endpoints_fast(path: str):
    status, body, ms = _http_get_timed(path)
    print(f"[LATENCY] static {path} -> {status} in {ms:.1f}ms")
    assert status == 200
    _assert_latency(f"static {path}", ms, MAX_STATIC_MS)


@pytest.mark.parametrize("path", LINKED_ENDPOINTS)
def test_linked_endpoints_fast(path: str):
    status, body, ms = _http_get_timed(path)
    print(f"[LATENCY] linked {path} -> {status} in {ms:.1f}ms")
    assert status in (200, 301, 302, 401, 403)
    _assert_latency(f"linked {path}", ms, MAX_LINKED_MS)


def _tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.2):
            return True
    except OSError:
        return False


@pytest.mark.parametrize("port", MONITOR_PORTS)
def test_monitor_responsive(port: int):
    if not _tcp_open(MONITOR_HOST, port):
        pytest.skip(f"{MONITOR_HOST}:{port} not listening")

    url = f"http://{MONITOR_HOST}:{port}/"
    t0 = time.perf_counter()
    try:
        req = Request(url, headers={"User-Agent": "pytest-monitor-probe"})
        with urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            _ = resp.read(1024)
            ms = (time.perf_counter() - t0) * 1000.0
            print(f"[LATENCY] monitor {url} in {ms:.1f}ms")
            _assert_latency(f"monitor {url}", ms, MAX_MONITOR_MS)
    except HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000.0
        _assert_latency(f"monitor {url}", ms, MAX_MONITOR_MS)
