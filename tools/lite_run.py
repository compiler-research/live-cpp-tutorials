#!/usr/bin/env python
"""Run cells in a JupyterLite site's REPL app headlessly and dump what each output area shows.
The REPL takes repeated code= query parameters (one per cell) and executes them in order.
Usage: lite_run.py --site http://127.0.0.1:8941 --kernel xcpp23 --cells cells.json [--timeout 300] [--out dir]
cells.json: a JSON list of cell sources (strings). A %%python magic must start its own cell.
Prints each output area's text (and the byte size of any inline image) as JSON lines; exit 0 when the last cell produced output."""
import argparse, json, sys, time, pathlib, urllib.parse
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--site", required=True); ap.add_argument("--kernel", default="xcpp23"); ap.add_argument("--cells", required=True)
ap.add_argument("--timeout", type=int, default=300); ap.add_argument("--out", default=""); ap.add_argument("--sentinel", default="__LITE_DONE__"); ap.add_argument("--ledger", default="", help="write every response (url, status, body bytes) as JSON"); ap.add_argument("--console-all", action="store_true", help="keep every console message, not only errors")
a = ap.parse_args()
cells = json.load(open(a.cells))
cells = cells + [f'#include <iostream>\nstd::cout << "{a.sentinel}" << std::endl;']   # a last C++ cell marks the end
url = f"{a.site}/repl/index.html?" + urllib.parse.urlencode([("kernel", a.kernel), ("execute", "1"), ("toolbar", "0")] + [("code", c) for c in cells])
t0 = time.time(); results = []
with sync_playwright() as p:
    browser = p.chromium.launch(); ctx = browser.new_context(); page = ctx.new_page()
    console, net = [], []
    page.on("console", lambda m: console.append(m.text) if (a.console_all or m.type in ("error", "warning")) else None)
    ctx.on("response", lambda r: net.append((r.status, r.url)) if (r.status >= 400 or ".so" in r.url or "mount_" in r.url) else None)
    ctx.on("requestfailed", lambda r: net.append(("failed", r.url)))
    ledger = []
    def _led(r):
        try: ledger.append({"url": r.url, "status": r.status, "body": r.request.sizes().get("responseBodySize", -1), "type": r.headers.get("content-type", "")})
        except Exception as e: ledger.append({"url": r.url, "status": r.status, "body": -1, "err": str(e)[:60]})
    if a.ledger: ctx.on("response", _led)
    page.goto(url, timeout=120_000, wait_until="domcontentloaded")
    done = False
    while time.time() - t0 < a.timeout:
        time.sleep(2)
        areas = page.query_selector_all(".jp-OutputArea-output")
        texts = [el.inner_text() for el in areas]
        if any(a.sentinel in t for t in texts): done = True; break
    areas = page.query_selector_all(".jp-OutputArea-output")
    for i, el in enumerate(areas):
        img = el.query_selector("img"); src = img.get_attribute("src") if img else None
        results.append({"i": i, "text": el.inner_text().strip()[:2000], "image_bytes": (len(src) * 3 // 4) if src else 0})
        if src and a.out:
            import base64; pathlib.Path(a.out).mkdir(parents=True, exist_ok=True)
            open(pathlib.Path(a.out) / f"out{i}.png", "wb").write(base64.b64decode(src.split(",", 1)[1]))
    if a.out:
        pathlib.Path(a.out).mkdir(parents=True, exist_ok=True); page.screenshot(path=str(pathlib.Path(a.out) / "page.png"), full_page=True)
    browser.close()
if a.ledger: json.dump(ledger, open(a.ledger, "w"), indent=0)
for r in results: print(json.dumps(r))
print(json.dumps({"done": done, "elapsed_s": round(time.time() - t0), "console_errors": console[:40], "net": net[:40]}))
sys.exit(0 if done else 1)
