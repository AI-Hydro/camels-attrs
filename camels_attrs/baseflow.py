"""
Lyne-Hollick baseflow filter, Ladson et al. (2013) recipe as used by CAMELS-US.

Faithful port of ``aihydro_watershed.signatures.baseflow.lyne_hollick_ladson2013``
(aihydro-watershed 0.2.0), which in turn follows TonyLadson/BaseflowSeparation_LyneHollick
``BFI.R`` and naddor/camels ``comp_i_bf_landson``. camels-attrs is the standalone reference
implementation and must not import the aihydro packages, so the kernel is ported, not imported;
``tests/test_signature_definitions.py`` pins it to CAMELS attributes v2.0 and to the watershed kernel's
documented outputs (docs/vision-2040/evidence/signature-definitions-1 in the AI-Hydro workspace).

Recipe: alpha 0.925; three alternating sweeps (forward, backward, forward); the series is
reflected 30 days at both ends; in each sweep the quick flow
``f(t) = alpha f(t-1) + (1+alpha)/2 (y(t) - y(t-1))`` is subtracted only where ``f > 0`` and the
(unclamped) result feeds the next sweep; the final baseflow is clipped at zero.
"""
import warnings

import numpy as np

LH_ALPHA = 0.925
LH_PASSES = 3
LH_N_REFLECT = 30
#: Below this many days the filter's start-up transient is a large part of the record.
WARMUP_BIAS_DAYS = 365

LYNE_HOLLICK_LADSON2013_REFERENCE = (
    "Lyne & Hollick (1979); Nathan & McMahon (1990); Ladson et al. (2013) as implemented in "
    "TonyLadson/BaseflowSeparation_LyneHollick BFI.R and used by naddor/camels comp_i_bf_landson "
    "(alpha 0.925, 3 passes forward-backward-forward, 30-day reflection, quick flow subtracted only "
    "where positive, baseflow clipped at zero)"
)


class WarmupBiasWarning(UserWarning):
    """A Lyne-Hollick baseflow computed on a short series (31-364 days) is biased low by the
    filter's start-up transient (the initial quick flow equals the first flow)."""


def _ladson_segment(q, alpha, passes, n_reflect):
    """Baseflow of one gap-free segment, exactly as BFI.R ``BFI.calc``."""
    nr = n_reflect
    c = 0.5 * (1.0 + alpha)
    # Reflect nr days at each end (excluding the end point itself).
    x = np.concatenate([q[nr:0:-1], q, q[-2:-nr - 2:-1]])
    n = x.size

    def fwd_f(y, f0):
        f = np.empty(n)
        f[0] = f0
        for i in range(1, n):
            f[i] = alpha * f[i - 1] + c * (y[i] - y[i - 1])
        return f

    def bwd_f(y):
        f = np.empty(n)
        f[-1] = y[-1]
        for i in range(n - 2, -1, -1):
            f[i] = alpha * f[i + 1] + c * (y[i] - y[i + 1])
        return f

    # First pass: initial quick flow equals the flow itself (BFI.R: Qf1[1] <- Q[1]).
    f = fwd_f(x, x[0])
    b = np.where(f > 0, x - f, x)
    # Further passes alternate backward, forward, ...; the state is NEVER clamped, the
    # quick flow is subtracted only where positive.
    for k in range(1, passes):
        f = bwd_f(b) if k % 2 == 1 else fwd_f(b, b[0])
        b = np.where(f > 0, b - f, b)
    b = b[nr:b.size - nr]
    b[b < 0] = 0.0
    return b


def lyne_hollick_ladson2013(streamflow, alpha=LH_ALPHA, passes=LH_PASSES, n_reflect=LH_N_REFLECT):
    """Canonical Lyne-Hollick baseflow filter (Ladson et al. 2013; CAMELS ``comp_i_bf_landson``).

    Reproduces the CAMELS attributes v2.0 baseflow index to <= 2e-6 relative on 01013500 and 01031500.

    A series of 31-364 days is computed but emits ``WarmupBiasWarning``; a series of 30 days or
    fewer raises ``ValueError``, as BFI.R does.

    NaN handling follows BFI.R: the filter runs on each run of more than ``n_reflect``
    consecutive finite values; days outside such runs return NaN.

    Returns a baseflow array the same length as ``streamflow``.
    """
    q = np.asarray(streamflow, dtype=float).ravel()
    if not 0.0 <= alpha < 1.0:
        raise ValueError("alpha must be in [0, 1), got %r" % (alpha,))
    if int(passes) < 1:
        raise ValueError("passes must be >= 1, got %r" % (passes,))
    if q.size <= n_reflect:
        raise ValueError(
            "lyne_hollick_ladson2013 needs more than n_reflect=%d days, got %d" % (n_reflect, q.size))
    if q.size < WARMUP_BIAS_DAYS:
        warnings.warn(
            "lyne_hollick_ladson2013 on %d days (< %d): the result carries a warm-up bias "
            "(BFI is biased low at short n)" % (q.size, WARMUP_BIAS_DAYS),
            WarmupBiasWarning, stacklevel=2)
    out = np.full(q.size, np.nan)
    finite = np.isfinite(q)
    if finite.all():
        return _ladson_segment(q, alpha, int(passes), n_reflect)
    # Runs of consecutive finite values longer than n_reflect.
    edges = np.flatnonzero(np.diff(np.concatenate([[0], finite.view(np.int8), [0]])))
    for lo, hi in zip(edges[::2], edges[1::2]):
        if hi - lo > n_reflect:
            out[lo:hi] = _ladson_segment(q[lo:hi], alpha, int(passes), n_reflect)
    return out
