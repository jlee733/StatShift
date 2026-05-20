"""Distribution fitting for fantasy points analysis."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from scipy import stats


CANDIDATE_DISTRIBUTIONS: list[tuple[str, Any]] = [
    ("Normal", stats.norm),
    ("Gamma", stats.gamma),
    ("Log-Normal", stats.lognorm),
    ("Weibull", stats.weibull_min),
]


def fit_best_distribution(
    data: list[float],
) -> tuple[str, dict[str, float], Callable[[np.ndarray], np.ndarray]]:
    """Fit candidate distributions and return best fit by AIC.
    
    Args:
        data: List of fantasy point values (non-zero values recommended)
    
    Returns:
        Tuple of (distribution_name, parameters_dict, pdf_function)
    """
    arr = np.array([x for x in data if x > 0])
    
    if len(arr) < 5:
        mean = float(np.mean(arr)) if len(arr) > 0 else 0.0
        std = float(np.std(arr)) if len(arr) > 1 else 1.0
        return (
            "Normal",
            {"mean": mean, "std": std},
            lambda x, m=mean, s=max(std, 0.1): stats.norm.pdf(x, loc=m, scale=s),
        )
    
    best_name = "Normal"
    best_params: dict[str, float] = {}
    best_pdf: Callable[[np.ndarray], np.ndarray] = lambda x: stats.norm.pdf(x)
    best_aic = float("inf")
    
    for name, dist in CANDIDATE_DISTRIBUTIONS:
        try:
            if name == "Normal":
                params = dist.fit(arr)
                loc, scale = params
                pdf_fn = lambda x, d=dist, p=params: d.pdf(x, *p)
                param_dict = {"mean": loc, "std": scale}
                
            elif name == "Gamma":
                params = dist.fit(arr, floc=0)
                a, loc, scale = params
                pdf_fn = lambda x, d=dist, p=params: d.pdf(x, *p)
                param_dict = {"shape": a, "scale": scale}
                
            elif name == "Log-Normal":
                params = dist.fit(arr, floc=0)
                s, loc, scale = params
                pdf_fn = lambda x, d=dist, p=params: d.pdf(x, *p)
                param_dict = {"s": s, "scale": scale}
                
            elif name == "Weibull":
                params = dist.fit(arr, floc=0)
                c, loc, scale = params
                pdf_fn = lambda x, d=dist, p=params: d.pdf(x, *p)
                param_dict = {"c": c, "scale": scale}
            else:
                continue
            
            log_likelihood = np.sum(np.log(dist.pdf(arr, *params) + 1e-10))
            k = len(params)
            aic = 2 * k - 2 * log_likelihood
            
            if aic < best_aic:
                best_aic = aic
                best_name = name
                best_params = param_dict
                best_pdf = pdf_fn
                
        except Exception:
            continue
    
    return best_name, best_params, best_pdf


def format_params_string(params: dict[str, float]) -> str:
    """Format parameters dictionary as a readable string."""
    return ", ".join(f"{k}={v:.2f}" for k, v in params.items())
