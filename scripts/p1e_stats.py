"""P1E.0 — Pure statistical helpers (NOT ranking/metric logic).

These implement the preregistered statistical methods from the protocol:
paired percentile bootstrap, paired permutation test, continuous-metric MDE
via the z-approximation, and top1_optimal MDE via deterministic McNemar
discordant-pair simulation. None of this is ranking or metric computation —
it operates on already-computed per-case metric vectors.

All seeds are frozen: primary 20260721, sensitivity 42.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence

# Frozen constants (protocol §8).
ALPHA = 0.05
POWER = 0.80
PRIMARY_SEED = 20260721
SENSITIVITY_SEED = 42
N_BOOTSTRAP = 10000
N_PERM_MC = 100000
N_MCNEMAR_SIM = 100000
Z_ALPHA_HALF = 1.959964  # z_{1 - 0.05/2}
Z_POWER = 0.841622       # z_{0.80}


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def paired_bootstrap_ci(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = PRIMARY_SEED,
    alpha: float = ALPHA,
) -> dict:
    """Paired percentile bootstrap CI on (b - a) per-case metric delta.

    Resampling unit = case. Returns mean_delta, percentile lower/upper (95%),
    p_positive (fraction of bootstrap means > 0), and excludes_zero flag.
    """
    assert len(a) == len(b)
    n = len(a)
    if n == 0:
        return {"mean_delta": 0.0, "lower": 0.0, "upper": 0.0, "p_positive": 0.0,
                "excludes_zero": False, "n": 0, "method": "percentile", "seed": seed}
    deltas = [b[i] - a[i] for i in range(n)]
    obs = sum(deltas) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(n_bootstrap):
        s = 0.0
        for _ in range(n):
            s += deltas[rng.randrange(n)]
        boots.append(s / n)
    boots.sort()
    lo = boots[int((alpha / 2) * n_bootstrap)]
    hi = boots[int((1 - alpha / 2) * n_bootstrap)]
    p_pos = sum(1 for d in boots if d > 0) / n_bootstrap
    return {
        "mean_delta": round(obs, 8),
        "lower": round(lo, 8),
        "upper": round(hi, 8),
        "p_positive": round(p_pos, 4),
        "excludes_zero": lo > 0 or hi < 0,
        "n": n,
        "method": "percentile",
        "seed": seed,
    }


def paired_permutation_pvalue(
    a: Sequence[float],
    b: Sequence[float],
    *,
    seed: int = PRIMARY_SEED,
    n_mc: int = N_PERM_MC,
) -> dict:
    """Two-sided paired permutation test on mean(b - a).

    Exact enumeration when n <= 20 (2^n feasible); Monte-Carlo otherwise
    (frozen seed, n_mc draws). Returns p_value two-sided.
    """
    assert len(a) == len(b)
    n = len(a)
    if n == 0:
        return {"p_value": 1.0, "method": "none", "n": 0, "seed": seed}
    deltas = [b[i] - a[i] for i in range(n)]
    obs = abs(sum(deltas) / n)

    def _two_sided_p_from_stats(count_geq: int, total: int) -> float:
        # two-sided: proportion of |sampled mean| >= |observed mean|
        return count_geq / total if total else 1.0

    if n <= 20:
        # exact enumeration over all 2^n sign flips
        total = 1 << n
        count = 0
        for mask in range(total):
            s = 0.0
            for i in range(n):
                s += deltas[i] if (mask >> i) & 1 else -deltas[i]
            if abs(s / n) >= obs - 1e-15:
                count += 1
        return {"p_value": count / total, "method": "exact_enumeration",
                "n": n, "seed": seed, "n_enumerated": total}
    # Monte-Carlo
    rng = random.Random(seed)
    count = 0
    for _ in range(n_mc):
        s = 0.0
        for i in range(n):
            s += deltas[i] if rng.random() < 0.5 else -deltas[i]
        if abs(s / n) >= obs - 1e-15:
            count += 1
    return {"p_value": count / n_mc, "method": "monte_carlo",
            "n": n, "seed": seed, "n_mc": n_mc}


def continuous_mde(diffs: Sequence[float]) -> dict:
    """MDE for a continuous paired metric via the preregistered z-approximation.

    MDE = (z_{1-a/2} + z_{power}) * sd(diff) / sqrt(n).
    MDE is reported as 0 ONLY when every paired difference is identical
    (zero variance); zero-variance is flagged separately.
    """
    n = len(diffs)
    if n == 0:
        return {"mde": 0.0, "n": 0, "sd": 0.0, "zero_variance": True,
                "method": "z_approx", "alpha": ALPHA, "power": POWER}
    sd = stdev(diffs)
    zero_var = sd == 0.0
    mde = 0.0 if zero_var else (Z_ALPHA_HALF + Z_POWER) * sd / math.sqrt(n)
    return {"mde": round(mde, 8), "n": n, "sd": round(sd, 8),
            "zero_variance": zero_var, "method": "z_approx",
            "alpha": ALPHA, "power": POWER,
            "formula": "(1.959964 + 0.841622) * sd(diff) / sqrt(n)"}


def top1_mcnemar_mde(
    a_binary: Sequence[int],
    b_binary: Sequence[int],
    *,
    seed: int = PRIMARY_SEED,
    n_sim: int = N_MCNEMAR_SIM,
) -> dict:
    """top1_optimal MDE via deterministic McNemar discordant-pair simulation.

    a_binary/b_binary are per-case 0/1 optimal outcomes for the two policies.
    Discordant pairs: (a=1,b=0) count = b01, (a=0,b=1) count = b10. Under the
    null, each discordant pair flips to b with probability 0.5. We simulate
    the smallest detectable shift in discordance proportion at 80% power.

    Zero discordance -> MDE unavailable; classify tied_heavy.
    """
    assert len(a_binary) == len(b_binary)
    pairs = list(zip(a_binary, b_binary))
    b01 = sum(1 for x, y in pairs if x == 1 and y == 0)
    b10 = sum(1 for x, y in pairs if x == 0 and y == 1)
    n_disc = b01 + b10
    n = len(pairs)
    if n_disc == 0:
        return {"mde": None, "n": n, "discordant_pairs": 0, "b01": b01, "b10": b10,
                "method": "mcnemar_discordant_sim", "seed": seed,
                "zero_discordance": True, "note": "MDE unavailable; classify tied_heavy"}
    # MDE = smallest true discordance asymmetry detectable at 80% power.
    # We scan candidate true proportions p of (b10|discordant) and simulate
    # the exact McNemar test's power; MDE in macro top1_optimal units =
    # detectable asymmetry / n.
    rng = random.Random(seed)
    candidates = [round(0.5 + k * 0.01, 3) for k in range(1, 51)]  # 0.51 .. 1.00
    mde_prop = None
    for p in candidates:
        # power = P(exact McNemar two-sided rejects | true p)
        rejects = 0
        for _ in range(n_sim):
            b10_sim = sum(1 for _ in range(n_disc) if rng.random() < p)
            b01_sim = n_disc - b10_sim
            # exact two-sided McNemar p-value via binomial tail
            pp = _binom_two_sided_p(b10_sim, n_disc, 0.5)
            if pp < ALPHA:
                rejects += 1
        power = rejects / n_sim
        if power >= POWER:
            mde_prop = p
            break
    mde_macro = ((mde_prop - 0.5) * n_disc / n) if mde_prop is not None else None
    return {"mde": round(mde_macro, 8) if mde_macro is not None else None,
            "n": n, "discordant_pairs": n_disc, "b01": b01, "b10": b10,
            "detectable_discordance_proportion": mde_prop,
            "method": "mcnemar_discordant_sim", "seed": seed,
            "n_sim": n_sim, "zero_discordance": False}


def _binom_two_sided_p(successes: int, trials: int, p0: float) -> float:
    """Exact two-sided binomial p-value (used by McNemar)."""
    if trials == 0:
        return 1.0
    # two-sided: 2 * min(P(X>=k), P(X<=k)), capped at 1
    k = successes
    upper = sum(_binom_pmf(i, trials, p0) for i in range(k, trials + 1))
    lower = sum(_binom_pmf(i, trials, p0) for i in range(0, k + 1))
    return min(1.0, 2.0 * min(upper, lower))


def _binom_pmf(i: int, n: int, p: float) -> float:
    return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))


def kendall_tau(rank_a: Sequence[str], rank_b: Sequence[str]) -> dict:
    """Kendall's tau-b over an identical candidate universe.

    rank_a/rank_b are ordered lists of candidate IDs (rank 1 first). The
    universe must be identical; a mismatch raises (integrity failure, not
    implicit tail assignment). Returns tau_b accounting for ties.
    """
    if set(rank_a) != set(rank_b):
        raise ValueError(
            f"candidate universe mismatch: {set(rank_a) ^ set(rank_b)} (integrity failure)"
        )
    # Map candidate -> rank position in each
    pos_a = {cid: i for i, cid in enumerate(rank_a)}
    pos_b = {cid: i for i, cid in enumerate(rank_b)}
    ids = list(rank_a)
    n = len(ids)
    if n < 2:
        return {"tau": 0.0, "n": n, "concordant": 0, "discordant": 0, "ties": 0}
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = pos_a[ids[i]] - pos_a[ids[j]]
            db = pos_b[ids[i]] - pos_b[ids[j]]
            sign = da * db
            if sign > 0:
                concordant += 1
            elif sign < 0:
                discordant += 1
    # tau-a (no ties expected since positions are unique); report tau
    total = concordant + discordant
    tau = (concordant - discordant) / total if total else 0.0
    return {"tau": round(tau, 6), "n": n, "concordant": concordant,
            "discordant": discordant, "ties": 0}


def spearman_rho(rank_a: Sequence[str], rank_b: Sequence[str]) -> dict:
    """Spearman's rho over an identical candidate universe (ranks are unique)."""
    if set(rank_a) != set(rank_b):
        raise ValueError("candidate universe mismatch (integrity failure)")
    pos_a = {cid: i + 1 for i, cid in enumerate(rank_a)}
    pos_b = {cid: i + 1 for i, cid in enumerate(rank_b)}
    ids = list(rank_a)
    n = len(ids)
    if n < 2:
        return {"rho": 0.0, "n": n}
    xs = [pos_a[c] for c in ids]
    ys = [pos_b[c] for c in ids]
    mx, my = mean(xs), mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    rho = num / (den_x * den_y) if den_x and den_y else 0.0
    return {"rho": round(rho, 6), "n": n}
