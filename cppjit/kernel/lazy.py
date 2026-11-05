"""Load SciPy and matplotlib on first import instead of at kernel start (browser kernel only).

The JupyterLite xeus kernel unpacks every package of its environment before the first cell runs. This module keeps
the environment at python + numpy and fetches the rest when a notebook first imports it:

  * `install()` registers an import hook and starts background downloads of the package tarballs (a `fetch` in the
    kernel's worker; it completes while the reader works through the first cells).
  * on `import scipy` / `import matplotlib` the hook takes the downloaded tarball, or downloads it synchronously if
    it has not arrived yet, extracts it into the kernel filesystem and lets the import proceed.

Fetching goes through `emscripten_run_script_string` from a tiny C++ helper compiled with cppjit, because the kernel's
Python has no sockets. The tarballs are the ones the site build packed, served under `<site>/lazy/`.
Native Python never imports this file: the notebooks only use it through the browser bootstrap cell."""
import sys, os, json, time, tarfile, importlib, importlib.abc, importlib.machinery

GROUPS = {}           # top-level module name -> list of tarball file names (lazy.json names packages; lazy/index.json,
                      # written by the site build from the tarballs it packed, maps a package to its file)
_cpp_ready = False
_state = {}           # tarball -> "fetched" | "extracted"

_CPP = r'''
#include <string>
extern "C" char* emscripten_run_script_string(const char* script);
extern "C" void emscripten_run_script(const char* script);
namespace sc26lazy {
  std::string base() { return emscripten_run_script_string("self.location.href.split('/extensions/')[0]"); }
  // synchronous XHR (allowed in a worker) into the kernel filesystem; returns the byte count or an error text
  std::string fetch_sync(const std::string& url, const std::string& path) {
    std::string js = "(function(){ try { var x = new XMLHttpRequest(); x.open('GET', '" + url + "', false);"
      " x.responseType = 'arraybuffer'; x.send(null); if (x.status != 200) return 'http ' + x.status;"
      " FS.writeFile('" + path + "', new Uint8Array(x.response)); return String(x.response.byteLength); }"
      " catch (e) { return 'error ' + String(e); } })()";
    return emscripten_run_script_string(js.c_str());
  }
  // background fetch: the worker's event loop runs between cells, so the file appears while the reader works
  void fetch_async(const std::string& url, const std::string& path) {
    std::string js = "fetch('" + url + "').then(r => { if (!r.ok) throw new Error('http ' + r.status); return r.arrayBuffer(); })"
      ".then(b => { if (FS.analyzePath('" + path + ".done').exists) return; FS.writeFile('" + path + ".part', new Uint8Array(b)); FS.rename('" + path + ".part', '" + path + "'); })"
      ".catch(e => { console.log('sc26 lazy prefetch failed', '" + url + "', String(e)); });";
    emscripten_run_script(js.c_str());
  }
}
'''

CACHE = "/tmp/sc26-lazy"


def _cpp():
    global _cpp_ready
    if not _cpp_ready:
        import cppjit
        cppjit.cppdef(_CPP); _cpp_ready = True
    import cppjit
    return cppjit.gbl.sc26lazy


import re as _re
_NAME = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*\.(tar\.gz|json|so)$")
_BASE = _re.compile(r"^https?://[A-Za-z0-9.:_/%+-]*$")


def _url(tarball):
    """The tarball URL. Both parts end up inside a JavaScript string literal, so only plain characters are allowed."""
    base = str(_cpp().base())   # cppjit hands back a std::string proxy
    if not _NAME.match(tarball): raise ImportError(f"sc26 lazy: refusing tarball name {tarball!r}")
    if not _BASE.match(base): raise ImportError(f"sc26 lazy: refusing site base {base!r}")
    return base + "/lazy/" + tarball


def prefetch(names=None):
    """Start background downloads for the given top-level modules (default: all known)."""
    os.makedirs(CACHE, exist_ok=True)
    for name in (names or list(GROUPS)):
        for tb in GROUPS[name]:
            path = os.path.join(CACHE, tb)
            if not _NAME.match(tb): continue
            if not os.path.exists(path) and _state.get(tb) is None:
                _cpp().fetch_async(_url(tb), path); _state[tb] = "fetching"


def ensure(name, verbose=True):
    """Make the top-level module `name` importable: download what is missing, extract, done."""
    if name not in GROUPS: return
    t0 = time.time(); fetched = 0
    for tb in GROUPS[name]:
        if _state.get(tb) == "extracted": continue
        path = os.path.join(CACHE, tb)
        if not os.path.exists(path):
            r = str(_cpp().fetch_sync(_url(tb), path))
            if not r.isdigit(): raise ImportError(f"sc26 lazy: could not fetch {tb}: {r}")
            fetched += int(r)
        with tarfile.open(path) as t: t.extractall("/", filter="data")
        os.remove(path); open(path + ".done", "w").close(); _state[tb] = "extracted"
    importlib.invalidate_caches()
    if verbose:
        how = f"{fetched / 1048576:.1f} MB downloaded now" if fetched else "already downloaded in the background"
        print(f"[browser] {name} unpacked in {time.time() - t0:.1f} s ({how})", file=sys.stderr)


def load_library(name, verbose=True):
    """Download the shared library `<site>/lazy/<name>` once and load it into the kernel (cppjit.load_library).
    For libraries only one notebook needs: files under the notebook's data/ are packed into every kernel's start-up
    download, files under lazy/ are fetched by the notebook that asks for them."""
    import cppjit
    path = os.path.join(CACHE, name)
    if _state.get(name) == "loaded": return path
    os.makedirs(CACHE, exist_ok=True); t0 = time.time()
    r = str(_cpp().fetch_sync(_url(name), path))
    if not r.isdigit(): raise ImportError(f"sc26 lazy: could not fetch {name}: {r}")
    cppjit.load_library(path); _state[name] = "loaded"
    if verbose: print(f"[browser] {name}: {int(r) / 1048576:.1f} MB downloaded and loaded in {time.time() - t0:.1f} s", file=sys.stderr)
    return path

class _Finder(importlib.abc.MetaPathFinder):
    """On the first import of a lazy top-level module, fetch and extract it, then defer to the normal finders."""
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in GROUPS and any(_state.get(tb) != "extracted" for tb in GROUPS[top]):
            ensure(top)
        return None   # the regular path finder now finds the extracted package


def install(show_png=None):
    """Register the hook, start the background downloads, and make matplotlib draw into the notebook."""
    here = os.path.dirname(os.path.abspath(__file__))
    groups = json.load(open(os.path.join(here, "lazy.json")))
    os.makedirs(CACHE, exist_ok=True)
    index_path = os.path.join(CACHE, "index.json")
    r = str(_cpp().fetch_sync(_url("index.json"), index_path))
    index = json.load(open(index_path)) if r.isdigit() else {}
    if not index: print("[browser] sc26 lazy: no lazy/index.json on the site, on-demand packages unavailable", file=sys.stderr)
    for mod, pkgs in groups.items():
        files = []
        for pk in pkgs:
            if pk.endswith(".tar.gz"): files.append(pk)                  # an explicit file name passes through
            elif pk in index: files.append(index[pk])
            # a package the environment no longer has is simply not part of the group
        if files: GROUPS[mod] = files
    sys.meta_path.insert(0, _Finder())
    os.environ.setdefault("MPLBACKEND", "Agg"); os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
    if show_png is not None:
        # matplotlib has no Jupyter backend in this kernel: plt.show() saves a PNG and the C++ helper displays it.
        _patch_pyplot(show_png)
    prefetch()


def _patch_pyplot(show_png):
    class PyplotPatch(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "matplotlib.pyplot": return None
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec is None or spec.loader is None: return None
            real_exec = spec.loader.exec_module
            def exec_module(module):
                real_exec(module)
                def _show(*a, **k):
                    module.savefig("/tmp/_fig.png", dpi=90, bbox_inches="tight"); module.close("all"); show_png("/tmp/_fig.png")
                module.show = _show
            spec.loader.exec_module = exec_module
            return spec
    sys.meta_path.insert(0, PyplotPatch())
