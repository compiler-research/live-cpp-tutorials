#!/usr/bin/env python
"""Measure what a reader's browser downloads for one notebook of the JupyterLite site, end to end: open the notebook in
the Lab UI, Run All Cells, wait for the last expected output, record every response body (kernel worker included).
Serve the site with a gzip-capable server first (see lite/README-build.md; python -m http.server does not compress).
Usage: lite_wire.py --site http://127.0.0.1:8943 --notebook 4_higgs_open_data.ipynb --expect "q0 = 9.87" [--images 2] [--out ledger.json]
Prints the bytes received per component, and the time from page load to the expected output."""
import argparse, json, time, urllib.parse, collections
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser(); ap.add_argument("--site", required=True); ap.add_argument("--notebook", required=True)
ap.add_argument("--expect", required=True, help="text that appears in the last cell's output"); ap.add_argument("--images", type=int, default=0, help="figures expected on the page")
ap.add_argument("--out", default=""); ap.add_argument("--timeout", type=int, default=600)
a = ap.parse_args(); led = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 900}); pg = ctx.new_page()
    def rec(r):
        try: led.append({"url": r.url, "status": r.status, "body": r.request.sizes().get("responseBodySize", -1), "t": time.time()})
        except Exception: pass
    ctx.on("response", rec)
    t0 = time.time()
    pg.goto(f"{a.site}/lab/index.html?path={a.notebook}", timeout=120000, wait_until="domcontentloaded")
    for _ in range(120):
        time.sleep(2)
        if pg.query_selector(".jp-Notebook") and pg.query_selector(".jp-KernelName, .jp-Toolbar-kernelName"): break
    t_ui = time.time() - t0
    time.sleep(5); pg.keyboard.press("Escape")
    # JupyterLab may ask "Save changes before closing?" for a tab it replaces when opening ?path=; keep the notebook open
    for _ in range(10):
        if not pg.query_selector(".jp-Dialog"): break
        btn = pg.query_selector(".jp-Dialog button:has-text('Cancel')") or pg.query_selector(".jp-Dialog .jp-Dialog-button")
        if btn: btn.click()
        time.sleep(1)
    pg.click("text=Run", timeout=30000); time.sleep(1); pg.click("text=Run All Cells", timeout=30000)
    done = False
    while time.time() - t0 < a.timeout:
        time.sleep(2)
        txt = pg.inner_text(".jp-Notebook")
        if a.expect in txt and len(pg.query_selector_all(".jp-OutputArea-output img")) >= a.images: done = True; break
    t_done = time.time() - t0
    if not done:   # leave evidence of what the page showed
        shot = (a.out or "wire") + ".png"; pg.screenshot(path=shot, full_page=False)
        print("not done; dialogs:", [d.inner_text()[:200].replace("\n", " | ") for d in pg.query_selector_all(".jp-Dialog")], "screenshot:", shot)
    b.close()
g = collections.defaultdict(lambda: [0, 0]); tot = 0; per = collections.Counter(); first_cell_bytes = 0
for r in led:
    u = urllib.parse.urlparse(r["url"]); path = u.path
    if r["status"] != 200 or r["body"] <= 0: continue
    per[path] += 1
    if "/lazy/" in path: k = "lazy packages (first import)"
    elif "kernel_packages" in path: k = "Python packages at start"
    elif path.endswith(("xcpp.wasm", "xcpp.data", "xcpp.js")): k = "C++ kernel"
    elif path.endswith("libclangCppInterOp.so"): k = "CppInterOp module"
    elif path.endswith(".so"): k = "shared libraries on demand"
    else: k = "app shell, extensions, files"
    g[k][0] += r["body"]; g[k][1] += 1; tot += r["body"]
print(f"{a.notebook}: UI up {t_ui:.0f} s, last output {t_done:.0f} s, done={done}")
for k, (bb, c) in sorted(g.items(), key=lambda x: -x[1][0]): print(f"  {k:32s} {bb/1048576:6.1f} MB  {c:4d} responses")
print(f"  {'total':32s} {tot/1048576:6.1f} MB")
dups = [(pp.rsplit('/', 1)[-1], c) for pp, c in per.items() if c > 1 and not pp.endswith(('.json', '.html', '.ipynb'))]
if dups: print("  fetched more than once:", dups[:6])
if a.out: json.dump({"notebook": a.notebook, "total_bytes": tot, "groups": {k: v[0] for k, v in g.items()}, "ui_s": t_ui, "done_s": t_done, "done": done}, open(a.out, "w"), indent=1)
