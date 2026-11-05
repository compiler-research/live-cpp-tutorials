#!/usr/bin/env python
"""Turn the home notebooks (Python kernel + cppjit wheel) into JupyterLite notebooks for the xcpp23 kernel that hosts
Python through cppjit: every Python cell becomes a %%python cell, a first pair of cells sets the working directory to the
mounted /cppjit (so kernel/ and data/ paths work unchanged), installs the lazy package loader (kernel/lazy.py: SciPy and
matplotlib download in the background and unpack on first import) and routes plt.show() through a C++ display helper
(matplotlib has no Jupyter backend inside this kernel: the figure is saved to /tmp and shown as a PNG by xcpp::display).
Usage: home2lite.py <home dir> <out dir>"""
import sys, json, os, copy, pathlib

src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); dst.mkdir(parents=True, exist_ok=True)

CPP_HELPER = r'''// Display helper: the Python cells save figures as PNG, this shows them. (C++ cell: the kernel is C++, Python runs inside it.)
#include <fstream>
#include <string>
#include "xcpp/xdisplay.hpp"
#include "nlohmann/json.hpp"
struct png_file { std::string bytes; explicit png_file(const std::string& path) { std::ifstream in(path, std::ios::binary); bytes.assign(std::istreambuf_iterator<char>(in), {}); } };
nlohmann::json mime_bundle_repr(const png_file& p) {
    static const char* t = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string o; int v = 0, b = -6;
    for (unsigned char c : p.bytes) { v = (v << 8) + c; b += 8; while (b >= 0) { o.push_back(t[(v >> b) & 63]); b -= 6; } }
    if (b > -6) o.push_back(t[((v << 8) >> (b + 8)) & 63]);
    while (o.size() % 4) o.push_back('=');
    return {{"image/png", o}};
}
void show_png(const std::string& path) { xcpp::display(png_file(path)); }'''

PY_BOOT = '''%%python
# Browser setup: the kernel is C++ (xcpp23) and hosts this Python through cppjit; the notebook's files are mounted at /cppjit.
# SciPy and matplotlib are not in the kernel's start-up set: they download in the background from here on and unpack on
# their first import (kernel/lazy.py), so the kernel is ready sooner and nothing is fetched that a notebook never uses.
import os, sys, cppjit
os.chdir("/cppjit"); sys.path.insert(0, "/cppjit/kernel")
import lazy; lazy.install(show_png=cppjit.gbl.show_png)
print("ready: cppjit", cppjit.__version__, "in the browser, working directory", os.getcwd())'''

def cell(kind, text):
    c = {"cell_type": kind, "metadata": {}, "source": text.splitlines(keepends=True)}
    if kind == "code": c["execution_count"] = None; c["outputs"] = []
    return c

for nb_path in sorted(src.glob("*.ipynb")):
    nb = json.load(open(nb_path)); out = copy.deepcopy(nb)
    cells = []
    first_code_done = False
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            text = "".join(c["source"])
            if not first_code_done:
                cells.append(cell("code", CPP_HELPER)); cells.append(cell("code", PY_BOOT)); first_code_done = True
            if text.strip():
                cells.append(cell("code", "%%python\n" + text))
        else:
            cells.append(copy.deepcopy(c))
    out["cells"] = cells
    out["metadata"]["kernelspec"] = {"display_name": "C++23", "language": "cpp", "name": "xcpp23"}
    out["metadata"]["language_info"] = {"name": "cpp", "codemirror_mode": "text/x-c++src", "file_extension": ".cpp", "mimetype": "text/x-c++src", "version": "23"}
    json.dump(out, open(dst / nb_path.name, "w"), indent=1, ensure_ascii=False)
    print(f"{nb_path.name}: {sum(1 for c in cells if c['cell_type']=='code')} code cells")
