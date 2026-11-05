# cppjit: one Python session with a C++ compiler inside it

Five notebooks from the SC26 tutorial *The Compiler Is in the Room*. The kernel is Python; `cppjit` carries Clang
and LLVM, reads a C++ header the way a compiler does, and lets Python call what it finds, with no bindings written by
anyone. Two small C++ models (a logistic step, a bouncing ball), one real dataset (the Higgs from CMS open data) and a
sixty-line "tiny twin" of a tumour model carry the three verbs of the talk: call it, compose it, transform it.

| notebook | what it does |
|---|---|
| `1_call_it.ipynb` | a C++ header called from Python, timed against pure Python |
| `2_transform_it.ipynb` | the derivative Clad wrote for that header, checked three ways, and why a tracer cannot do it |
| `3_fit_it.ipynb` | a bouncing-ball simulator in C++ fitted to data with BFGS on Clad's exact gradient |
| `4_higgs_open_data.ipynb` | the four-lepton Higgs mass fitted on CMS 2012 open data without ROOT, checked against RooFit |
| `5_tiny_twin.ipynb` | the cancer model's shape in sixty lines of C++: called, composed with Python, calibrated |

## In the browser, nothing installed

The same five notebooks run on this repository's GitHub Pages site, on the xeus-cpp kernel compiled to WebAssembly
hosting Python through cppjit: `https://compiler-research.org/live-cpp-tutorials/lab/index.html?path=cppjit/1_call_it.ipynb`
and so on (the C++ series of this repository is there too, under `cpp/`). The first load downloads the compiler once
(about 45 MB); after that everything runs in the tab. How the site is built: `lite/README-build.md`.

## On a laptop

```sh
pip install cppjit-*.whl numpy scipy matplotlib jupyter   # the wheel of this repository's release: cppjit with Clad inside, Python 3.12, Linux x86_64
# (the PyPI cppjit runs the notebooks' C++ too, but has no Clad plugin yet, so the derivative cells need the wheel)
jupyter lab
```

Open the notebooks in this directory with the Python kernel. No Clad, no ROOT, no BioDynaMo needed.

## What is shipped and why

- `kernel/logistic_step.h`, `kernel/ball.h`, `kernel/twin.h`: the C++ the notebooks call, as written.
- `kernel/derivatives.py`: where the notebooks get Clad's derivatives. The kernel's compiler carries Clad (the browser
  kernel, and the cppjit wheel of this repository's release, whose CppInterOp is built with the plugin), so the
  derivatives are generated in the session from three requests and land in `clad_generated` under the names the
  notebooks use; `derivatives.code()` returns the source Clad wrote. The PyPI cppjit has no Clad yet: install the wheel
  from the release (`pip install cppjit-*.whl`, Python 3.12) or open the notebooks in the browser.
- `kernel/lazy.py`, `kernel/lazy.json`: used only in the browser, where SciPy and matplotlib load on first import.
- `data/higgs4l.npz` (214 KB): four-lepton invariant masses from CMS 2012 open data (CC0) after ROOT's df103 selection,
  with the simulated signal and ZZ background in 70-182 GeV; `data/higgs4l_roofit_reference.json`: the RooFit result
  the talk quotes, so you can check your fit against it.

The notebooks are developed in the SC26 tutorial repository; this is the hand-out copy.
