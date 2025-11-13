#!/usr/bin/env python3
"""
test_wordpress_endpoints.py

Broad HTTP sanity tests for your WordPress / captive-portal / Apache-backed server.

Features:
- Discovers endpoints *broadly* by scanning project files:
  - href, src, srcset, action
  - fetch(), axios.*, $.ajax(), XHR open()
  - location.assign / location.href / history.pushState
  - generic string paths like "/some/route"
  - form method=GET/POST actions
- PLUS Apache 2–style endpoint discovery:
  - RewriteRule pattern targets (from .htaccess / *.conf)
  - Alias / ScriptAlias paths
  - DirectoryIndex index files

Configuration via environment:
    WP_BASE_URL   – base URL of the running server (default: http://192.168.4.1)
    PROJECT_ROOT  – root directory to scan for endpoints
                    (default: project root ".." relative to this file)
    MAX_ENDPOINTS – hard cap on discovered endpoints (default: 400)

Typical usage:
    export WP_BASE_URL="http://192.168.4.1"
    export PROJECT_ROOT="/AP_mode_wordpress_launcher"
    python -m unittest tests.test_wordpress_endpoints
"""

from __future__ import annotations
import os
import re
import unittest
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Set

import requests


# =========================
# Config
# =========================

BASE_URL = os.environ.get("WP_BASE_URL", "http://192.168.4.1")

PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

MAX_ENDPOINTS = int(os.environ.get("MAX_ENDPOINTS", "400"))

# File extensions we broadly scan
SCAN_EXTENSIONS = {
    ".php", ".html", ".htm",
    ".js", ".ts",
    ".css", ".json",
    ".py", ".sh",
    ".conf",        # Apache vhost / site config
}

# Special filenames with no extension (Apache)
SCAN_SPECIAL_FILES = {".htaccess"}


@dataclass(frozen=True)
class Endpoint:
    name: str
    path: str
    method: str = "GET"
    allow_redirects: bool = True
    expected_min_status: int = 200
    expected_max_status: int = 399
    expect_text: Optional[str] = None


# =========================
# Endpoint discovery – generic
# =========================

# HTML attributes
RE_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
RE_SRC = re.compile(r"""src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
RE_SRCSET = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
RE_ACTION = re.compile(r"""action\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

# JS fetch / axios / jQuery / XHR
RE_FETCH = re.compile(r"""fetch\(\s*["']([^"']+)["']""", re.IGNORECASE)
RE_AXIOS = re.compile(
    r"""axios\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
RE_JQUERY = re.compile(
    r"""\$\.(get|post|ajax)\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
RE_XHR_OPEN = re.compile(
    r"""XMLHttpRequest\s*\(\)\s*;?.*?\.open\(\s*["'](GET|POST|PUT|DELETE|PATCH)["']\s*,\s*["']([^"']+)["']""",
    re.IGNORECASE | re.DOTALL,
)

# Location/history navigation
RE_LOCATION_ASSIGN = re.compile(
    r"""(?:window\.)?location\.(?:href|assign|replace)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)
RE_HISTORY_PUSHSTATE = re.compile(
    r"""history\.pushState\([^)]*["']([^"']+)["']""",
    re.IGNORECASE,
)

# Generic string paths like "/foo/bar"
RE_GENERIC_PATH = re.compile(r"""["'](/[^"']+)["']""")

# Rough form tag detection: <form ... >
RE_FORM_TAG = re.compile(
    r"""<form[^>]*?>""",
    re.IGNORECASE | re.DOTALL,
)
RE_FORM_ACTION = re.compile(r"""action\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
RE_FORM_METHOD = re.compile(r"""method\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


# =========================
# Endpoint discovery – Apache 2 specific
# =========================

# RewriteRule pattern target [flags]
#   RewriteRule ^foo/bar/?$  /index.php?route=foo [L,QSA]
RE_APACHE_REWRITERULE = re.compile(
    r"""^\s*RewriteRule\s+(\S+)\s+(\S+)""",
    re.IGNORECASE | re.MULTILINE,
)

# Alias / ScriptAlias
#   Alias /static/ /var/www/static/
RE_APACHE_ALIAS = re.compile(
    r"""^\s*(Alias|ScriptAlias)\s+["']?(/[^"'\s]*)["']?\s+["']?[^"'\s]*["']?""",
    re.IGNORECASE | re.MULTILINE,
)

# DirectoryIndex
#   DirectoryIndex index.php index.html
RE_APACHE_DIRINDEX = re.compile(
    r"""^\s*DirectoryIndex\s+(.+)$""",
    re.IGNORECASE | re.MULTILINE,
)


def _normalize_path(raw: str) -> Optional[str]:
    """
    Normalize a discovered URL into a clean path suitable for testing.

    - Drops protocol/host if absolute URL (we only care about path).
    - Ignores anchors, mailto:, javascript: etc.
    - Converts relative paths to root-based ("/...") as a best-effort heuristic.
    - No extension filtering: CSS/JS/images/etc. are allowed.
    """
    raw = raw.strip()

    if not raw or raw.startswith("#"):
        return None
    if raw.startswith("mailto:") or raw.lower().startswith("javascript:"):
        return None

    # Full URLs -> keep only path
    if raw.startswith("http://") or raw.startswith("https://"):
        try:
            idx = raw.index("/", raw.index("://") + 3)
            raw = raw[idx:]
        except ValueError:
            return None

    # Protocol-relative URLs ("//example.com/...") – treat as external, skip
    if raw.startswith("//"):
        return None

    # Strip query / fragment
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    if "#" in raw:
        raw = raw.split("#", 1)[0]

    if not raw:
        return None

    if not raw.startswith("/"):
        raw = "/" + raw.lstrip("./")

    return raw or None


def _apache_pattern_to_path(pattern: str) -> Optional[str]:
    """
    Attempt to convert a RewriteRule pattern into a testable path.

    This is heuristic—Apache patterns are regexes; we:
        - strip leading '^' and trailing '$'
        - stop at the first regex-special char if present
        - ensure it starts with '/'
    """
    pat = pattern.strip()

    # If target is "-" (rewrite to nothing), skip
    if pat == "-":
        return None

    if pat.startswith("^"):
        pat = pat[1:]
    if pat.endswith("$"):
        pat = pat[:-1]

    # If it already looks like a path "/foo/bar", great
    if pat.startswith("/"):
        # If there are obvious regex components, truncate before them
        m = re.search(r"[?*+()|\[\]]", pat)
        if m:
            pat = pat[: m.start()]
        return _normalize_path(pat)

    # If it starts with a word (e.g. "foo/bar"), treat as "/foo/bar"
    # but truncate at regex chars
    m = re.search(r"[?*+()|\[\]]", pat)
    if m:
        pat = pat[: m.start()]

    if not pat:
        return None

    if not pat.startswith("/"):
        pat = "/" + pat

    return _normalize_path(pat)


def _apache_scan(text: str) -> Set[Tuple[str, str]]:
    """
    Scan Apache 2 config-style text (.htaccess, *.conf) for endpoint-like paths.

    Returns:
        A set of (method, path) tuples (method is usually "GET").
    """
    results: Set[Tuple[str, str]] = set()

    # RewriteRule patterns
    for pattern, target in RE_APACHE_REWRITERULE.findall(text):
        path = _apache_pattern_to_path(pattern)
        if path:
            results.add(("GET", path))

        # Also consider the target if it looks like an endpoint
        t_norm = _normalize_path(target)
        if t_norm:
            results.add(("GET", t_norm))

    # Alias / ScriptAlias
    for _kind, alias_path in RE_APACHE_ALIAS.findall(text):
        norm = _normalize_path(alias_path)
        if norm:
            results.add(("GET", norm))

    # DirectoryIndex entries
    for dirline in RE_APACHE_DIRINDEX.findall(text):
        for token in dirline.split():
            norm = _normalize_path(token)
            if norm:
                results.add(("GET", norm))

    return results


def _add_paths(matches, method: str,
               get_like: Set[Tuple[str, str]],
               post_like: Set[Tuple[str, str]]) -> None:
    """
    Helper to add paths from regex matches to get_like/post_like sets.
    """
    for m in matches:
        if isinstance(m, tuple):
            url = m[-1]
        else:
            url = m
        norm = _normalize_path(url)
        if norm:
            if method.upper() == "POST":
                post_like.add(("POST", norm))
            else:
                get_like.add(("GET", norm))


def _scan_file_for_endpoints(path: str) -> Tuple[Set[Tuple[str, str]], Set[Tuple[str, str]]]:
    """
    Scan a single file for endpoints.

    Returns:
        (get_like, post_like)
        where each is a set of (method, normalized_path) pairs.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        return set(), set()

    get_like: Set[Tuple[str, str]] = set()
    post_like: Set[Tuple[str, str]] = set()

    # Apache-specific scanning for .htaccess / *.conf
    fname = os.path.basename(path).lower()
    if fname in SCAN_SPECIAL_FILES or fname.endswith(".conf"):
        ap_paths = _apache_scan(text)
        for tup in ap_paths:
            get_like.add(tup)

    # HTML attributes
    _add_paths(RE_HREF.findall(text), "GET", get_like, post_like)
    _add_paths(RE_SRC.findall(text), "GET", get_like, post_like)

    # srcset may contain multiple URLs
    srcset_matches = RE_SRCSET.findall(text)
    split_srcset_urls: List[str] = []
    for s in srcset_matches:
        for part in s.split(","):
            url_part = part.strip().split(" ")[0]
            if url_part:
                split_srcset_urls.append(url_part)
    _add_paths(split_srcset_urls, "GET", get_like, post_like)

    _add_paths(RE_ACTION.findall(text), "GET", get_like, post_like)  # default: GET

    # JS APIs
    _add_paths(RE_FETCH.findall(text), "GET", get_like, post_like)
    _add_paths(RE_AXIOS.findall(text), "GET", get_like, post_like)
    _add_paths(RE_JQUERY.findall(text), "GET", get_like, post_like)

    for http_method, url in RE_XHR_OPEN.findall(text):
        norm = _normalize_path(url)
        if norm:
            if http_method.upper() == "POST":
                post_like.add(("POST", norm))
            else:
                get_like.add(("GET", norm))

    # Location/history
    _add_paths(RE_LOCATION_ASSIGN.findall(text), "GET", get_like, post_like)
    _add_paths(RE_HISTORY_PUSHSTATE.findall(text), "GET", get_like, post_like)

    # Generic "/foo/bar" strings
    _add_paths(RE_GENERIC_PATH.findall(text), "GET", get_like, post_like)

    # Form-specific method/post detection
    for form_match in RE_FORM_TAG.finditer(text):
        form_tag = form_match.group(0)

        action_match = RE_FORM_ACTION.search(form_tag)
        if not action_match:
            continue

        action_raw = action_match.group(1)
        norm = _normalize_path(action_raw)
        if not norm:
            continue

        method_match = RE_FORM_METHOD.search(form_tag)
        if method_match:
            m = method_match.group(1).strip().upper()
        else:
            m = "GET"

        if m == "POST":
            post_like.add(("POST", norm))
        else:
            get_like.add(("GET", norm))

    return get_like, post_like


def discover_endpoints(project_root: str, limit: int = MAX_ENDPOINTS) -> List[Endpoint]:
    """
    Walk the project tree and discover endpoints referenced in code & Apache configs.
    Returns a list of Endpoint objects.
    """
    seen: Dict[Tuple[str, str], Endpoint] = {}

    # Baseline WordPress-ish endpoints
    baseline = [
        Endpoint(name="home", path="/"),
        Endpoint(name="wp_login", path="/wp-login.php"),
        Endpoint(name="wp_admin", path="/wp-admin/"),
        Endpoint(name="wp_rest_root", path="/wp-json/"),
    ]
    for ep in baseline:
        seen[(ep.method, ep.path)] = ep

    for root, _, files in os.walk(project_root):
        for fname in files:
            lower = fname.lower()
            ext = os.path.splitext(lower)[1]

            if ext not in SCAN_EXTENSIONS and lower not in SCAN_SPECIAL_FILES:
                continue

            fpath = os.path.join(root, fname)
            get_like, post_like = _scan_file_for_endpoints(fpath)

            for method, path in get_like.union(post_like):
                key = (method, path)
                if key in seen:
                    continue

                name = f"{method}_{path.strip('/').replace('/', '_') or 'root'}"
                ep = Endpoint(
                    name=name,
                    path=path,
                    method=method,
                    allow_redirects=True,  # Apache/WordPress frequently redirect
                    expected_min_status=200,
                    expected_max_status=399,
                )
                seen[key] = ep

                if len(seen) >= limit:
                    return list(seen.values())

    return list(seen.values())


# Populated in setUpClass
ENDPOINTS: List[Endpoint] = []


# =========================
# TestCase
# =========================

class TestWordPressEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        global ENDPOINTS

        if not BASE_URL.startswith("http"):
            raise RuntimeError(f"WP_BASE_URL must be a full URL (got {BASE_URL!r})")

        print(f"[TestWordPressEndpoints] Using base URL: {BASE_URL}")
        print(f"[TestWordPressEndpoints] Scanning project root: {PROJECT_ROOT}")

        ENDPOINTS = discover_endpoints(PROJECT_ROOT, limit=MAX_ENDPOINTS)
        if not ENDPOINTS:
            raise RuntimeError(
                f"No endpoints discovered in project root {PROJECT_ROOT!r}. "
                "Check PROJECT_ROOT or add baseline endpoints."
            )

        print(f"[TestWordPressEndpoints] Discovered {len(ENDPOINTS)} endpoints (capped at {MAX_ENDPOINTS}):")
        for ep in ENDPOINTS:
            print(f"  - {ep.method} {ep.path} ({ep.name})")

    def _request_endpoint(self, ep: Endpoint) -> requests.Response:
        url = BASE_URL.rstrip("/") + ep.path
        method = ep.method.upper()

        kwargs = dict(allow_redirects=ep.allow_redirects, timeout=10)

        if method == "GET":
            resp = requests.get(url, **kwargs)
        elif method == "HEAD":
            resp = requests.head(url, **kwargs)
        elif method == "POST":
            resp = requests.post(url, data={}, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {ep.method}")

        return resp

    def test_all_endpoints_status(self):
        """
        For each discovered endpoint:
        - Make the appropriate HTTP request (GET/POST).
        - Assert response status is 2xx–3xx.
        """
        for ep in ENDPOINTS:
            with self.subTest(endpoint=ep.name, path=ep.path, method=ep.method):
                resp = self._request_endpoint(ep)

                self.assertGreaterEqual(
                    resp.status_code,
                    ep.expected_min_status,
                    msg=f"{ep.name} ({ep.path}) returned {resp.status_code}, "
                        f"expected >= {ep.expected_min_status}",
                )
                self.assertLessEqual(
                    resp.status_code,
                    ep.expected_max_status,
                    msg=f"{ep.name} ({ep.path}) returned {resp.status_code}, "
                        f"expected <= {ep.expected_max_status}",
                )

                if ep.expect_text is not None and ep.method != "HEAD":
                    self.assertIn(
                        ep.expect_text,
                        resp.text,
                        msg=(
                            f"{ep.name} ({ep.path}) did not contain expected text "
                            f"{ep.expect_text!r}"
                        ),
                    )

    def test_no_5xx_errors(self):
        """
        Guardrail: ensure no discovered endpoint returns 5xx.
        """
        for ep in ENDPOINTS:
            with self.subTest(endpoint=ep.name, path=ep.path, method=ep.method):
                resp = self._request_endpoint(ep)
                self.assertFalse(
                    500 <= resp.status_code <= 599,
                    msg=f"{ep.name} ({ep.path}) returned server error {resp.status_code}",
                )


if __name__ == "__main__":
    unittest.main()
