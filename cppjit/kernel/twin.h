// twin.h -- a tiny tumour twin: the cancer model's shape in sixty lines, for a laptop.
//
// N sites on a line. Each site holds a cell count c[i] that grows by the SC26 header's logistic step at a rate
// set by the oxygen there and spreads to its neighbours, so the colony's front advances. Oxygen diffuses along the line from both edges, which are held at o_edge (the medium),
// and is consumed by the cells. Two knobs the real model also has: the consumption rate `cons` and the edge
// oxygen `o_edge`. The smooth part (oxygen) is restated below as one function the compiler can differentiate,
// exactly as the talk restates the real model's oxygen update.
#pragma once
#include <cmath>
#include <functional>
#include <vector>
#include "logistic_step.h"

constexpr int kMaxSites = 256;

struct Twin {
  int n;                      // sites
  std::vector<double> c, o;   // cells and oxygen per site
  double r = 0.15, K = 2000.0;        // growth: rate at full oxygen, carrying capacity per site
  double spread = 0.03;               // cells: fraction exchanged with each neighbour per step (the colony's front advances)
  double D = 4.5, cons = 1e-5;        // oxygen: diffusion per substep, consumption per cell per substep
  double o_edge = 38.0;               // oxygen at the two edges (the medium)
  int substeps = 2000; double dto = 0.1;  // oxygen substeps per step: the field settles within one growth step
  long steps_done = 0;
  explicit Twin(int sites, double edge = 38.0) : n(sites), c(sites, 0.0), o(sites, edge), o_edge(edge) {
    for (int i = n / 2 - 2; i <= n / 2 + 2; ++i) c[i] = 10.0;   // a small colony in the middle
  }
  void oxygen_substep() {
    double prev = o[0];
    for (int i = 1; i < n - 1; ++i) {
      double cur = o[i];
      o[i] += dto * (D * (prev - 2 * cur + o[i + 1]) - cons * c[i] * cur);
      if (o[i] < 0) o[i] = 0;
      prev = cur;
    }
    o[0] = o_edge; o[n - 1] = o_edge;
  }
  void step() {
    for (int s = 0; s < substeps; ++s) oxygen_substep();
    for (int i = 0; i < n; ++i) {
      double rate = r * o[i] / (o[i] + 5.0);                   // Michaelis-Menten in the oxygen
      c[i] = logistic_step<double>(c[i], rate, K);              // the header, as written, as the growth law
    }
    double prev = c[0];
    for (int i = 1; i < n - 1; ++i) {                           // the cells spread to their neighbours
      double cur = c[i]; c[i] += spread * (prev - 2 * cur + c[i + 1]); prev = cur;
    }
    ++steps_done;
  }
  double total_cells() const { double s = 0; for (double x : c) s += x; return s; }
  double mean_oxygen_at_cells() const {
    double s = 0, w = 0; for (int i = 0; i < n; ++i) { s += c[i] * o[i]; w += c[i]; } return w > 0 ? s / w : 0; }
};

// Run `steps` steps; `hook(step, twin)` is called before each one. A Python function can be the hook.
inline void run(Twin& t, int steps, std::function<void(int, Twin&)> hook) {
  for (int s = 0; s < steps; ++s) { hook(s, t); t.step(); }
}

// The smooth part, restated for the compiler: from a uniform field at o_edge, `iters` oxygen substeps over FIXED cells,
// then the cell-weighted mean oxygen. The derivative of this with respect to (cons, o_edge) is what calibrates the twin.
inline double oxygen_after(const double* cells, int n, double cons, double o_edge, double D, double dto, int iters) {
  double o[kMaxSites];
  for (int i = 0; i < n; ++i) o[i] = o_edge;
  for (int it = 0; it < iters; ++it) {
    double prev = o[0];
    for (int i = 1; i < n - 1; ++i) {
      double cur = o[i];
      o[i] += dto * (D * (prev - 2 * cur + o[i + 1]) - cons * cells[i] * cur);
      prev = cur;
    }
    o[0] = o_edge; o[n - 1] = o_edge;
  }
  double s = 0, w = 0;
  for (int i = 0; i < n; ++i) { s += cells[i] * o[i]; w += cells[i]; }
  return s / w;
}
