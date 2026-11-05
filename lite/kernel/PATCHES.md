# The browser kernel's source patches

The kernel and the native cppjit wheel are built from CppInterOp, cppjit, xeus-cpp and Clad at the commits in `README.md`
(Clad at 90a623d6, which carries vgvassilev/clad#2453: without it the kernel hung after any parse error),
with the patches below (`tools/build-wasm-kernel.sh` applies them with `git am -3`, in this order per project; the wheel
adds the three CppInterOp follow-ups of #830 that install Clad's runtime headers next to the library).

**Not copied here.** The patches by Vipul Cariappa were written for `Vipul-Cariappa/jupyterlite-deploy` (commit 3379385,
2026-08-25), a repository without a licence file; the build script fetches them from
`https://github.com/Vipul-Cariappa/jupyterlite-deploy/tree/3379385/patches` (`PATCHES=` points at a local copy). Aaron
Jomy's change is CppInterOp pull request 1167; its diff (head of 2026-11-02) is `patches/cppinterop-000-...diff`, carried here
because CppInterOp is Apache-2.0 with LLVM exceptions. Of Vipul's CppInterOp patches, 002 is upstream
(#1157) and is skipped; his cppjit 001, 002, 004 and 005 are superseded on cppjit main (the external-CppInterOp path, the
RTLD_GLOBAL preload) and replaced by our `cppjit-001`; his 003 still applies and is used.

**In `patches/`, under the repository licence** (ours):

| patch | what it does |
|---|---|
| `cppinterop-000` | CppInterOp PR 1167, Enable Clad plugin in WASM (Aaron Jomy, Apache-2.0 with LLVM exceptions): Clad cross-built with a host clad-tblgen, headers at `/include` in the wasm filesystem |
| `cppinterop-001` | the clad cross-build no longer receives `-fwasm-exceptions` before LLVM's `-fno-exceptions` (emcc rejected the pair) |
| `cppinterop-002` | the static Emscripten library's CMake config carries the Clad archives, without a `--whole-archive` pair (which strips libc) |
| `cppjit-001` | libcppjit as a wasm side module against an external CppInterOp: wasm Python headers, `SIDE_MODULE`, virtual-filesystem paths |
| `cppjit-002` | `CPPJIT_ENABLE_CLAD`: the bundled CppInterOp built with the Clad plugin, its runtime headers shipped under `interop/include/clad` (the native wheel of the release) |
| `xeus-cpp-019` | WebGPU linked into the kernel, device handed over from `post.js` |
| `xeus-cpp-020` | cppjit's package layout (`cppjit/libcppjit.so`) and the Clad runtime headers preloaded at `/include/clad` |
| `xeus-cpp-021` | `libclangCppInterOp.so` listed in the kernel spec only when CppInterOp is a shared library |
| `xeus-cpp-022` | `XEUS_CPP_WASM_LINK_OPTIONS`, link options applied after xeus-lite's defaults |
| `xeus-cpp-023` | the preloaded filesystem leaves out the sysroot's graphics and audio headers, other architectures' intrinsics and a few stdlib modules (about 16 MB raw) |
| `cppinterop-followup-001`, `-002` | for the native wheel only: Clad's runtime headers found next to the installed library and installed with it (the three follow-ups of CppInterOp #830, less the Clad pin the build overrides); tests for the parse-error path, the gradient and `getCode` |

**Referenced** (third party, applied by the build script):

| patch | subject | author |
|---|---|---|
| `CppInterOp-001` | Let `Declare` target a specific interpreter | Vipul Cariappa |
| `CppInterOp-003` | Look symbols up by IR name when the linker name misses | Vipul Cariappa |
| `CppInterOp-004` | Do not inspect a nonexistent executable when initializing the dyld | Vipul Cariappa |
| `cppjit-003` | Key the string converters on the typedef spellings too | Vipul Cariappa |
| `xeus-cpp-001` | supporting cppyy | Vipul Cariappa |
| `xeus-cpp-002` | implement sub-interpreters | Vipul Cariappa |
| `xeus-cpp-003` | add example notebook | Vipul Cariappa |
| `xeus-cpp-004` | supporting cppyy | Vipul Cariappa |
| `xeus-cpp-005` | update the kernels.json.in | Vipul Cariappa |
| `xeus-cpp-006` | Drive the `%%python` magic with cppjit | Vipul Cariappa |
| `xeus-cpp-007` | Migrate to CppInterOp's typed handle API | Vipul Cariappa |
| `xeus-cpp-008` | Don't end a stream capture the failure path never began | Vipul Cariappa |
| `xeus-cpp-009` | Flush Python's stream buffers before ending the capture | Vipul Cariappa |
| `xeus-cpp-010` | Point the wasm kernel's embedded Python at cppjit | Vipul Cariappa |
| `xeus-cpp-011` | Say why `%%python` failed, and let Python run when cppjit will not | Vipul Cariappa |
| `xeus-cpp-012` | Stop a magic's argument from swallowing the cell's first line | Vipul Cariappa |
| `xeus-cpp-013` | Preload the CppInterOp headers the interpreter is told to use | Vipul Cariappa |
| `xeus-cpp-014` | Track the preloaded python files as link dependencies | Vipul Cariappa |
| `xeus-cpp-015` | Echo the value of a `%%python` cell's last expression | Vipul Cariappa |
| `xeus-cpp-016` | Preload the Python C-API headers | Vipul Cariappa |
| `xeus-cpp-017` | Ship only the C++23 and C23 kernels in the wasm build | Vipul Cariappa |
| `xeus-cpp-018` | Keep other kernels out of the wasm filesystem image | Vipul Cariappa |

## Upstream status, checked 2026-11-03

Against the GitHub `main` branches (CppInterOp 8bf7250, cppjit 0332d76, xeus-cpp 65584a8, the pins) and the three
repositories' pull-request lists, by content, not by memory:

| patch | upstream |
|---|---|
| Clad: discard after a repl error on clang >= 22 | merged, vgvassilev/clad#2453 (90a623d6, 2026-10-31); the pin includes it, nothing carried |
| Vipul `CppInterOp-002` (CppInterOp already in the process) | merged, compiler-research/CppInterOp#1157; not applied |
| `cppinterop-000` (PR 1167, Clad in wasm) | open, head b6411e3, unchanged since the copy; its CI rows fail (the next two rows) |
| `cppinterop-001`, `cppinterop-002` | not upstream; fixes for #1167, to go on that pull request. #1168 (open) moves `-flto` into the all-targets flags, which `cppinterop-001` strips for clad as well; compatible |
| `cppinterop-followup-001`, `-002` | not upstream (follow-ups of #830, still to be filed) |
| Vipul `CppInterOp-003` (symbol lookup by IR name) | open as compiler-research/CppInterOp#1158, grown beyond the referenced patch (DynamicLibraryManagerSymbol, tests); the referenced 2026-08 version is what the build applies |
| Vipul `CppInterOp-001`, `-004` | no pull request |
| `cppjit-001`, `cppjit-002`, Vipul `cppjit-003` | not upstream; cppjit main has no Emscripten support and no Clad option |
| `xeus-cpp-001` to `-018` (Vipul), `-019` to `-023` (ours) | not upstream; xeus-cpp main has no cppjit-hosted `%%python`, no sub-interpreters, no WebGPU link. compiler-research/xeus-cpp#499 (open) builds xeus-cpp as an LLVM external project for Emscripten and is unrelated |

