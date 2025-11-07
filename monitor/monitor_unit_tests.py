#!/usr/bin/env python3
"""
monitor_route_tester.py

Quick text utility to probe all routes on the PiPress Monitor service.
Run your Flask app first, then run this:

    python monitor_route_tester.py --base http://127.0.0.1:35373
"""

import argparse
import json
from typing import Any, Dict

import requests


# routes that are always safe to GET
GET_ROUTES = [
    "/",                # dashboard page
    "/status",          # JSON status
    "/logs",            # recent logs
    "/api/captive/list",
    "/favicon.ico",
]

# control routes (start/stop/restart) – may fail on Windows, so we mark them optional
CONTROL_ROUTES = [
    "/control/start",
    "/control/stop",
    "/control/restart",
]


def print_header(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def try_get(base: str, path: str):
    url = base.rstrip("/") + path
    try:
        r = requests.get(url, timeout=4)
        ct = r.headers.get("Content-Type", "")
        print(f"[GET] {path} -> {r.status_code}")
        if "application/json" in ct:
            try:
                j = r.json()
                print(json.dumps(j, indent=2))
            except Exception:
                print(r.text[:300])
        else:
            text = r.text.strip()
            if len(text) > 300:
                text = text[:300] + " ..."
            print(text)
    except Exception as e:
        print(f"[GET] {path} -> ERROR: {e}")


def try_post(base: str, path: str, data: Dict[str, Any] | None = None, files=None):
    url = base.rstrip("/") + path
    try:
        r = requests.post(url, data=data, files=files, timeout=4)
        ct = r.headers.get("Content-Type", "")
        print(f"[POST] {path} -> {r.status_code}")
        if "application/json" in ct:
            try:
                print(json.dumps(r.json(), indent=2))
            except Exception:
                print(r.text[:300])
        else:
            text = r.text.strip()
            if len(text) > 300:
                text = text[:300] + " ..."
            print(text)
    except Exception as e:
        print(f"[POST] {path} -> ERROR: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test all monitor routes.")
    parser.add_argument("--base", default="http://127.0.0.1:35373", help="Base URL of monitor app")
    parser.add_argument("--skip-control", action="store_true", help="Skip /control/* routes (useful on Windows)")
    args = parser.parse_args()

    base = args.base

    # 1. original GET behavior
    print_header("1. GET routes")
    for path in GET_ROUTES:
        try_get(base, path)

    # 2. original POST behavior (with additions)
    print_header("2. POST routes")

    # /api/captive/clear
    try_post(base, "/api/captive/clear")

    # /api/captive/restore
    try_post(base, "/api/captive/restore")

    # /update-settings – send dummy settings (same as before)
    try_post(base, "/update-settings", data={
        "use_local": "on",
        "fast_launch": "on",
        "verbose": "on",
        "startup": "",
        "captiveportal": "",
        "fti": "",
        "ssid": "TestSSID",
        "wap_passphrase": "TestPass",
    })

    # /update-lms – send dummy LMS (slightly more obviously test-ish)
    try_post(base, "/update-lms", data={
        "lms_port": "9090",
        "lms_dir": "/srv/test_lms_dir",
    })

    # 3. captive portal preview (preserved)
    print_header("3. Captive portal preview test (if any files exist)")
    try:
        r = requests.get(base.rstrip("/") + "/api/captive/list", timeout=4)
        if r.ok:
            files = r.json()
            if isinstance(files, list) and files:
                first = files[0]
                preview_url = f"/api/captive/preview?file={first}"
                print(f"Attempting preview of first file: {first}")
                try_get(base, preview_url)
            else:
                print("No captive portal files to preview.")
        else:
            print("Could not list captive portal files.")
    except Exception as e:
        print(f"Error checking captive files: {e}")

    # 3b. explicit reset check right after the preview
    print_header("3b. Captive reset re-check")
    try_post(base, "/api/captive/restore")

    # 4. control routes (preserved)
    if not args.skip_control:
        print_header("4. Control routes (may fail on non-Linux systems)")
        for path in CONTROL_ROUTES:
            try_get(base, path)
    else:
        print_header("4. Control routes")
        print("Skipped by --skip-control")

    print_header("Done.")
    print("If some routes failed with 404 or 500, check your Flask app for those endpoints.")


if __name__ == "__main__":
    main()
