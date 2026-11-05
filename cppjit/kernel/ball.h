// ball.h -- a ball dropped from 2 m with air drag; the apex height of bounce n, and a least-squares loss.
// The same simulator as the SC26 talk's "Simulate and fit it" slide. 20,000 time steps, a floor with a clamp
// and a branch: nothing a tracing autodiff framework can enter, everything a compiler can differentiate.
#pragma once
#include <cmath>
inline double apex(double e, double k, int n) {
  double y = 2.0, v = 0.0, dt = 1e-3, top = 0.0; int bounces = 0;
  for (int i = 0; i < 20000; ++i) {
    v -= (9.81 + k * v * std::fabs(v)) * dt;          // gravity and air drag
    y += v * dt;
    if (y < 0.0) { y = 0.0; v = -e * v; ++bounces; }  // the floor: a clamp and a branch
    if (bounces == n && v > 0.0 && y > top) top = y;  // the apex of bounce n
    if (bounces > n) break;
  }
  return top;
}
// p = {e, k}; obs = the apex heights of bounces 1..3
inline double loss(double* p, const double* obs) {
  double L = 0; for (int n = 1; n <= 3; ++n) { double d = apex(p[0], p[1], n) - obs[n-1]; L += d * d; } return L; }
