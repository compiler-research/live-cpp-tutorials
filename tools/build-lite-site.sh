#!/usr/bin/env bash
# Build the slim JupyterLite site for the home notebooks: the rebuilt xcpp23 kernel (C++ hosting Python through cppjit),
# python + numpy in the kernel's start-up set (SciPy and matplotlib on first import), cppjit/kernel and cppjit/data
# mounted at /cppjit, and the repository's C++ series alongside.
#
#   SP=<dir prepared by tools/setup-lite-env.sh> OUT=<dist dir> bash tools/build-lite-site.sh
#
# $SP holds site-venv (jupyter lite build, empack) and mamba/envs/{xeus-kernels,xeus-slim,xeus-lazy}; see
# tools/setup-lite-env.sh for how they are made and lite/README-build.md for the design.
set -euo pipefail
: "${SP:?}"
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}
SERIES=${SERIES:-$REPO/cppjit}       # the notebooks, kernel/ and data/ that go into the site
OUT=${OUT:-$REPO/lite/dist}
BUILD_ENV=${BUILD_ENV:-$SP/site-venv}; [ -x "$BUILD_ENV/bin/jupyter" ] || BUILD_ENV=$SP/mamba/envs/build-env   # the September layout
PREFIX=${PREFIX:-$SP/mamba/envs/xeus-lazy}   # xeus-slim minus the packages kernel/lazy.py fetches on first import
CONTENT=${CONTENT:-$REPO/lite/content}
export PATH="$BUILD_ENV/bin:$PATH"
for d in "$OUT" "$CONTENT"; do   # the two directories this script deletes and recreates
  case "$d" in ""|/|/home|/home/*/|"$HOME"|"$HOME"/) echo "refusing to use '$d' as an output directory"; exit 2;; esac
done

echo "[content] notebooks -> xcpp23 notebooks"
rm -rf "$CONTENT" && mkdir -p "$CONTENT"
"$BUILD_ENV/bin/python" "$REPO/tools/home2lite.py" "$SERIES" "$CONTENT/cppjit"
# the repository's own C++ series runs in the browser kernel as it is (kernel name mapped to the one the site ships)
"$BUILD_ENV/bin/python" - "$REPO/xeus-cpp" "$CONTENT/cpp" <<'PY'
import json, sys, pathlib
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); dst.mkdir(parents=True, exist_ok=True)
# 10_modular_notebook_design defines a lambda named `log`; the browser kernel already has std::log at global scope
# (its preamble includes <cmath>), so the cell does not compile there. Left out of the site until the notebook or the
# kernel preamble changes; it stays in the native series.
EXCLUDE = {"10_modular_notebook_design.ipynb"}
for nb in sorted(src.glob("*.ipynb")):
    if nb.name in EXCLUDE: continue
    d = json.load(open(nb)); d["metadata"]["kernelspec"] = {"display_name": "C++23", "language": "cpp", "name": "xcpp23"}
    json.dump(d, open(dst / nb.name, "w"), indent=1, ensure_ascii=False)
print(f"[content] {len(list(dst.glob('*.ipynb')))} C++ notebooks -> {dst}")
PY
cp "$REPO/lite/README.md" "$CONTENT/README.md"

# lite/labext holds symlinks to the two extensions the site needs (the xeus kernel extension and the notebook UI); the
# build environment's other extensions (pyodide, javascript, p5 kernels, themes) stay out.
mkdir -p "$REPO/lite/labext/@jupyterlite" "$REPO/lite/labext/@jupyter-notebook"
ln -sfn "$BUILD_ENV/share/jupyter/labextensions/@jupyterlite/xeus" "$REPO/lite/labext/@jupyterlite/xeus"
ln -sfn "$BUILD_ENV/share/jupyter/labextensions/@jupyter-notebook/lab-extension" "$REPO/lite/labext/@jupyter-notebook/lab-extension"
# The lazy packages (SciPy, matplotlib and friends) are the pack step's own tarballs: harvest them once from a build
# against xeus-slim (which still contains them), then build the site against xeus-lazy (which does not).
# The harvest is keyed on the environment lock: a lock change (new builds of SciPy, matplotlib) invalidates it.
LOCKSUM=$(sha256sum "$REPO/lite/env/xeus-kernels.explicit.txt" | cut -c1-16)
if [ ! -f "$REPO/lite/lazy-packages/.lock-$LOCKSUM" ]; then
  echo "[site] harvesting the lazy package tarballs from a pack of xeus-slim (lock $LOCKSUM)"
  rm -rf "$OUT-harvest" "$REPO/lite/.jupyterlite.doit.db"; mkdir -p "$REPO/lite/lazy-packages"
  rm -f "$REPO"/lite/lazy-packages/*.tar.gz "$REPO"/lite/lazy-packages/.lock-*
  (cd "$REPO/lite" && jupyter lite build --contents "$CONTENT" --output-dir "$OUT-harvest" \
     --XeusAddon.prefix="$SP/mamba/envs/xeus-slim" --XeusAddon.empack_config="$REPO/lite/empack_config.yaml" --XeusAddon.default_channels="https://prefix.dev/emscripten-forge-4x" --XeusAddon.default_channels="conda-forge" \
     --LiteBuildConfig.ignore_sys_prefix=True --FederatedExtensionAddon.extra_labextensions_path="$REPO/lite/labext" >/dev/null)
  for p in $(grep -v '^#' "$REPO/lite/env/lazy-remove.txt"); do cp "$OUT-harvest"/xeus/*/kernel_packages/"$p"-[0-9]*.tar.gz "$REPO/lite/lazy-packages/" 2>/dev/null || true; done
  rm -rf "$OUT-harvest"; touch "$REPO/lite/lazy-packages/.lock-$LOCKSUM"; ls "$REPO"/lite/lazy-packages/*.tar.gz | wc -l | xargs echo "  lazy tarballs:"
fi

echo "[site] jupyter lite build -> $OUT"
rm -rf "$OUT" "$REPO/lite/.jupyterlite.doit.db"
cd "$REPO/lite"
jupyter lite build --contents "$CONTENT" --output-dir "$OUT" \
  --XeusAddon.prefix="$PREFIX" --XeusAddon.empack_config="$REPO/lite/empack_config.yaml" --XeusAddon.default_channels="https://prefix.dev/emscripten-forge-4x" --XeusAddon.default_channels="conda-forge" \
  --XeusAddon.mounts="$SERIES/kernel:/cppjit/kernel" --XeusAddon.mounts="$SERIES/data:/cppjit/data" \
  --LiteBuildConfig.ignore_sys_prefix=True \
  --FederatedExtensionAddon.extra_labextensions_path="$REPO/lite/labext"

# The kernel's dynamic loader resolves a module's needed shared libraries (libopenblas.so for numpy, libz.so for pillow)
# by URL next to the kernel script, not through its filesystem; serve them there. Fetched only when first needed.
echo "[site] shared libraries next to the kernel script"
STATIC="$OUT/extensions/@jupyterlite/xeus-extension/static"
for so in libopenblas.so libz.so; do cp -L "$PREFIX/lib/$so" "$STATIC/$so"; done
ls -la "$STATIC"/*.so | awk '{printf "  %7.2f MB  %s\n",$5/1048576,$9}'

# Packages loaded on first import by kernel/lazy.py (not in the start-up set): the tarballs packed from xeus-slim.
echo "[site] lazy packages -> $OUT/lazy/"
mkdir -p "$OUT/lazy" && cp "$REPO"/lite/lazy-packages/*.tar.gz "$OUT/lazy/" && du -sh "$OUT/lazy" | cut -f1 | xargs echo "  lazy packages:"
# package name -> tarball file, read by kernel/lazy.py at start (lazy.json names packages, not builds)
"$BUILD_ENV/bin/python" - "$OUT/lazy" <<'PY'
import json, pathlib, re, sys
d = pathlib.Path(sys.argv[1]); index = {}
for f in sorted(d.glob("*.tar.gz")):
    m = re.match(r"^(.+?)-\d[^-]*-[^-]+\.tar\.gz$", f.name)
    if m: index[m.group(1)] = f.name
json.dump(index, open(d / "index.json", "w"), indent=1); print(f"  lazy/index.json: {len(index)} packages")
PY


# GitHub Pages: no Jekyll processing (it would skip files and folders it considers special)
touch "$OUT/.nojekyll"

echo "[site] kernels: $(cat "$OUT/xeus/kernels.json")"
echo "[site] kernel packages: $(ls "$OUT"/xeus/*/kernel_packages/*.tar.gz | wc -l), $(du -shc "$OUT"/xeus/*/kernel_packages/*.tar.gz | tail -1 | cut -f1)"
du -sh "$OUT" | cut -f1 | xargs echo "[site] total on disk:"
echo "SITE_DONE"
