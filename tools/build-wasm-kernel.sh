#!/usr/bin/env bash
# Build the browser kernel: xeus-cpp + cppjit + CppInterOp (with Clad) on wasm32, LLVM 23 line, 2026-11-03.
#
#   SP=<scratch> bash tools/build-wasm-kernel.sh envs        # micromamba envs: wasm32 kernel env from the lock, native LLVM 23 tools
#   SP=<scratch> bash tools/build-wasm-kernel.sh sources     # clone at the pins, apply the patches (lite/kernel/PATCHES.md)
#   SP=<scratch> bash tools/build-wasm-kernel.sh build       # tblgen tools, CppInterOp (+Clad), cppjit, xeus-cpp -> $SP/mamba/envs/xeus-kernels
#   SP=<scratch> bash tools/build-wasm-kernel.sh wasm-opt    # binaryen -Oz over xcpp.wasm (needs ~12 GB of memory; may run elsewhere)
#   SP=<scratch> bash tools/build-wasm-kernel.sh overlay <tag>   # kernel-overlay-<tag>.tar.gz + its SHA-256 line
#   SP=<scratch> bash tools/build-wasm-kernel.sh wheel         # the native cppjit wheel with Clad inside (Python 3.12, Linux x86_64)
#
# Needs: emsdk 4.0.9 at $EMSDK (emsdk install 4.0.9 && emsdk activate 4.0.9), $SP/bin/micromamba (tools/setup-lite-env.sh
# puts one there), git, curl. Patches by Vipul Cariappa are fetched from his repository (PATCHES= for a local copy); the
# rest, Aaron Jomy's PR 1167 diff included, is lite/kernel/patches/. About an hour on 4 cores (.github/workflows/build-kernel.yml
# runs exactly this on a GitHub runner and attaches the results to a release).
set -euo pipefail
: "${SP:?set SP to the scratch directory}" "${EMSDK:?set EMSDK to an emsdk 4.0.9 checkout}"
REPO=${REPO:-$(cd "$(dirname "$0")/.." && pwd)}
OURS=$REPO/lite/kernel/patches
PATCHES=${PATCHES:-}   # directory with Vipul Cariappa's CppInterOp-*/cppjit-*/xeus-cpp-*.patch; fetched when empty
THIRD_PARTY_URL=https://raw.githubusercontent.com/Vipul-Cariappa/jupyterlite-deploy/3379385/patches
# CppInterOp pull request 1167 (Aaron Jomy, "Enable Clad plugin in WASM") as the diff of its head on 2026-11-02; CppInterOp is
# Apache-2.0 with LLVM exceptions, so the diff is carried here rather than fetched from a moving pull request.
PR1167_DIFF=$OURS/cppinterop-000-pr1167-enable-clad-plugin-in-wasm.diff
CPPINTEROP_COMMIT=8bf7250bb4cd9d10d733eb3bc0841daa9ac1388f   # main, 2026-10-31
CPPJIT_COMMIT=0332d7688e17e93b0e8735ba54ca0e3d7f0fbaaf       # main, 2026-11-02
XEUS_CPP_COMMIT=65584a89c9c81f26466abcad7f498f3da3917eb2     # main, 2026-10-21
CLAD_COMMIT=90a623d62891b044575c0c7d425b216e17deb2ef            # 2026-10-31, merge of vgvassilev/clad#2453 (discard after a repl error on all clang versions)
CLANG_MAJOR=23
export MAMBA_ROOT_PREFIX=$SP/mamba
PREFIX=$SP/mamba/envs/xeus-kernels; NATIVE=$SP/mamba/envs/native-llvm; W=$SP/kernel-work
SYSROOT_PATH=$EMSDK/upstream/emscripten/cache/sysroot
JOBS=${JOBS:-$(nproc)}
# LLVM_WASM_DIR: an LLVM/Clang/lld install for wasm32 to build against instead of the environment's emscripten-forge llvm
# package (for example a ci-workflows llvm-wasm recipe tree: WebAssembly target only, -Oz; see lite/README-build.md).
LLVM_WASM_DIR=${LLVM_WASM_DIR:-}
LLVM_ROOT=${LLVM_WASM_DIR:-$PREFIX}
MM=$SP/bin/micromamba
G="-c user.name=kernel-build -c user.email=kernel-build@localhost"
stage=${1:-}

envs() {
  [ -d "$PREFIX/conda-meta" ] || "$MM" create -y -q -p "$PREFIX" --platform emscripten-wasm32 -f "$REPO/lite/env/xeus-kernels.explicit.txt"
  [ -d "$NATIVE/conda-meta" ] || "$MM" create -y -q -p "$NATIVE" -c conda-forge python=3.12 cmake ninja "llvmdev=23.1" "clangdev=23.1" zlib zstd libxml2
  echo "envs ready: $(ls "$PREFIX"/conda-meta/*.json | wc -l) wasm32 packages, native llvm $("$NATIVE/bin/llvm-config" --version)"
}

fetch_third_party() {
  if [ -z "$PATCHES" ]; then
    PATCHES=$W/third-party-patches; mkdir -p "$PATCHES"
    for p in CppInterOp-001 CppInterOp-003 CppInterOp-004 cppjit-003 $(seq -f 'xeus-cpp-%03g' 1 18); do
      [ -f "$PATCHES/$p.patch" ] || curl -sSL --retry 3 -o "$PATCHES/$p.patch" "$THIRD_PARTY_URL/$p.patch"
    done
  fi
}

clone_at() {  # clone_at <dir> <url> <commit>
  [ -d "$W/$1" ] || git clone -q "$2" "$W/$1"
  git -C "$W/$1" checkout -q "$3"
}

sources() {
  mkdir -p "$W"; fetch_third_party
  clone_at CppInterOp https://github.com/compiler-research/CppInterOp.git "$CPPINTEROP_COMMIT"
  clone_at cppjit     https://github.com/compiler-research/cppjit.git     "$CPPJIT_COMMIT"
  clone_at xeus-cpp   https://github.com/compiler-research/xeus-cpp.git   "$XEUS_CPP_COMMIT"
  clone_at clad       https://github.com/vgvassilev/clad.git              "$CLAD_COMMIT"
  # CppInterOp: PR 1167 (Clad in wasm), Vipul's 001/003/004 (002 is upstream), ours
  (cd "$W/CppInterOp" && git apply "$PR1167_DIFF" && git $G commit -qam "CppInterOp PR 1167: Enable Clad plugin in WASM (Aaron Jomy)" \
     && git $G am -3 -q "$PATCHES"/CppInterOp-001.patch "$PATCHES"/CppInterOp-003.patch "$PATCHES"/CppInterOp-004.patch \
     && git $G am -q "$OURS"/cppinterop-00[1-9]-*.patch)   # the follow-ups are for the native wheel only
  (cd "$W/cppjit"   && git $G am -q "$OURS"/cppjit-00[1-9]-*.patch && git $G am -3 -q "$PATCHES"/cppjit-003.patch)
  (cd "$W/xeus-cpp" && git $G am -3 -q "$PATCHES"/xeus-cpp-0{01..18}.patch && git $G am -q "$OURS"/xeus-cpp-0{19,20,21,22,23}-*.patch)
  for d in CppInterOp cppjit xeus-cpp clad; do echo "[$d] now at $(git -C "$W/$d" rev-parse --short HEAD), $(git -C "$W/$d" log --oneline | wc -l) commits"; done
}

build() {
  source "$EMSDK/emsdk_env.sh" >/dev/null 2>&1
  export PATH=$NATIVE/bin:$PATH
  cd "$W"
  echo "[tblgen] host tools against the native LLVM"
  cmake -S CppInterOp -B tblgen -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$NATIVE" -DLLVM_DIR="$NATIVE/lib/cmake/llvm" \
    -DCPPINTEROP_ENABLE_TESTING=OFF -DCMAKE_CXX_STANDARD=17 -DCPPINTEROP_BUILD_TABLEGEN_ONLY=ON >/dev/null
  cmake --build tblgen --target cppinterop-tblgen -j "$JOBS" >/dev/null
  cmake -S clad/utils/clad-tblgen -B clad-tblgen -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLVM_DIR="$NATIVE/lib/cmake/llvm" >/dev/null
  cmake --build clad-tblgen -j "$JOBS" >/dev/null
  echo "[cppinterop] static wasm library with Clad"
  emcmake cmake -S CppInterOp -B build-cppinterop -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$PREFIX" -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DLLVM_DIR="$LLVM_ROOT/lib/cmake/llvm" -DLLD_DIR="$LLVM_ROOT/lib/cmake/lld" -DClang_DIR="$LLVM_ROOT/lib/cmake/clang" \
    -DBUILD_SHARED_LIBS=OFF -DCPPINTEROP_ENABLE_TESTING=OFF -DCMAKE_CXX_STANDARD=17 \
    -DSYSROOT_PATH="$SYSROOT_PATH" -DCPPINTEROP_TABLEGEN_EXE="$W/tblgen/utils/TableGen/cppinterop-tblgen" \
    -DCPPINTEROP_ENABLE_CLAD=ON -DCLAD_SOURCE_DIR="$W/clad" -DCLAD_TABLEGEN_EXE="$W/clad-tblgen/clad-tblgen"
  cmake --build build-cppinterop -j "$JOBS" && cmake --build build-cppinterop --target install >/dev/null
  echo "[cppjit] side module"
  emcmake cmake -S cppjit -B build-cppjit -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$PREFIX" \
    -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ON -DCppInterOp_DIR="$PREFIX/lib/cmake/CppInterOp"
  cmake --build build-cppjit -j "$JOBS"
  echo "[xeus-cpp] kernel (linked at -O1: binaryen runs in the wasm-opt stage)"
  emcmake cmake -S xeus-cpp -B build-xeus-cpp -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$PREFIX" -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ON \
    -DXEUS_CPP_EMSCRIPTEN_WASM_BUILD=ON -DXEUS_CPP_BUILD_TESTS=OFF "-DCMAKE_EXE_LINKER_FLAGS=-O1${LLVM_WASM_DIR:+ -L$LLVM_WASM_DIR/lib}" \
    -DXEUS_CPP_RESOURCE_DIR="$LLVM_ROOT/lib/clang/$CLANG_MAJOR" -DSYSROOT_PATH="$SYSROOT_PATH" \
    -DCPPJIT_SOURCE_DIR="$W/cppjit" -DCPPJIT_BUILD_DIR="$W/build-cppjit" \
    -DXEUS_CPP_CLAD_INCLUDE_DIR="$W/build-cppinterop/plugins/clad/include"
  cmake --build build-xeus-cpp -j "$JOBS" && cmake --build build-xeus-cpp --target install >/dev/null
  ls -la "$PREFIX"/bin/xcpp.* | awk '{printf "  %7.1f MB %s\n",$5/1048576,$9}'
}

wasm_opt() {  # the same passes emcc runs at -Oz; needs about 12 GB of memory for this module
  local opt=$EMSDK/upstream/bin/wasm-opt f=$PREFIX/bin/xcpp.wasm
  "$opt" --strip-target-features --post-emscripten -Oz --low-memory-unused --zero-filled-memory \
    --pass-arg=directize-initial-contents-immutable --no-stack-ir "$f" -o "$f.opt" \
    --mvp-features --enable-threads --enable-bulk-memory --enable-bulk-memory-opt --enable-call-indirect-overlong \
    --enable-exception-handling --enable-multivalue --enable-mutable-globals --enable-nontrapping-float-to-int \
    --enable-reference-types --enable-sign-ext --enable-simd --enable-tail-call
  mv "$f.opt" "$f"; ls -la "$f" | awk '{printf "  %7.1f MB %s\n",$5/1048576,$9}'
}

wheel() {  # cppjit with CppInterOp built with Clad, against the native LLVM: the release's cppjit-*.whl
  # cloned without a checkout: the source tree sits on a detached HEAD, which a plain clone would not check out
  [ -d "$W/CppInterOp-native" ] || git clone -q --no-checkout "$W/CppInterOp" "$W/CppInterOp-native"
  # the three follow-ups of CppInterOp #830: Clad's runtime headers found next to the installed library, and installed
  (cd "$W/CppInterOp-native" && git checkout -q "$(git -C "$W/CppInterOp" rev-parse HEAD)" \
     && git $G am -3 "$OURS"/cppinterop-followup-*.patch \
     && grep -q "clad_runtime_include_dir\|install(DIRECTORY \${CMAKE_BINARY_DIR}/plugins/clad/include/clad" plugins/clad/CMakeLists.txt lib/CppInterOp/CMakeLists.txt CMakeLists.txt \
     || { echo "the Clad follow-ups did not apply"; exit 1; })
  "$NATIVE/bin/python" -m venv "$SP/wheel-venv" && "$SP/wheel-venv/bin/pip" install -q scikit-build-core ninja cmake
  export PATH=$NATIVE/bin:$PATH CMAKE_PREFIX_PATH=$NATIVE CMAKE_BUILD_PARALLEL_LEVEL=$JOBS
  export CMAKE_ARGS="-DLLVM_DIR=$NATIVE/lib/cmake/llvm -DClang_DIR=$NATIVE/lib/cmake/clang -DCMAKE_C_COMPILER=$NATIVE/bin/clang -DCMAKE_CXX_COMPILER=$NATIVE/bin/clang++ -DCPPINTEROP_SOURCE_DIR=$W/CppInterOp-native -DCPPJIT_ENABLE_CLAD=ON -DCPPJIT_CLAD_SOURCE_DIR=$W/clad"
  (cd "$W/cppjit" && "$SP/wheel-venv/bin/pip" wheel --no-deps --no-build-isolation -w "$SP" .)
  (cd "$SP" && ls cppjit-*.whl && sha256sum cppjit-*.whl)
}

overlay() {  # the files no conda package owns; the file is kernel-overlay-<date>.tar.gz whether the tag carries the kernel- prefix or not
  local tag=${2:?tag}; tag=${tag#kernel-}; cd "$PREFIX"
  tar czf "$SP/kernel-overlay-$tag.tar.gz" bin/xcpp.js bin/xcpp.wasm bin/xcpp.data share/jupyter/kernels/xcpp23
  (cd "$SP" && sha256sum "kernel-overlay-$tag.tar.gz")
}

case "$stage" in
  envs) envs;; sources) sources;; build) build;; wasm-opt) wasm_opt;; overlay) overlay "$@";; wheel) wheel;;
  all) envs; sources; build;;
  *) echo "usage: $0 envs|sources|build|wasm-opt|overlay <tag>|wheel|all"; exit 2;;
esac
