"""F8 - figuras do relatorio (PNG em pipeline/results/figs/). Sem LLM. Roda depois de f7_analyze.py (le runs/ e o gabarito).

1. recall x taxa de falsos alarmes conhecidos: curva do B1 (corte de confianca do A1) e os pontos de B0, C1, C2, C3 (H4);
   dois paineis: regra estrita (principal) e so linha +-3 (sensibilidade).
2. por configuracao: taxa de falsos alarmes conhecidos e media de achados fora do gabarito por arquivo (IC 95% por arquivo).
3. verificador (C1, C2, C3): falsos alarmes removidos e verdadeiros positivos perdidos, sobre os achados do B1.

Cores: ordem fixa da paleta validada (azul, laranja, verde-agua, amarelo, magenta) = B0, B1, C1, C2, C3; a ordem das figuras nao
muda a cor de uma configuracao. Contraste baixo de verde-agua/amarelo/magenta: todo ponto tem rotulo direto e as tabelas estao em
results/f7_resultados.md. Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f8_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

import f7_analyze as f7  # noqa: E402
import metrics as mt  # noqa: E402
from cwe import CWEHierarchy, load_families  # noqa: E402
from stats import clopper_pearson, cluster_bootstrap  # noqa: E402

FIGS = f7.RESULTS / "figs"
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COLOR = {"B0": "#2a78d6", "B1": "#eb6834", "C1": "#1baf7a", "C2": "#eda100", "C3": "#e87ba4"}
MARKER = {"B0": "o", "B1": "s", "C1": "D", "C2": "^", "C3": "v"}      # canal secundario: forma (contraste baixo de 3 tons)
NAME = {"B0": "B0 (prompt do artigo)", "B1": "B1 (A1 só)", "C1": "C1", "C2": "C2", "C3": "C3"}


def setup() -> None:
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 9.5, "text.color": INK, "axes.labelcolor": INK2,
        "axes.edgecolor": AXIS, "axes.linewidth": 1.0, "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False})


def tidy(ax, xlabel: str, ylabel: str, grid_axis: str = "y") -> None:
    ax.grid(axis=grid_axis)
    ax.grid(axis="x" if grid_axis == "y" else "y", visible=False)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.tick_params(length=0)


def fig_curve(all_res, gt, hier, fams, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.7))
    for ax, (title, kw) in zip(axes, (("Regra estrita (principal): linha ±3 e CWE compatível", {}),
                                      ("Sensibilidade: só linha ±3, sem checar a CWE", {"require_cwe": False}))):
        var = f7.run_variant(all_res, gt, "main", hier, fams, **kw)
        cur = mt.confidence_curve(all_res["B1"], gt, hierarchy=hier, families=fams, **kw)
        ax.plot(100 * cur["false_alarm_rate"], 100 * cur["recall"], "-", color=COLOR["B1"], lw=2, alpha=0.9, zorder=2)
        ax.plot(100 * cur["false_alarm_rate"], 100 * cur["recall"], "o", color=COLOR["B1"], ms=4, mec=SURFACE, mew=1, zorder=3)
        pts: dict[tuple, list[str]] = {}
        for c in f7.CONFIGS:
            m = var[c][0].metrics()
            pts.setdefault((round(100 * m["false_alarm_rate"], 2), round(100 * m["recall"], 2)), []).append(c)
        xmax = max(max(x for x, _ in pts), 100 * cur["false_alarm_rate"].max())
        ymax = max(max(y for _, y in pts), 100 * cur["recall"].max())
        for (x, y), cfgs in pts.items():
            for k, c in enumerate(sorted(cfgs, reverse=True)):               # marcadores concentricos quando coincidem
                ax.plot([x], [y], MARKER[c], color=COLOR[c], ms=(8 + 3 * (len(cfgs) - 1 - k)) if len(cfgs) > 1 else 10, mec=SURFACE, mew=2, zorder=4 + k)
            label = " = ".join(sorted(cfgs)) if len(cfgs) > 1 else NAME[cfgs[0]]
            dx, dy = (0.03 * xmax, -0.015 * ymax) if cfgs != ["B1"] else (0.03 * xmax, -0.075 * ymax)
            ax.annotate(label, (x, y), xytext=(x + dx, y + dy), fontsize=9.5, color=INK, va="center", zorder=6)
        ax.set_xlim(-0.03 * xmax, 1.28 * xmax)
        ax.set_ylim(-0.03 * ymax, 1.12 * ymax)
        ax.set_title(title, fontsize=10.5, color=INK, loc="left", pad=8)
        tidy(ax, "Falsos alarmes conhecidos acusados (% de 85)", "Issues reais acusadas (% de 56)", "both")
        ax.grid(axis="x", visible=True)
    fig.tight_layout()
    fig.text(0.01, -0.02, "Linha laranja: B1 aceitando só achados com confiança do A1 ≥ limiar (cada ponto é um limiar). Marcadores concêntricos = configurações com o mesmo valor exato.",
             fontsize=8.5, color=INK2)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def bars(ax, names, vals, lo, hi, fmt_fn, ylabel, ymax):
    x = np.arange(len(names))
    ax.bar(x, vals, width=0.58, color=[COLOR[n] for n in names], edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.errorbar(x, vals, yerr=[np.array(vals) - np.array(lo), np.array(hi) - np.array(vals)], fmt="none", ecolor=INK2, elinewidth=1.2, capsize=3, zorder=4)
    for xi, v, h in zip(x, vals, hi):
        ax.text(xi, h + 0.025 * ymax, fmt_fn(v), ha="center", va="bottom", fontsize=9.5, color=INK, zorder=5)
    ax.set_xticks(x, names, color=INK2)
    ax.set_ylim(0, ymax)
    tidy(ax, "", ylabel)


def fig_far_and_out(all_res, gt, hier, fams, path: Path, n_boot: int = 2000) -> None:
    var = f7.run_variant(all_res, gt, "main", hier, fams)
    cfgs = f7.CONFIGS
    far, out = [], []
    for c in cfgs:
        cnt = var[c][1].to_numpy(float)
        far.append(cluster_bootstrap(cnt, lambda s: f7.metric_value("false_alarm_rate", s), n_boot=n_boot))
        out.append(cluster_bootstrap(cnt, lambda s: s[f7.IDX["out"]] / (s[f7.IDX["n_pos"]] + s[f7.IDX["n_neg"]]), n_boot=n_boot))
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.3))
    ymax1 = 100 * max(d["hi"] for d in far) * 1.25
    bars(axes[0], cfgs, [100 * d["point"] for d in far], [100 * d["lo"] for d in far], [100 * d["hi"] for d in far], lambda v: f"{v:.1f}%",
         "Falsos alarmes conhecidos acusados (% de 85)", ymax1)
    ymax2 = max(d["hi"] for d in out) * 1.25
    bars(axes[1], cfgs, [d["point"] for d in out], [d["lo"] for d in out], [d["hi"] for d in out], lambda v: f"{v:.2f}",
         "Achados fora do gabarito por arquivo (média)", ymax2)
    axes[0].set_title("Falsos alarmes que os autores examinaram e julgaram seguros", fontsize=10.5, loc="left", color=INK, pad=8)
    axes[1].set_title("Achados sem rótulo (não julgados), média por arquivo", fontsize=10.5, loc="left", color=INK, pad=8)
    fig.text(0.01, -0.02, "Barras de erro: IC de 95% por bootstrap sobre arquivos (114 arquivos, 2000 réplicas). Regra estrita; verificador: 'uncertain' = rejeitado.",
             fontsize=8.5, color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_verifier(all_res, gt, hier, fams, path: Path) -> None:
    var = f7.run_variant(all_res, gt, "main", hier, fams)
    ref = var["B1"][0]
    cfgs = ["C1", "C2", "C3"]
    eff = {c: mt.verifier_effect(ref, var[c][0]) for c in cfgs}
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.3), sharey=True)
    for ax, (key_n, key_d, title) in zip(axes, (("fp_removed", "fp_ref", "Falsos alarmes conhecidos removidos (quanto mais, melhor)"),
                                                ("tp_lost", "tp_ref", "Issues reais perdidas (quanto menos, melhor)"))):
        vals, lo, hi = [], [], []
        for c in cfgs:
            k, n = eff[c][key_n], eff[c][key_d]
            l, h = clopper_pearson(k, n)
            vals.append(100 * k / n)
            lo.append(100 * l)
            hi.append(100 * h)
        bars(ax, cfgs, vals, lo, hi, lambda v: f"{v:.0f}%", "% dos locais que o A1 (B1) acusava" if ax is axes[0] else "", 118)
        for xi, c in enumerate(cfgs):
            ax.text(xi, 2.5, f"{eff[c][key_n]}/{eff[c][key_d]}", ha="center", va="bottom", fontsize=9, color="#ffffff" if c != "C2" else INK, zorder=6)
        ax.set_title(title, fontsize=10.5, loc="left", color=INK, pad=8)
        ax.set_yticks([0, 25, 50, 75, 100])
    fig.text(0.01, -0.02, "Barras de erro: IC exato de 95% (Clopper-Pearson) sobre poucos locais; C1 e C3 têm o mesmo conjunto aceito (o A3a decide nos dois).",
             fontsize=8.5, color=INK2)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    setup()
    FIGS.mkdir(parents=True, exist_ok=True)
    gt = mt.load_gt(f7.DATA)
    hier = CWEHierarchy.from_xml(f7.DATA / "cwe" / "1000.xml")
    fams = load_families(f7.HERE / "matching_families.yaml")
    all_res = f7.load_all("main")
    fig_curve(all_res, gt, hier, fams, FIGS / "fig1_recall_vs_falsos_alarmes.png")
    fig_far_and_out(all_res, gt, hier, fams, FIGS / "fig2_falsos_alarmes_e_fora_do_gabarito.png")
    fig_verifier(all_res, gt, hier, fams, FIGS / "fig3_verificador_remocao_e_perda.png")
    print("figuras em", FIGS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
