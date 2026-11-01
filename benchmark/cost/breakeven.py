from __future__ import annotations

import math
from typing import Callable

import numpy as np
from scipy.optimize import brentq


def find_intersections(left: Callable[[float], float], right: Callable[[float], float], lower=0.0, upper=1e9, *, grid_size=301, breakpoints=(), tolerance=1e-7) -> dict:
    """Bracket continuous roots; report equality intervals and discontinuities separately.

    This is a finite search. Arbitrarily narrow intersections can be missed; supply
    known piecewise model breakpoints and inspect the search_resolution metadata.
    """
    if lower < 0 or upper <= lower or grid_size < 3:
        raise ValueError("Invalid search domain")
    grid = np.unique(np.r_[lower, np.geomspace(max(lower, 1e-6), upper, grid_size), [p for p in breakpoints if lower <= p <= upper]])
    cache = {}

    def difference(x):
        if x not in cache:
            cache[x] = float(left(x) - right(x))
        return cache[x]
    values = np.array([difference(float(x)) for x in grid])
    roots, intervals, jumps = [], [], []
    near = np.isclose(values, 0, atol=tolerance, rtol=0)
    index = 0
    while index < len(grid):
        if near[index]:
            end = index
            while end + 1 < len(grid) and near[end + 1]:
                midpoint = (grid[end] + grid[end + 1]) / 2
                if abs(difference(float(midpoint))) > tolerance:
                    break
                end += 1
            if end > index:
                intervals.append([float(grid[index]), float(grid[end])])
            else:
                roots.append(float(grid[index]))
            index = end + 1
        else:
            index += 1
    for a, b, fa, fb in zip(grid[:-1], grid[1:], values[:-1], values[1:]):
        if not (math.isfinite(fa) and math.isfinite(fb)) or fa * fb >= 0:
            continue
        candidate = float(brentq(difference, float(a), float(b), xtol=1e-8))
        residual = abs(difference(candidate))
        if residual <= tolerance:
            if not any(abs(candidate - x) < max(1e-4, abs(x) * 1e-7) for x in roots):
                roots.append(candidate)
        else:
            jumps.append({"bracket": [float(a), float(b)], "candidate": candidate, "residual_usd": residual})
    return {"status": "COINCIDENT_INTERVAL" if intervals else "ROOTS_FOUND" if roots else "NO_INTERSECTION_IN_DOMAIN", "roots": sorted(roots), "coincident_intervals": intervals, "discontinuities": jumps, "domain": [lower, upper], "search_resolution": {"grid_size": len(grid), "known_breakpoints": len(breakpoints), "method": "log grid + supplied knots + Brent + residual validation", "limitation": "finite search cannot guarantee every narrow/tangent intersection"}}
