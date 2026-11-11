"""Estatistica: McNemar exato, Q de Cochran, correcao de Holm e bootstrap por cluster
(reamostrando arquivos). Funcoes puras, testaveis com fixtures pequenas."""
from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats as sps


def mcnemar_exact(a, b) -> dict:
    """McNemar exato bilateral para duas listas booleanas pareadas (True = 'acusou'/'detectou')."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    only_a, only_b = int((a & ~b).sum()), int((~a & b).sum())
    n = only_a + only_b
    p = 1.0 if n == 0 else float(sps.binomtest(min(only_a, only_b), n, 0.5).pvalue)
    return {"only_a": only_a, "only_b": only_b, "discordant": n, "p": p}


def cochran_q(matrix) -> dict:
    """Q de Cochran para k >= 3 configuracoes sobre os mesmos itens. matrix: [itens x k] booleana."""
    x = np.asarray(matrix, float)
    n, k = x.shape
    rows, cols = x.sum(axis=1), x.sum(axis=0)
    t = x.sum()
    den = k * t - (rows ** 2).sum()
    if den == 0:
        return {"Q": 0.0, "df": k - 1, "p": 1.0}
    q = (k - 1) * (k * (cols ** 2).sum() - t ** 2) / den
    return {"Q": float(q), "df": k - 1, "p": float(sps.chi2.sf(q, k - 1))}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """p-valores ajustados por Holm-Bonferroni (monotonicos, limitados a 1)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def pairwise_mcnemar_holm(columns: dict[str, list[bool]]) -> list[dict]:
    """Q de Cochran e depois McNemar par a par com Holm. columns: {config: [bool por item]}."""
    names = list(columns)
    res = []
    raw = {}
    for a, b in itertools.combinations(names, 2):
        r = mcnemar_exact(columns[a], columns[b])
        raw[f"{a} x {b}"] = r["p"]
        res.append({"pair": f"{a} x {b}", **r})
    adj = holm(raw)
    for r in res:
        r["p_holm"] = adj[r["pair"]]
    return res


def cluster_bootstrap(counts: np.ndarray, stat_fn, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """IC por bootstrap percentil reamostrando ARQUIVOS (clusters).

    counts: [n_arquivos x m] contagens por arquivo (ex.: acusados reais, total real, acusados falsos, total falso...).
    stat_fn: funcao da soma das contagens (vetor de tamanho m) -> estatistica escalar.
    """
    counts = np.asarray(counts, float)
    n = counts.shape[0]
    point = float(stat_fn(counts.sum(axis=0)))
    rng = np.random.default_rng(seed)
    w = rng.multinomial(n, [1.0 / n] * n, size=n_boot)       # pesos por arquivo em cada replica
    sums = w @ counts
    vals = np.array([stat_fn(s) for s in sums], float)
    vals = vals[~np.isnan(vals)]
    lo, hi = (np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)]) if len(vals) else (float("nan"), float("nan")))
    return {"point": point, "lo": float(lo), "hi": float(hi), "n_boot": int(len(vals))}


def paired_bootstrap_diff(counts_a: np.ndarray, counts_b: np.ndarray, stat_fn, n_boot: int = 2000, seed: int = 0,
                          alpha: float = 0.05) -> dict:
    """Diferenca (a - b) de uma estatistica, com os MESMOS arquivos reamostrados nas duas configuracoes (pareado)."""
    a, b = np.asarray(counts_a, float), np.asarray(counts_b, float)
    assert a.shape[0] == b.shape[0], "as duas configuracoes precisam cobrir os mesmos arquivos"
    n = a.shape[0]
    point = float(stat_fn(a.sum(axis=0)) - stat_fn(b.sum(axis=0)))
    rng = np.random.default_rng(seed)
    w = rng.multinomial(n, [1.0 / n] * n, size=n_boot)
    sa, sb = w @ a, w @ b
    vals = np.array([stat_fn(x) - stat_fn(y) for x, y in zip(sa, sb)], float)
    vals = vals[~np.isnan(vals)]
    lo, hi = (np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)]) if len(vals) else (float("nan"), float("nan")))
    return {"diff": point, "lo": float(lo), "hi": float(hi), "n_boot": int(len(vals)),
            "p_two_sided": float(min(1.0, 2 * min((vals <= 0).mean(), (vals >= 0).mean()))) if len(vals) else float("nan")}


def mean_sd(values) -> dict:
    v = np.asarray(values, float)
    return {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else float("nan"), "n": int(len(v))}


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo, hi = sps.binomtest(k, n).proportion_ci(confidence_level=1 - alpha, method="exact")
    return float(lo), float(hi)


def cohen_kappa(y_true, y_pred) -> float:
    """Kappa de Cohen para duas listas booleanas."""
    y_true, y_pred = np.asarray(y_true, bool), np.asarray(y_pred, bool)
    n = len(y_true)
    if n == 0:
        return float("nan")
    po = float((y_true == y_pred).mean())
    pe = float(y_true.mean() * y_pred.mean() + (1 - y_true.mean()) * (1 - y_pred.mean()))
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)
