#!/usr/bin/env python3
"""E2E test for the Deductible web UI using Playwright.

Prereq:  python web.py  running on http://127.0.0.1:8000  (or this test starts it)
Run:     ../.venv-llm/Scripts/python.exe e2e_web_test.py

Verifies the real offline ask flow end-to-end in a real browser:
  load page -> click "load sample" -> type a question -> click Ask -> answer renders.
"""
import sys
import time
import subprocess
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
URL = "http://127.0.0.1:8000"
PY = str(HERE.parent / ".venv-llm" / "Scripts" / "python.exe")
if not Path(PY).exists():
    PY = sys.executable  # fall back to the interpreter running this test


def ensure_server():
    import urllib.request
    try:
        urllib.request.urlopen(URL, timeout=1)
        return None
    except Exception:
        return subprocess.Popen([PY, str(HERE / "web.py")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_ready(timeout=60):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("web server did not come up")


def main():
    proc = ensure_server()
    wait_ready()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(URL)

            # 1. Page renders with title + ask button disabled
            assert "Deductible" in page.title() or "Deductible" in page.content(), "page title"
            assert page.is_disabled("#ask"), "ask button starts disabled"

            # 2. Load sample -> ask button becomes enabled
            page.click("#load-sample")
            page.wait_for_function("!document.getElementById('ask').disabled")
            csv_text = page.input_value("#csv")
            assert "BLUE BOTTLE" in csv_text, "sample CSV loaded"

            # 3. Ask a real question -> offline answer renders in <out>
            page.fill("#q", "What are my biggest deductible expenses?")
            page.click("#ask")
            page.wait_for_selector("#out:not([hidden])", timeout=120_000)
            page.wait_for_function("!document.getElementById('out').textContent.includes('Error:')")

            out = page.inner_text("#out")
            print("=== OUT ===\n", out[:1500])
            # ledger UI: table + answer block + flagged block
            assert "Your bookkeeper says" in out, "answer block present"
            assert "Equipment" in out, "grounded category present"
            assert "Estimated deductible" in out, "total row present"
            # the ANSWER block itself must cite a dollar figure (not just the table)
            answer_text = page.inner_text(".answer")
            assert "$" in answer_text, "answer cites a dollar figure"
            # model-classified rows must surface in the review box
            assert page.query_selector(".flagblock") is not None, "flagged block rendered"

            # 4. Screenshot as visual proof
            shot = HERE / "demo_screenshot.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"\nSCREENSHOT SAVED: {shot}")

            print("\nE2E WEB TEST PASSED")
            browser.close()
            return 0
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())