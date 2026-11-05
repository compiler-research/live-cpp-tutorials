# The notebooks in the browser: how the JupyterLite site is built

Built and verified 2026-11-03 (kernel rebuilt on the LLVM 23 line with Clad inside). The five `cppjit/` notebooks run in
the browser with no install, in the xcpp23 kernel (clang-repl on WebAssembly) that hosts Python through cppjit: Python
cells call C++ in the same process, exactly the pairing the tutorial is about, and `clad::gradient` works live in both.
Output: `lite/dist/` (285 MB on disk).

## What is in it

| part | content |
|---|---|
| kernel | xeus-cpp + cppjit + CppInterOp with Clad built in, on CppInterOp, cppjit and xeus-cpp main of 2026-10/11 (`tools/build-wasm-kernel.sh`, emsdk 4.0.9, emscripten-forge llvm 23.1.2; `lite/kernel/README.md`, `PATCHES.md`) |
| Python packages | python 3.13.1, numpy 2.5.4, scipy 1.18.0, matplotlib-base 3.11.2, pillow 13.0.0 and their dependencies: 31 packages, 24 MB on the wire (the upstream site ships 94 packages, 59 MB) |
| mounts | `cppjit/kernel` at `/cppjit/kernel` (the three headers, `derivatives.py`) and `cppjit/data` at `/cppjit/data` (the Higgs masses) |
| Clad | built into the kernel: notebooks 2, 3 and 5 generate their derivatives live (`kernel/derivatives.py`, the same requests that produced the shipped sources); a C++ cell can call `clad::gradient` directly |
| notebooks | the five home notebooks converted by `tools/home2lite.py`: Python cells become `%%python` cells; two cells at the top set the working directory to `/cppjit` and route `plt.show()` through a C++ display helper |
| extensions | only the xeus kernel extension and the notebook UI (no pyodide, javascript, p5 kernels, no widgets) |

## SciPy and matplotlib on first import, not at start

The xeus kernel unpacks every package of its environment before the first cell runs. The site keeps that start-up
set at python + numpy (20 packages, 6.2 MB) and loads the rest on demand: `cppjit/kernel/lazy.py`, mounted with the
kernel files, registers an import hook and starts background downloads of the SciPy and matplotlib tarballs from the
bootstrap cell (a `fetch` in the kernel's worker through `emscripten_run_script`; the worker's event loop runs between
cells, so the files arrive while the reader works). On the first `import scipy` or `import matplotlib` the hook extracts
the downloaded tarball into the kernel filesystem (about 1 s), or downloads it synchronously first (an XHR, allowed in
a worker) if the reader got there before the background did. The tarballs are served under `lazy/` (18 MB, the same
files the pack step produces; `cppjit/kernel/lazy.json` maps top-level modules to them). `plt.show()` is routed to the
C++ display helper by a second hook that patches `matplotlib.pyplot` as it loads. SciPy stays SciPy in the notebooks.

## Traffic, measured end to end (2026-11-03)

`tools/lite_wire.py`: a local server that compresses like nginx (`gzip` for wasm, js, json, html, so, data; `.tar.gz`
untouched), headless Chromium opening the notebook in the Lab UI and running all cells, every response body counted as
received, kernel worker included (`lite/wire-ledger.json`, `lite/wire-ledger-nb1.json`):

| component | notebook 1 (no SciPy, no plots) | notebook 4 (SciPy, matplotlib, data) |
|---|---:|---:|
| C++ kernel: `xcpp.wasm` (LLVM, Clang, lld, Clad, CppInterOp inside: 97.6 MB raw) 30.8, `xcpp.data` 4.8, glue | 35.8 | 35.8 |
| app shell, extensions, notebook files | 7.8 | 7.8 |
| Python packages at start (python, numpy, 18 small ones) | 6.1 | 6.1 |
| shared libraries on first use (openblas, zlib, xeus) | 0.1 | 2.7 |
| lazy packages on first import (SciPy, the matplotlib group) | 0 | 17.3 |
| **total** | **49.8 MB** | **69.8 MB** |
| kernel ready / last output | 4 s / 13 s | 4 s / 43 s |

September, for comparison (LLVM 22 kernel, CppInterOp as a separate 19.8 MB module): 44.8 MB and 64.4 MB. The LLVM 23
line builds CppInterOp as a static library, so one `xcpp.wasm` carries LLVM, Clang, lld, Clad and CppInterOp: 30.8 MB
gzip after `wasm-opt -Oz` (119.9 MB raw at link, 97.6 after binaryen), against 4.9 + 19.8 MB for the two September
pieces. The growth is LLVM 23 itself (its archives are 13 % larger than 22's), Clad (6 MB raw) and the lld and ORC code
the static layout keeps; `MAIN_MODULE=2` with an export list was tried and dropped: it saves 6 MB raw, 0.5 MB gzip, and
risks a missing export for JIT-compiled cells. The old double fetch of the CppInterOp module is gone with the module.

Run All Cells is the worst case for the lazy loader: the first `import scipy` comes before the background download
has finished, so SciPy (9.9 MB) is downloaded a second time synchronously; measured that way notebook 4 is 79.7 MB.
Reading the notebook at a human pace, the background copy wins and the total is the 69.8 MB above. 220 KB come from `raw.githubusercontent.com` (jupyterlite-xeus' parselmouth mapping), the only request that
leaves the host. A host serving Brotli would take 15 to 20 % more off the wasm and JS; one serving uncompressed would
send the raw sizes (about 170 MB), so check the server's compression once deployed.

## The C++ series in the browser

The repository's `xeus-cpp/` notebooks go into the site unchanged apart from the kernel name (`cpp/`). Checked headlessly
on 2026-11-02: 01, 02, 04 to 09, the project report and the visual guide run; 03 stops at its intentional
redefinition error, as it should; 10 is left out because its lambda named `log` collides with `std::log`, which the
browser kernel's preamble puts in scope (the native kernel does not).

## Two things the kernel needed

**Shared libraries.** Python extension modules that depend on a shared library (numpy on `libopenblas.so`, pillow on
`libz.so`) failed to import with `need to see wasm magic number`. The kernel's dynamic loader resolves a module's
needed libraries by URL next to the kernel script (`extensions/@jupyterlite/xeus-extension/static/`), not through the
in-memory filesystem where the packages put them; jupyterlite-xeus 5.0 preloads shared libraries only for Emscripten
< 4, and this kernel is Emscripten 4.0.9. The 404 page comes back as the "wasm". The upstream deployment has the same
defect: numpy imports there only because its numpy build has no such dependency, and matplotlib fails on pillow.
The fix in `tools/build-lite-site.sh` is to serve `libopenblas.so` and `libz.so` at that URL (fetched once, on first
use) and to leave them out of the packed packages so they are not transferred twice. Worth reporting to
jupyterlite-xeus with the kernel's `emscriptenMajorVersion` branch as the pointer.

**Figures.** matplotlib has no Jupyter backend inside this kernel. The C++ helper cell defines `show_png(path)`, which
reads a PNG and publishes it with `xcpp::display`; the Python bootstrap replaces `plt.show()` with save-then-show.
`xcpp::display` needs `<nlohmann/json.hpp>`, which the upstream pack configuration excluded; the slim configuration keeps
that one header.

## Rebuild from scratch (verified 2026-11-01, 21:30 Sofia)

Everything the site needs is in the repository, except the kernel binaries, which take about an hour to rebuild (plus a
binaryen pass that needs 12 GB of memory) and live as one saved artifact. Two commands, about ten minutes, network to
GitHub, PyPI and prefix.dev, no sudo:

```sh
SP=/some/empty/dir bash tools/setup-lite-env.sh     # micromamba, host venv, wasm32 env from the lock, kernel overlay, slim/lazy envs
SP=/some/empty/dir OUT=lite/dist bash tools/build-lite-site.sh
```

| piece | where | what |
|---|---|---|
| host side | `lite/env/site-env.requirements.txt` + `build-env.pip-freeze.txt` | jupyterlite-core 0.8.3, jupyterlite-xeus 5.0.0, empack 6.0.1, notebook 7.6.2, pinned to the 2026-09-20 build environment |
| wasm32 environment | `lite/env/xeus-kernels.explicit.txt` | micromamba explicit list, 40 packages with md5, emscripten-forge-4x (llvm 23.1.2, emscripten-abi 4.0.9) |
| derived environments | `lite/env/{slim,lazy,kernelspecs}-remove.txt` | build-time-only packages dropped; the lazy ones are packed once from xeus-slim into `lite/lazy-packages/` |
| kernel overlay | `release asset kernel-overlay-2026-11-03.tar.gz` (35.8 MB) | the files of the kernel build that no package owns: `xcpp.{js,wasm,data}` and the `xcpp23` kernel spec |
| kernel source patches and pins | `lite/kernel/`, `tools/build-wasm-kernel.sh` | the 27 third-party patches (CppInterOp 4, cppjit 5, xeus-cpp 18, listed in PATCHES.md) plus our WebGPU patch, Vipul's `deploy.yml`, `environment.yml`, `build-environment.yml`, the upstream pack config; `tools/build-wasm-kernel.sh` rebuilds the kernel from them |

The explicit-lock environment carries no channel history, so the build passes `--XeusAddon.default_channels`
explicitly. The September scratchpad under `/tmp` is no longer needed.

## Building the binaries on a GitHub runner

`.github/workflows/build-kernel.yml` (manual dispatch, input: the release tag) rebuilds both binaries from the repository
alone: micromamba and emsdk 4.0.9 pinned, the wasm32 and native environments from the locks, the sources at the pins with
the patches of `lite/kernel/`, then kernel, `wasm-opt -Oz` (the runner's 16 GB cover binaryen's 11.5 GB), overlay and
wheel. It attaches them with `SHA256SUMS` to the release and opens a pull request that puts the digests into
`lite/kernel/SHA256SUMS` and the release name into the two workflows that download from it: the Pages and cppjit jobs
verify the assets against the repository, never against a file served beside them, so a rebuilt release becomes the
deployed one only through that pull request. About an hour. Under act the release and pull-request steps are skipped
and the files land in the artifact (`act workflow_dispatch -W .github/workflows/build-kernel.yml -j build --input
tag=<tag> ...`).

## Testing the workflows locally with nektos/act

```sh
mkdir -p lite/kernel-artifacts && cp <release asset kernel-overlay-*.tar.gz> lite/kernel-artifacts/
act -W .github/workflows/deploy-pages.yml -j build -P ubuntu-24.04=catthehacker/ubuntu:act-24.04 \
    --use-gitignore=false --artifact-server-path /tmp/act-artifacts
act -W .github/workflows/check-notebooks.yml -j execute-notebooks-cppjit -P ubuntu-latest=catthehacker/ubuntu:act-24.04 \
    --artifact-server-path /tmp/act-artifacts
```

`--use-gitignore=false` matters: act copies the checkout into the container honouring `.gitignore`, and
`lite/kernel-artifacts/` is ignored, so without it the digest check finds no files. `--artifact-server-path` lets the
upload-artifact steps succeed. Under act the release download and the Pages upload/deploy steps are skipped (`ACT=true`);
everything else runs as on GitHub: environment from the locks, site build, headless browser smoke test under a sub-path.
Verified on 2026-11-02 on a 56-core machine: the cppjit CI job in about 10 minutes, the Pages build in about 15.

## Deploy

Any static host serves it; GitHub Pages is the upstream pattern (its `deploy.yml` uploads the `dist` directory as the
Pages artifact). Serve with gzip (Brotli where possible: another 15 to 20 % off the wasm). The links to hand out are
`<site>/lab/index.html?path=cppjit/1_call_it.ipynb` and so on, or `<site>/notebooks/index.html?path=...` for the single-notebook
view. Nothing in the site phones home.

## The LLVM 23 line (2026-11-02/03)

The September kernel was 27 third-party patches on CppInterOp, cppjit and xeus-cpp commits of August, with CppInterOp as
a separate wasm module and no Clad. The kernel now builds from the three projects' main branches plus CppInterOp pull
request 1167 (Clad in wasm) and Clad 90a623d6, with the patches in `lite/kernel/PATCHES.md`. Found on the way, fixed
in our patches and worth sending upstream:

- PR 1167's clad cross-build fails under emsdk 4.0.9 (`-fwasm-exceptions` before LLVM's `-fno-exceptions`), its static
  library's CMake config does not export the Clad archives, and wrapping them in `--whole-archive` strips libc for an
  Emscripten main module (numpy then fails to load for want of `acosf`).
- Clad's plugin discarded the consumer calls of a failed input only for clang < 22, citing llvm/llvm-project#182044,
  which is about virtual files for `input_line_N`, not about this: on clang 23 in wasm the failed input's
  `TopLevelStmtDecl` was replayed into CodeGen on the next cell and the kernel hung after any parse error (found here
  with a Node harness of the kernel's interpreter stack and the inspector's pause). Fixed upstream the same day by
  vgvassilev/clad#2453 (90a623d6), which the pin now includes.
- cppjit's string converters must be keyed on the typedef spellings (Vipul's `cppjit-003`): libc++ spells
  `std::string` out, and without it a `std::string` argument from Python fails to convert.

The module's size is the compiler's: Clang 40 MB, target-independent LLVM 38 MB and the X86 and AArch64 backends 18 MB
of the 126 MB link (linker map), all from emscripten-forge's llvm package, which is built at -O3 with three targets and
as plain wasm objects, so link-time optimisation cannot reach it. Building LLVM ourselves with the ci-workflows
`llvm-wasm` recipe (WebAssembly target only, -Oz, LTO; emsdk 4.0.9 needs `-mtail-call`, and clang 23 needs
emscripten-forge's two interpreter patches) gives 69.4 MB raw / 23.7 MB gzipped after wasm-opt against 103.4 / 32.5,
with cell times unchanged within noise (measured on the z840 builds of 2026-11-04 across -Oz, -Os, -O2, with and without
LTO). `tools/build-wasm-kernel.sh` takes that install through `LLVM_WASM_DIR`, and the release `kernel-2026-11-03`
carries that kernel (the -Oz + LTO build of 2026-11-04, verified twice in the browser on the smoke cells and the five
notebooks). `build-kernel.yml` still builds against the conda package: until the LLVM install is published as a cell or
release asset it can download, a rerun of that workflow proposes the larger kernel's digest. With the smaller kernel the
wire figures in the table above drop by 8.2 MB (the module's gzip size, 32.5 to 24.3 MB): about 41.6 MB for the first
notebook, 61.6 MB with SciPy and matplotlib loaded; to be re-measured on the public site.

The preloaded filesystem (`xcpp.data`) left out what a notebook kernel never includes (the sysroot's SDL, GL, X11 and
sanitizer headers, the other architectures' intrinsics in clang's resource directory, `pydoc_data`): 46.5 to 27.5 MB raw,
6.5 to 4.8 MB gzip, patch `xeus-cpp-023`; a cell including the common C++, emscripten and WebGPU headers and the Python
standard library imports the notebooks use still runs.

The module cannot be optimised in a 7 GB container: binaryen needs about 11.5 GB for this module, so the kernel is linked
at `-O1` and `wasm-opt -Oz` runs as a separate stage on a bigger machine (five minutes on 56 cores).

## What would make it smaller still

| lever | saves | cost |
|---|---:|---|
| ORC out of the wasm interpreter (llvm/llvm-project#175910 is in LLVM main, not 23.x): a backport into the emscripten-forge llvm package or ci-workflows' `llvm-wasm` recipe | 3 to 8 MB | an LLVM rebuild for wasm32 |
| Brotli precompression on the server | 6 to 8 MB | none, server-side |
| matplotlib-base: keep only the Agg backend files | about 0.5 MB | pack rules |
