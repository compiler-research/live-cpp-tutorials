# The browser kernel

The xcpp23 kernel of the site is xeus-cpp on wasm32 hosting Python through cppjit, with Clad built into CppInterOp: a C++
cell can call `clad::gradient` and a Python cell can do the same through `cppjit.cppdef`. Built on 2026-11-04 by
`tools/build-wasm-kernel.sh` with emsdk 4.0.9 against an LLVM 23 (release/23.x, 2875c607) built for wasm32 with the
ci-workflows `llvm-wasm` recipe: WebAssembly target only, -Oz, full LTO, `-mtail-call`, and emscripten-forge's two Clang
interpreter patches (`LLVM_WASM_DIR` in the script; `lite/README-build.md` has the measurements). The environment lock is
`lite/env/xeus-kernels.explicit.txt`; its emscripten-forge llvm package is what the script uses when `LLVM_WASM_DIR` is
unset, and what `build-kernel.yml` builds today (a kernel 8 MB larger on the wire, otherwise the same).

Pins: CppInterOp main 8bf7250 (2026-10-31) plus pull request 1167, cppjit main 0332d76, xeus-cpp main 65584a8, Clad
90a623d6 (2026-10-31, the merge of vgvassilev/clad#2453). Patches: `PATCHES.md`. CppInterOp is a static library in this line (its #1149), so LLVM, Clang,
lld and Clad are inside `xcpp.wasm` and there is no separate CppInterOp module to fetch.

The built kernel is the release asset `kernel-overlay-2026-11-03.tar.gz` of this repository: the files no conda package
owns (`xcpp.js`, `xcpp.wasm`, `xcpp.data`, the `xcpp23` kernel spec). `tools/setup-lite-env.sh` lays it over the locked
environment after checking it against `SHA256SUMS` here. The site itself never rebuilds the kernel.

`xcpp.wasm` is linked at `-O1` and then passed through binaryen's `wasm-opt -Oz` on a machine with 12 GB of memory
(`tools/build-wasm-kernel.sh wasm-opt`); the two steps are separate because wasm-opt needs more memory than the build
container has. Numbers in `lite/README-build.md`.
