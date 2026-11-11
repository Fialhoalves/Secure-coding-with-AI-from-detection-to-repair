"""Estatistica: McNemar exato, Q de Cochran, Holm, bootstrap por cluster (conferidos contra statsmodels/scipy)."""
import numpy as np
import pytest
from statsmodels.stats.contingency_tables import cochrans_q
from statsmodels.stats.multitest import multipletests

import stats as st


def test_mcnemar_exact_matches_the_papers_audit_value():
    # GPT-4o (2024) x GPT-4.1 (2025) nos 28 issues comuns: 2 so do primeiro, 9 so do segundo -> p = 0,065 (auditoria)
    a = [True] * 2 + [False] * 9 + [True] * 14 + [False] * 3
    b = [False] * 2 + [True] * 9 + [True] * 14 + [False] * 3
    r = st.mcnemar_exact(a, b)
    assert (r["only_a"], r["only_b"], r["discordant"]) == (2, 9, 11) and r["p"] == pytest.approx(0.0654, abs=1e-4)


def test_mcnemar_no_discordant_pairs():
    assert st.mcnemar_exact([True, False, True], [True, False, True])["p"] == 1.0
    assert st.mcnemar_exact([True] * 8, [False] * 8)["p"] == pytest.approx(2 * 0.5 ** 8)


def test_cochran_q_against_statsmodels():
    rng = np.random.default_rng(1)
    x = (rng.random((40, 4)) < [0.8, 0.6, 0.5, 0.7]).astype(int)
    mine, ref = st.cochran_q(x), cochrans_q(x)
    assert mine["Q"] == pytest.approx(ref.statistic) and mine["p"] == pytest.approx(ref.pvalue) and mine["df"] == 3
    assert st.cochran_q(np.ones((5, 3)))["p"] == 1.0                 # sem variacao: nao ha o que testar


def test_holm_matches_statsmodels_and_is_monotone():
    p = {"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5}
    mine = st.holm(p)
    ref = multipletests(list(p.values()), method="holm")[1]
    assert [mine[k] for k in p] == pytest.approx(list(ref))
    assert mine["a"] == pytest.approx(0.04) and mine["c"] == pytest.approx(0.09) and mine["b"] == pytest.approx(0.09)
    assert st.holm({"x": 0.9})["x"] == 0.9 and all(v <= 1 for v in st.holm({"a": 0.6, "b": 0.7}).values())


def test_pairwise_mcnemar_holm():
    cols = {"A": [True] * 20, "B": [True] * 10 + [False] * 10, "C": [True] * 20}
    res = {r["pair"]: r for r in st.pairwise_mcnemar_holm(cols)}
    assert set(res) == {"A x B", "A x C", "B x C"}
    assert res["A x C"]["p"] == 1.0 and res["A x B"]["p_holm"] >= res["A x B"]["p"]


def test_cluster_bootstrap_ci_contains_point_and_is_deterministic():
    rng = np.random.default_rng(0)
    real = rng.integers(0, 3, 114)
    counts = np.c_[np.minimum(real, rng.integers(0, 3, 114)), real]          # [acusados, total] por arquivo
    f = lambda s: s[0] / s[1] if s[1] else float("nan")                    # noqa: E731
    a = st.cluster_bootstrap(counts, f, n_boot=500, seed=3)
    b = st.cluster_bootstrap(counts, f, n_boot=500, seed=3)
    assert a == b and a["lo"] <= a["point"] <= a["hi"] and a["n_boot"] == 500
    assert st.cluster_bootstrap(counts, f, n_boot=500, seed=4)["lo"] != a["lo"]


def test_cluster_bootstrap_degenerate_data_has_zero_width_ci():
    counts = np.tile([1.0, 2.0], (30, 1))
    r = st.cluster_bootstrap(counts, lambda s: s[0] / s[1], n_boot=200)
    assert r["point"] == r["lo"] == r["hi"] == 0.5


def test_paired_bootstrap_diff():
    a = np.c_[np.ones(60), np.full(60, 2.0)]
    same = st.paired_bootstrap_diff(a, a, lambda s: s[0] / s[1], n_boot=200)
    assert same["diff"] == 0 and same["lo"] == 0 and same["hi"] == 0
    b = np.c_[np.full(60, 0.5), np.full(60, 2.0)]
    d = st.paired_bootstrap_diff(a, b, lambda s: s[0] / s[1], n_boot=200)
    assert d["diff"] == pytest.approx(0.25) and d["lo"] > 0 and d["p_two_sided"] < 0.05
    with pytest.raises(AssertionError):
        st.paired_bootstrap_diff(a, b[:10], lambda s: s[0])


def test_clopper_pearson_and_mean_sd():
    lo, hi = st.clopper_pearson(46, 56)
    assert (lo, hi) == pytest.approx((0.696, 0.911), abs=1e-3)           # IC do artigo: [70%, 90%] arredondado
    assert st.mean_sd([1, 2, 3]) == {"mean": 2.0, "sd": 1.0, "n": 3}
    assert np.isnan(st.mean_sd([5])["sd"])
