# live-cpp-tutorials

`live-cpp-tutorials` is a collection of interactive Jupyter notebooks for learning C++, OpenMP, and CUDA - all powered by the [xeus-cpp](https://github.com/compiler-research/xeus-cpp) kernel. Code compiles and runs directly in the notebook; no local toolchain setup is required beyond the conda environment.

Join our discord for discussions and collaboration.

[![Discord](https://github.com/compiler-research/CppInterOp/raw/main/discord.svg)](https://discord.gg/Vkv3ne4zVK)

## About

Each notebook series builds on the previous, taking you from core C++ through shared-memory parallelism with OpenMP to GPU programming with CUDA. Kernels are incremental - state, variables, and `#include`s persist across cells exactly like a Python notebook.

The CUDA notebooks run on a CUDA 12-capable GPU and produce images rendered inline in the notebook.

## Notebooks

### C++ (`xeus-cpp/`)
An introduction to modern C++ through live, interactive examples. Topics include basic syntax, standard containers, templates, and the C++ standard library—all executed cell-by-cell without leaving the browser. These tutorials leverage the Jupyter Notebook interface to allow deep exploration of C++ features like memory management, lambda expressions, object-oriented concepts, and advanced standard library structures in a highly visual, incremental manner.

### OpenMP (`openmp/`)
CPU parallelism using OpenMP pragmas. Covers `#pragma omp parallel`, loop-level parallelism, reductions, and thread synchronization using the OpenMP-enabled `xeus-cpp` kernel. The notebooks guide you step-by-step from foundational concepts like spawning threads and managing shared vs. private data variables, all the way to advanced patterns like task-based parallelism, critical sections, and optimizing performance loops directly in an interactive environment.

### CUDA (`cuda/`)
GPU programming from first principles using CUDA C++. This section explores how to accelerate compute-heavy workloads by utilizing graphics cards. It covers essential GPU architecture concepts, kernel declarations, memory allocation (`cudaMalloc`), host-to-device data transfers, and thread organization across grids and blocks to give you hands-on experience writing raw parallel code optimized for parallel hardware.

## Installation
To ensure a clean setup, install `live-cpp-tutorials` inside a fresh environment using Micromamba. 

Clone the repository and move into the directory:

```
git clone --depth=1 [https://github.com/compiler-research/live-cpp-tutorials.git](https://github.com/compiler-research/live-cpp-tutorials.git)
cd live-cpp-tutorials
```

Create and activate the environment:

```
micromamba env create -f environment.yml
micromamba activate livecpp-ci
```

Launch Jupyter:

```
jupyter lab
```

The environment provides:

- `xeus-cpp` - Jupyter kernel for C++ (Clang 21 / C++23)
- `llvm-openmp` - OpenMP runtime for the parallel notebooks
- `cuda-toolkit 12` - CUDA compiler and runtime for the GPU notebooks

## How it works

xeus-cpp wraps [Clang-Repl](https://clang.llvm.org/docs/ClangRepl.html) - an incremental C++ compiler - behind the [Jupyter protocol](https://jupyter-client.readthedocs.io/en/stable/messaging.html). Each cell is compiled and executed in the same persistent process, so definitions carry across cells. The CUDA notebooks additionally link against the NVIDIA runtime so `__global__` kernels compile and launch on the host GPU.

## Related projects

- [xeus-cpp](https://github.com/compiler-research/xeus-cpp) - the Jupyter kernel these notebooks run on
- [CppInterOp](https://github.com/compiler-research/CppInterOp) - the C++ interoperability library xeus-cpp is built on
- [compiler-research.org](https://compiler-research.org) - the research group behind this work

## License

This software is licensed under the `Apache-2.0 License`. See the [LICENSE](LICENSE) file for details.
