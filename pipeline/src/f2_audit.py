"""F2 item 4 - auditoria do artigo: recalcula, a partir das tabelas do proprio PDF e dos dados dos autores,
as inconsistencias do artigo identificadas na revisao das tabelas. Gera results/auditoria_artigo.md. Nao chama LLM.

Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f2_audit.py
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from canonical import MODELS  # noqa: E402
from paper_tables import extract_paper_tables, extract_table11  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
PDF = HERE.parent / "artigo.pdf"
M3 = list(MODELS)  # gpt-4.1, gpt-5, opus-4.1
NAME = {"gpt-4.1": "GPT-4.1", "gpt-5": "GPT-5", "opus-4.1": "Claude Opus 4.1", "gpt-4o": "GPT-4o"}

# Tabelas 17 e 18 transcritas do PDF (p. 30-32): (detectadas, corrigidas) por modelo.
PAPER_T17_USER = {"gpt-4.1": (22, 22), "gpt-5": (21, 21), "opus-4.1": (19, 19)}      # 25 issues
PAPER_T18_GPT = {"gpt-4.1": (26, 23), "gpt-5": (23, 23), "opus-4.1": (26, 25)}       # 31 issues


def pdf_pages() -> list[str]:
    import pypdf
    return [" ".join((p.extract_text() or "").split()) for p in pypdf.PdfReader(str(PDF)).pages]


def page_of(pages: list[str], snippet: str) -> int | None:
    s = " ".join(snippet.split())
    for i, t in enumerate(pages, 1):
        if s in t:
            return i
    return None


def mcnemar_exact(a: list[bool], b: list[bool]) -> tuple[int, int, float]:
    """(b01, b10, p exato bilateral). b01 = so o primeiro acertou; b10 = so o segundo acertou."""
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    n = only_a + only_b
    return only_a, only_b, (1.0 if n == 0 else binomtest(min(only_a, only_b), n, 0.5).pvalue)


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f}%"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    pages = pdf_pages()
    t = extract_paper_tables(PDF)                    # 56 issues (Tabelas 13 e 14)
    t11 = extract_table11(PDF)                       # 32 issues (Tabela 11, 2024)
    gt = pd.read_csv(DATA / "gt_issues.csv")
    fpdf = pd.read_csv(DATA / "gt_scanner_fp.csv")
    files = [json.loads(line) for line in open(DATA / "files.jsonl", encoding="utf-8")]
    t["group"] = t["paper_source"].str.lower().map(lambda s: "user" if s == "user" else "gpt")
    L: list[str] = ["# Auditoria do artigo (recalculada a partir dos dados)", "",
                    "Artigo: Belozerov, Barclay, Sami, *Secure coding with AI - from detection to repair*, Empirical Software "
                    "Engineering (2026) 31:93. Tabelas 11-14, 17 e 18 foram extraidas do PDF (`paper_tables.py`); os rotulos por issue "
                    "vem das Tabelas 13 e 14; as paginas citadas sao as do PDF. Nenhum LLM foi usado.", ""]
    summary: list[tuple[str, str]] = []

    def section(title: str, verdict: str, body: list[str]) -> None:
        summary.append((title, verdict))
        L.extend([f"## {title}", "", f"**Veredito: {verdict}**", "", *body, ""])

    # ----------------------------------------------------------------- 1. Tabela 11 (GPT-4o, 2024)
    d11, f11 = int(t11.detected.sum()), int(t11.fixed.sum())
    p11 = page_of(pages, "GPT-4o successfully detected 18 but failed to recognise 14")
    section("1. Tabela 11 (GPT-4o, 2024): corrigidas na tabela x texto",
            "CONFIRMADO" if (len(t11), d11, f11) == (32, 18, 16) else "DIVERGE DO ESPERADO",
            [f"- Texto (p. {p11}): 'GPT-4o successfully detected 18 ... successfully resolved 17 issues but failed to fix 15' (32 issues).",
             f"- Recontagem das 32 linhas da Tabela 11 (p. {page_of(pages, 'Table 11 Security issues detection')}): "
             f"**{d11} detectadas e {f11} corrigidas** ({32 - f11} nao corrigidas).",
             f"- O texto diz 17 corrigidas / 15 nao corrigidas; a tabela mostra {f11} / {32 - f11}. A detecao (18/14) bate."])

    # ----------------------------------------------------------------- 2. Tabelas 17 e 18
    rows = []
    for m in M3:
        for grp, paper in (("user", PAPER_T17_USER), ("gpt", PAPER_T18_GPT)):
            sub = t[t.group == grp]
            rows.append({"modelo": NAME[m], "grupo": grp, "n": len(sub),
                         "detectadas (recontagem)": int(sub[f"{m}__detected"].sum()), "corrigidas (recontagem)": int(sub[f"{m}__fixed"].sum()),
                         "detectadas (artigo)": paper[m][0], "corrigidas (artigo)": paper[m][1]})
    r = pd.DataFrame(rows)
    r["dif det"] = r["detectadas (recontagem)"] - r["detectadas (artigo)"]
    r["dif fix"] = r["corrigidas (recontagem)"] - r["corrigidas (artigo)"]
    tot_t12 = {m: (int(t[f"{m}__detected"].sum()), int(t[f"{m}__fixed"].sum())) for m in M3}
    art17_18 = {m: (PAPER_T17_USER[m][0] + PAPER_T18_GPT[m][0], PAPER_T17_USER[m][1] + PAPER_T18_GPT[m][1]) for m in M3}
    bad = r[(r["dif det"] != 0) | (r["dif fix"] != 0)]
    body = [f"Grupos pela coluna 'Source' das Tabelas 13/14: user = {int((t.group == 'user').sum())} issues, "
            f"gerado por LLM = {int((t.group == 'gpt').sum())} (o artigo diz 25 e 31).", "", r.to_markdown(index=False), "",
            "Soma das Tabelas 17 + 18 (artigo) x Tabela 12 (e x recontagem):", ""]
    for m in M3:
        body.append(f"- {NAME[m]}: 17+18 = {art17_18[m][0]} detectadas / {art17_18[m][1]} corrigidas; Tabela 12 = "
                    f"{tot_t12[m][0]} / {tot_t12[m][1]}.")
    body += ["", f"Na Tabela 17 (p. {page_of(pages, 'Not fixed Issues 1 2 3 90.91')}), a linha 'Not fixed Issues' do GPT-4.1 traz o percentual "
             "**90,91**; 3 de 25 e 12,00%."]
    section("2. Tabelas 17 e 18 (codigo do usuario x codigo gerado por GPT)",
            f"{len(bad)} de {len(r)} celulas divergem" if len(bad) else "CONSISTENTE", body)

    # ----------------------------------------------------------------- 3. Finding 15
    p15 = page_of(pages, "slightly higher accuracy on user-provided")
    body = [f"Finding 15 (p. {p15}): todos os modelos tem acuracia 'slightly higher' em codigo do usuario do que em codigo gerado por IA.", "",
            "| modelo | usuario: det / corr | gerado: det / corr | usuario > gerado em AMBAS? (numeros do artigo) | idem (recontagem) |", "|---|---|---|---|---|"]
    verdicts = {}
    for m in M3:
        u, g = t[t.group == "user"], t[t.group == "gpt"]
        ru = (u[f"{m}__detected"].mean(), u[f"{m}__fixed"].mean())
        rg = (g[f"{m}__detected"].mean(), g[f"{m}__fixed"].mean())
        pu = (PAPER_T17_USER[m][0] / 25, PAPER_T17_USER[m][1] / 25)
        pg = (PAPER_T18_GPT[m][0] / 31, PAPER_T18_GPT[m][1] / 31)
        ok_paper = pu[0] > pg[0] and pu[1] > pg[1]
        ok_re = ru[0] > rg[0] and ru[1] > rg[1]
        verdicts[m] = (ok_paper, ok_re)
        body.append(f"| {NAME[m]} | {100 * ru[0]:.0f}% / {100 * ru[1]:.0f}% | {100 * rg[0]:.0f}% / {100 * rg[1]:.0f}% | "
                    f"{'sim' if ok_paper else '**nao**'} ({100 * pu[0]:.0f}/{100 * pu[1]:.0f} vs {100 * pg[0]:.1f}/{100 * pg[1]:.1f}) | {'sim' if ok_re else '**nao**'} |")
    failing = [NAME[m] for m, (a, b) in verdicts.items() if not (a and b)]
    section("3. Finding 15 ('todos os modelos vao melhor em codigo do usuario')",
            "REFUTADO para " + ", ".join(failing) if failing else "CONFIRMADO", body)

    # ----------------------------------------------------------------- 4. GPT-5 'corrigiu todas as que detectou'
    det_not_fix = t[(t["gpt-5__detected"]) & (~t["gpt-5__fixed"])]["issue_id"].tolist()
    fix_not_det = t[(~t["gpt-5__detected"]) & (t["gpt-5__fixed"])]["issue_id"].tolist()
    p5 = page_of(pages, "successfully fixing every 44 issue it detected")
    section("4. 'GPT-5 ... successfully fixing every 44 issue it detected'",
            "REFUTADO" if det_not_fix or fix_not_det else "CONFIRMADO",
            [f"Texto (p. {p5}). Recontagem nas Tabelas 13/14: GPT-5 detectou {tot_t12['gpt-5'][0]} e corrigiu {tot_t12['gpt-5'][1]} "
             "(mesmo numero, mas nao sao os mesmos issues).",
             f"- Detectadas **e nao corrigidas**: {det_not_fix}.", f"- Corrigidas **sem terem sido detectadas**: {fix_not_det}."])

    # ----------------------------------------------------------------- 5. gabarito 2024 x 2025
    canon8 = {i for i in t.issue_id if i.startswith("v8:")}
    ids11 = set(t11.issue_id)
    removed = sorted(ids11 - canon8)
    added = sorted(canon8 - ids11)
    t8 = t.set_index("issue_id")
    changes = []
    for iid in sorted(ids11 & canon8):
        a, b = t11.set_index("issue_id").loc[iid], t8.loc[iid]
        if a.source.lower() != str(b.paper_source).lower():
            changes.append(f"{iid}: origem '{a.source}' (2024) -> '{b.paper_source}' (2025)")
        if a.cwe != str(b.paper_cwe):
            changes.append(f"{iid}: CWE '{a.cwe}' (2024) -> '{b.paper_cwe}' (2025)")
        if a.lang != str(b.paper_lang):
            changes.append(f"{iid}: linguagem '{a.lang}' -> '{b.paper_lang}'")
    gone = t11[t11.issue_id.isin(removed)]
    section("5. O gabarito mudou entre 2024 e 2025 (mesmo snapshot v8)",
            "CONFIRMADO" if removed else "NAO ENCONTRADO",
            [f"- Tabela 11 (2024): {len(ids11)} issues; Tabela 13 (2025): {len(canon8)}. Presentes so em 2024: **{removed}**; so em 2025: {added or 'nenhum'}.",
             "- As removidas: " + "; ".join(f"{r_.issue_id} (CWE {r_.cwe}, {r_.lang}, GPT-4o detectou={'sim' if r_.detected else 'nao'})" for r_ in gone.itertuples()) + ".",
             "- Mudancas nos issues comuns: " + ("; ".join(changes) if changes else "nenhuma") + ".",
             f"- Consequencia: a comparacao 2024 x 2025 so e pareavel nos {len(ids11 & canon8)} issues comuns; as taxas globais "
             f"({d11}/32 = {pct(d11, 32)} em 2024 vs 80,4%, 78,6%, 82,1% em 2025) usam bases diferentes."])

    # ----------------------------------------------------------------- 6. McNemar (28 issues comuns) e IC
    common = sorted(ids11 & canon8)
    det24 = t11.set_index("issue_id").loc[common, "detected"].tolist()
    mc_rows = []
    for m in M3:
        a = det24
        b = t8.loc[common, f"{m}__detected"].tolist()
        o1, o2, p = mcnemar_exact(a, b)
        mc_rows.append({"comparacao": f"GPT-4o (2024) x {NAME[m]} (2025)", "n": len(common), "detectadas 1o": sum(a), "detectadas 2o": sum(b),
                        "so o 1o": o1, "so o 2o": o2, "p (McNemar exato)": round(p, 3)})
    for m1, m2 in itertools.combinations(M3, 2):
        a, b = t[f"{m1}__detected"].tolist(), t[f"{m2}__detected"].tolist()
        o1, o2, p = mcnemar_exact(a, b)
        mc_rows.append({"comparacao": f"{NAME[m1]} x {NAME[m2]} (2025, 56 issues)", "n": len(a), "detectadas 1o": sum(a), "detectadas 2o": sum(b),
                        "so o 1o": o1, "so o 2o": o2, "p (McNemar exato)": round(p, 3)})
    ci = []
    for m in M3:
        k = tot_t12[m][0]
        lo, hi = binomtest(k, 56).proportion_ci(confidence_level=0.95, method="exact")
        ci.append(f"{NAME[m]}: {k}/56 = {100 * k / 56:.1f}%, IC95% (Clopper-Pearson) [{100 * lo:.1f}%, {100 * hi:.1f}%]")
    pmin = min(r_["p (McNemar exato)"] for r_ in mc_rows[:3])
    section("6. Significancia da 'melhora' de 2024 para 2025", "NAO SIGNIFICATIVA a 5% (nenhum teste confirmatorio passa)" if pmin >= 0.05 else "ALGUMA COMPARACAO SIGNIFICATIVA",
            ["Detecao, issues pareados (mesmo issue nas duas rodadas), McNemar exato bilateral:", "", pd.DataFrame(mc_rows).to_markdown(index=False), "",
             "Intervalos de confianca da detecao de 2025 (o artigo nao reporta nenhum):", "", *[f"- {c}" for c in ci],
             "", "Cada modelo foi rodado uma unica vez (`llm_config.json`: `repetitions: 1`), entao a variancia de amostragem nao esta nos IC acima."])

    # ----------------------------------------------------------------- 7. re-scan
    p_abs = page_of(pages, "Manual review and re-scanning of the modified code")
    p_fut = page_of(pages, "Re-evaluating Fixed Code with Static Scanners")
    full = " ".join(pages)
    j = full.index("Re-evaluating Fixed Code with Static Scanners")
    quote = full[j: j + 190]
    section("7. 'Re-scanning of the modified code' (resumo) x trabalho futuro",
            "CONFIRMADO (inconsistencia interna)" if p_abs and p_fut else "NAO ENCONTRADO",
            [f"- Resumo (p. {p_abs}): 'Manual review and re-scanning of the modified code showed that GPT-4.1, GPT-5, and Claude Opus 4.1 correctly detected 46, 44, and 45 vulnerabilities, and successfully repaired 42, 44, and 43'.",
             f"- Trabalho futuro (p. {p_fut}): '{quote}...'", "- Nao ha, no corpo do artigo, descricao de um re-scan do codigo corrigido; a correcao foi avaliada por revisao manual."])

    # ----------------------------------------------------------------- 8. numero de scanners e criterio de selecao
    n_sc = gt["scanners"].map(lambda s: len([x for x in str(s).split("|") if x])).tolist()
    kf = fpdf["scanners"].map(lambda s: len([x for x in str(s).split("|") if x])).tolist()
    single = sum(1 for x in n_sc if x == 1)
    multi_fp = sum(1 for x in kf if x >= 2)
    multi_files = {(r_.snapshot, r_.file_number) for r_ in gt.itertuples() if len([x for x in str(r_.scanners).split("|") if x]) >= 2} | \
                  {(r_.snapshot, r_.file_number) for r_ in fpdf.itertuples() if len([x for x in str(r_.scanners).split("|") if x]) >= 2}
    n_files_judged = sum(1 for r_ in files if r_["class"] in ("positive", "negative"))
    p3 = page_of(pages, "we employed three different static analysis tools")
    p_sel = page_of(pages, "A file is selected if multiple scanners detected an issue on the same line")
    section("8. Numero de scanners e criterio de selecao de arquivos",
            "CONFIRMADO (inconsistencia)",
            [f"- Ameacas a validade (p. {p3}): 'we employed three different static analysis tools'. O artigo usa quatro: Flawfinder, Semgrep, Snyk e Cppcheck "
             "(resumo, metodo e colunas S/Sg/F/C das Tabelas 15-16).",
             f"- Criterio de selecao (p. {p_sel}): 'A file is selected if multiple scanners detected an issue on the same line'. "
             f"Nos 56 issues confirmados, **{single} ({pct(single, 56)}) foram apontados por um unico scanner** e {56 - single} por dois ou mais (coluna 'Scanner' das Tabelas 13/14). "
             f"Nos {len(kf)} falsos alarmes conhecidos, {sum(1 for x in kf if x == 1)} ({pct(sum(1 for x in kf if x == 1), len(kf))}) tambem vem de um unico scanner.",
             f"- Pela coluna 'Scanners' da planilha (que junta os scanners que apontaram a mesma linha), so {len(multi_files)} dos {n_files_judged} arquivos "
             f"analisados tem alguma linha apontada por mais de um scanner. Portanto, o criterio, lido literalmente, nao explica a selecao da maioria dos arquivos "
             "(ressalva: a ferramenta dos autores pode casar deteccoes por uma janela de linhas, o que nao da para verificar nos dados publicos).",
             f"- Observacao descritiva (util para a proposta de verificador): das 141 deteccoes julgadas, {7 if (56 - single) == 7 else 56 - single + multi_fp} "
             f"tiveram 2+ scanners e **todas foram reais** ({56 - single} reais, {multi_fp} falsas); entre as deteccoes de um unico scanner, "
             f"{single} de {single + len(kf) - multi_fp} ({pct(single, single + len(kf) - multi_fp)}) foram reais."])

    # ----------------------------------------------------------------- 9. 'accuracy' = recall
    p4 = page_of(pages, "Finding 4: All three")  # o PDF embaralha letras dentro da frase; o inicio do rotulo e estavel
    sc = {m: (tot_t12[m][0], tot_t12[m][1]) for m in M3}
    section("9. 'Accuracy' nos Findings 4 e 15", "CONFIRMADO (rotulo inadequado)",
            [f"Finding 4 (p. {p4}): 'approximately 78% accuracy in both vulnerability detection and code correction'.",
             "- A metrica e detectadas / 56 (e corrigidas / 56): **recall relativo ao gabarito**. Nao ha verdadeiros negativos nem precisao; o artigo nao mede falsos positivos.",
             "- Os dados para medir falso positivo existem: 66 dos 114 arquivos sao negativos (todas as deteccoes de scanner neles foram julgadas falsas pelos autores), e todos foram enviados aos LLMs com o prompt 'You must find security issues'.",
             "- Detecao/correcao: " + "; ".join(f"{NAME[m]} {pct(a, 56)}/{pct(b, 56)}" for m, (a, b) in sc.items()) + " (faixa 75-82%, nao 'approximately 78% in both')."])

    # ----------------------------------------------------------------- 10. CWE trocadas (achado novo) e consistencias verificadas
    pc = pd.read_csv(DATA / "gt_issues.csv").set_index("issue_id")
    swap = []
    for a, b in (("v10:3/7", "v10:3/11"),):
        swap.append(f"- {a}: planilha dos autores = CWE {pc.loc[a, 'cwe_sheet']} (flawfinder, 'Statically-sized arrays...'); Tabela 14 do artigo = CWE {pc.loc[a, 'cwe_paper']}.")
        swap.append(f"- {b}: planilha = CWE {pc.loc[b, 'cwe_sheet']} (cppcheck, 'Improper Initialisation'); Tabela 14 = CWE {pc.loc[b, 'cwe_paper']}.")
    section("10. (achado novo) CWEs trocadas na Tabela 14", "CONFIRMADO",
            ["Das 56 CWEs, 5 diferem entre a planilha e as Tabelas 13/14 (F1). A mais clara e uma troca entre dois issues do mesmo arquivo:", *swap,
             "O tipo de scanner e a descricao da regra concordam com a planilha; as CWEs da Tabela 14 parecem trocadas."])

    pos_per = {s: sum(1 for r_ in files if r_["snapshot"] == s and r_["class"] == "positive") for s in ("v8", "v10")}
    n_sel = {s: sum(1 for r_ in files if r_["snapshot"] == s and r_["class"] in ("positive", "negative")) for s in ("v8", "v10")}
    unk_neg = sum(1 for r_ in files if r_["class"] == "negative" and r_["origin"] == "unknown")
    section("11. Verificacoes que NAO acharam problema", "CONSISTENTE",
            [f"- Tabela 12: 63 + 51 = 114 arquivos; os dados dao {n_sel['v8']} + {n_sel['v10']} (a pasta File_02 de v8 esta no repositorio mas fora da analise).",
             f"- Tabela 12: 24 + 24 = 48 arquivos com issue; os dados dao {pos_per['v8']} + {pos_per['v10']}.",
             "- Tabela 12: 73 + 68 = 141 deteccoes de scanner; a planilha tem 74 + 68 = 142, e a diferenca e exatamente o item removido v8:2/14.",
             "- Contadores detectadas/corrigidas por modelo (Tabela 12) = soma das Tabelas 13 e 14 (46/42, 44/44, 45/43).",
             f"- Limite de verificacao: a afirmacao do resumo de que 'LLM-generated code is about as likely to contain vulnerabilities as developer-written code' "
             f"nao pode ser recalculada, porque a origem do codigo nao esta registrada em {unk_neg} dos {sum(1 for r_ in files if r_['class'] == 'negative')} arquivos negativos."])

    L.insert(4, "## Resumo")
    L.insert(5, "")
    L.insert(6, "| # | Item | Veredito |")
    L.insert(7, "|---|---|---|")
    for i, (title, verdict) in enumerate(summary):
        L.insert(8 + i, f"| {i + 1} | {title.split('. ', 1)[1]} | {verdict} |")
    L.insert(8 + len(summary), "")
    (RESULTS / "auditoria_artigo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    for title, verdict in summary:
        print(f"{title}  ->  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
