// logistic_step.h -- one explicit-Euler step of logistic growth, dN/dt = r*N*(1 - N/K):
//
//     N_{t+1} = N_t + r * N_t * (1 - N_t / K)
//
// The one header the whole tutorial runs on: called from Python through cppjit, differentiated by Clad, and the
// proliferation law inside the tumour twin. Templated on the scalar type so one source serves float and double and
// so Clad differentiates the generic body, not a type-erased wrapper.
#ifndef SC26_KERNEL_LOGISTIC_STEP_H
#define SC26_KERNEL_LOGISTIC_STEP_H

template <typename T>
T logistic_step(T N, T r, T K) {
    T growth = r * N * (T(1) - N / K);
    return N + growth;
}

#endif // SC26_KERNEL_LOGISTIC_STEP_H
