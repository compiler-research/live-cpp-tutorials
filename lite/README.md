# SC26 at home, in the browser

Six notebooks from the SC26 Python tutorial and the C++ series of live-cpp-tutorials, running here without any install. The kernel is C++ (clang-repl compiled
to WebAssembly); Python runs inside it and calls the C++ through cppjit, which is the pairing the tutorial is about.

1. `1_call_it.ipynb`: call a C++ header from Python, time it against pure Python.
2. `2_transform_it.ipynb`: the derivative Clad wrote for that header, checked three ways.
3. `3_fit_it.ipynb`: a bouncing ball in C++, fitted to data with BFGS on Clad's exact gradient.
4. `4_higgs_open_data.ipynb`: the four-lepton Higgs mass on CMS 2012 open data, without ROOT, checked against RooFit.
5. `5_tiny_twin.ipynb`: the cancer model's shape in sixty lines of C++, called, composed with Python, calibrated.
6. `6_cartopiax.ipynb`: the cancer model itself (CARTopiaX on BioDynaMo, compiled to WebAssembly), downloaded by
   this notebook only, run for a few simulated minutes and looked inside with numpy and matplotlib.

Run the cells top to bottom (the first two cells of each notebook set the browser up). The first start downloads the
compiler and the Python packages once; after that everything runs locally in your browser tab. The same notebooks
1 to 5 for a laptop (`pip install cppjit numpy scipy matplotlib`) are in `cppjit/` of this repository, and the C++ series under
`cpp/` here is the repository's `xeus-cpp/` series, unchanged.
