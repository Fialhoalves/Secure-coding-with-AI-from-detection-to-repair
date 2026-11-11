"""F4 - prepara os 56 casos da validacao do julgamento automatico de correcao: o patch que o GPT-4.1 gerou no artigo
(ultimo New_generated_code da pasta) e o achado reconstruido a partir do gabarito (CWE, linha, descricao do scanner).

O arquivo gerado (data/f4_fix_cases.jsonl) NAO traz os rotulos "Was issue fixed" dos autores: esses ficam so na maquina local
e sao comparados depois (f4_analyze.py). Sem LLM.

Uso:  pipeline\\.venv\\Scripts\\python.exe -I pipeline\\src\\f4_prepare.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"


def finding_from_issue(row: pd.Series, source_code: str | None, scanner_text: str | None) -> dict:
    """Achado no mesmo formato do A1, para o A3b julgar o patch. Sem a classificacao 'real' dos autores e sem rotulos de correcao."""
    desc = re.sub(r"^\s*(yes|sim)\b[,.:;\s-]*", "", str(row["verdict_raw"]), flags=re.I).strip() or "see scanner message"
    cwes = [x for x in str(row["cwe_ids"]).split("|") if x and x != "nan"]
    return {"id": "G1", "cwe": f"CWE-{cwes[0]}" if cwes else "none", "lines": [int(row["line"])], "title": desc[:300],
            "untrusted_source": "not specified (see title)", "sink": (source_code or "").strip()[:200],
            "trigger": (scanner_text or desc)[:300], "assumptions": "none"}


def scanner_finding(row: pd.Series) -> dict:
    """Achado reconstruido SO do relatorio do scanner (igual para issue real e falso alarme: nada da explicacao dos autores,
    que traz o veredito). Para a calibracao do A3a."""
    dets = json.loads(row["detections_json"]) if pd.notna(row["detections_json"]) else []
    text = next((d.get("text") for d in dets if d.get("text")), None) or "static-analysis warning"
    cwes = [x for x in str(row["cwe_ids"]).split("|") if x and x != "nan"]
    src = str(row["source_code"]).strip() if pd.notna(row["source_code"]) else ""
    return {"id": "G1", "cwe": f"CWE-{cwes[0]}" if cwes else "none", "lines": [int(row["line"])], "title": text[:300],
            "untrusted_source": "not specified (static-analysis report)", "sink": src[:200],
            "trigger": "not specified (static-analysis report)", "assumptions": "none"}


def write_verifier_cases(gt: pd.DataFrame, files: dict) -> int:
    """141 casos (56 issues reais + 85 falsos alarmes conhecidos) para ver se o A3a confirma o que e real e refuta o que e seguro.
    O arquivo NAO traz o rotulo (real/falso alarme): a juncao e feita localmente por case_id."""
    fp = pd.read_csv(DATA / "gt_scanner_fp.csv")
    ids = list(gt["issue_id"]) + list(fp["issue_id"])
    assert len(ids) == len(set(ids)), "case_id repetido entre issues reais e falsos alarmes"
    n = 0
    with open(DATA / "f4_verifier_cases.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for _, row in pd.concat([gt, fp], ignore_index=True).iterrows():
            rec = files[f"{row['snapshot']}:File_{int(row['file_number']):02d}"]
            f.write(json.dumps({"case_id": row["issue_id"], "file": f"{row['snapshot']}:File_{int(row['file_number']):02d}", "snapshot": rec["snapshot"],
                                "folder": rec["folder"], "file_number": rec["file_number"], "lang": rec["language"], "ext": rec["code"]["ext"],
                                "code_path": rec["code"]["path"], "finding": scanner_finding(row)}, ensure_ascii=False) + "\n")
            n += 1
    return n


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    gt = pd.read_csv(DATA / "gt_issues.csv")
    files = {f"{r['snapshot']}:{r['folder']}": r for r in (json.loads(line) for line in open(DATA / "files.jsonl", encoding="utf-8"))}
    cases = []
    for _, row in gt.iterrows():
        fid = f"{row['snapshot']}:File_{int(row['file_number']):02d}"
        rec = files[fid]
        new = rec["models"]["gpt-4.1"]["new_code"]
        dets = json.loads(row["detections_json"]) if pd.notna(row["detections_json"]) else []
        text = next((d.get("text") for d in dets if d.get("text")), None)
        cases.append({"issue_id": row["issue_id"], "file": fid, "snapshot": rec["snapshot"], "folder": rec["folder"], "file_number": rec["file_number"],
                      "lang": rec["language"], "ext": rec["code"]["ext"], "code_path": rec["code"]["path"], "patch_path": new[-1],
                      "finding": finding_from_issue(row, row["source_code"] if pd.notna(row["source_code"]) else None, text)})
    with open(DATA / "f4_fix_cases.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{write_verifier_cases(gt, files)} casos de calibracao do A3a em {DATA / 'f4_verifier_cases.jsonl'}")
    print(f"{len(cases)} casos em {DATA / 'f4_fix_cases.jsonl'}; exemplo:")
    print(json.dumps(cases[0]["finding"], ensure_ascii=False, indent=1)[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
