#!/usr/bin/env bash
# Recreate, from the repository plus one saved kernel artifact, everything tools/build-lite-site.sh needs:
#
#   SP=<empty dir> bash tools/setup-lite-env.sh
#
# Produces under $SP:
#   bin/micromamba                      pinned release (MICROMAMBA_URL)
#   site-venv/                          host side: jupyter lite build + empack, pinned (lite/env/site-env.requirements.txt,
#                                       constrained by lite/env/build-env.pip-freeze.txt, the 2026-09-20 build environment)
#   mamba/envs/xeus-kernels/            the wasm32 environment of the kernel build, from the explicit lock
#                                       (lite/env/xeus-kernels.explicit.txt), plus the kernel overlay: the xcpp23 kernel
#                                       binaries and spec (KERNEL_ART/kernel-overlay-*.tar.gz, the part that takes an hour to
#                                       rebuild: see lite/kernel/README.md)
#   mamba/envs/xeus-slim/, xeus-lazy/   derived by deleting conda-meta entries (lite/env/*-remove.txt) and kernel specs
#
# Network: GitHub (micromamba), PyPI, prefix.dev (emscripten-forge-4x). No sudo. About 10 minutes.
set -euo pipefail
: "${SP:?set SP to an empty directory}"
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}
KERNEL_ART=${KERNEL_ART:-$REPO/lite/kernel-artifacts}   # kernel-overlay-*.tar.gz from the GitHub release
MICROMAMBA_URL=${MICROMAMBA_URL:-https://github.com/mamba-org/micromamba-releases/releases/download/2.9.0-0/micromamba-linux-64}
MICROMAMBA_SHA256=${MICROMAMBA_SHA256:-366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3}   # linux-64, release 2.9.0-0
PY=${PY:-python3}
mkdir -p "$SP/bin" "$SP/mamba"

if [ ! -x "$SP/bin/micromamba" ]; then
  echo "[setup] micromamba <- $MICROMAMBA_URL"
  curl -sSL -o "$SP/bin/micromamba" "$MICROMAMBA_URL"
  # verified against a digest committed here, not one fetched next to the binary
  (cd "$SP/bin" && echo "$MICROMAMBA_SHA256  micromamba" | sha256sum -c -) && chmod +x "$SP/bin/micromamba"
fi
"$SP/bin/micromamba" --version

if [ ! -x "$SP/site-venv/bin/jupyter" ]; then
  echo "[setup] host environment (jupyter lite build, empack)"
  "$PY" -m venv "$SP/site-venv"
  "$SP/site-venv/bin/pip" install -q -c "$REPO/lite/env/build-env.pip-freeze.txt" -r "$REPO/lite/env/site-env.requirements.txt"
fi
"$SP/site-venv/bin/jupyter" lite --version | xargs echo "  jupyterlite-core"

export MAMBA_ROOT_PREFIX="$SP/mamba"
K="$SP/mamba/envs/xeus-kernels"
if [ ! -d "$K/conda-meta" ]; then
  echo "[setup] wasm32 kernel environment from the explicit lock"
  "$SP/bin/micromamba" create -y -q -p "$K" --platform emscripten-wasm32 -f "$REPO/lite/env/xeus-kernels.explicit.txt"
fi
echo "  $(ls "$K/conda-meta"/*.json | wc -l) packages"

OVERLAY=$(ls "$KERNEL_ART"/kernel-overlay-*.tar.gz 2>/dev/null | tail -1)
[ -n "$OVERLAY" ] || { echo "no kernel-overlay-*.tar.gz in $KERNEL_ART (download the kernel release assets there first)"; exit 2; }
# the kernel assets must match the digests committed in the repository (lite/kernel/SHA256SUMS), not ones shipped with them
(cd "$KERNEL_ART" && sha256sum -c --ignore-missing "$REPO/lite/kernel/SHA256SUMS")
if [ ! -f "$K/bin/xcpp.wasm" ]; then
  echo "[setup] kernel overlay <- $OVERLAY"
  tar xzf "$OVERLAY" -C "$K"
fi
ls -la "$K"/bin/xcpp.* | awk '{printf "  %6.1f MB %s\n",$5/1048576,$9}'

# The kernel spec in the overlay names the kernel binary by the absolute path of the machine that built it; jupyterlite-xeus
# finds xcpp.js/.wasm/.data next to argv[0], so point it at this prefix (and at each derived prefix below).
point_kernelspec() {  # point_kernelspec <prefix>
  "$PY" - "$1" <<'PY'
import json, sys, pathlib
prefix = pathlib.Path(sys.argv[1])
for ks in (prefix / "share/jupyter/kernels").glob("*/kernel.json"):
    d = json.load(open(ks)); d["argv"][0] = str(prefix / "bin" / pathlib.Path(d["argv"][0]).name)
    json.dump(d, open(ks, "w"), indent=2)
PY
}
point_kernelspec "$K"

derive() {  # derive <src env> <dst env> <remove list>...: copy, then drop conda-meta entries and kernel specs
  local src=$1 dst=$2; shift 2
  case "$dst" in */mamba/envs/*) ;; *) echo "refusing to remove $dst"; exit 2;; esac
  rm -rf "$dst" && cp -a "$src" "$dst"
  for list in "$@"; do
    for p in $(grep -v '^#' "$list"); do rm -f "$dst"/conda-meta/"$p"-[0-9]*.json; done
  done
  for ks in $(grep -v '^#' "$REPO/lite/env/kernelspecs-remove.txt"); do rm -rf "$dst/share/jupyter/kernels/$ks"; done
  rm -rf "$dst/share/jupyter/labextensions"
  point_kernelspec "$dst"
  echo "  $(basename "$dst"): $(ls "$dst"/conda-meta/*.json | wc -l) packages, kernels: $(ls "$dst/share/jupyter/kernels")"
}
echo "[setup] derived environments"
derive "$K" "$SP/mamba/envs/xeus-slim" "$REPO/lite/env/slim-remove.txt"
derive "$K" "$SP/mamba/envs/xeus-lazy" "$REPO/lite/env/slim-remove.txt" "$REPO/lite/env/lazy-remove.txt"
echo "SETUP_DONE $SP"
