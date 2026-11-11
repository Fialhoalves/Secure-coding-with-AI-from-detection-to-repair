"""Valores canonicos do artigo (Tabelas 12-14 de Belozerov et al. 2026).

Estes valores sao usados SO para validar o gabarito reconstruido a partir da planilha dos autores.
Nenhum agente do pipeline os recebe.
"""

# 56 issues reais, no formato "<snapshot>:<arquivo>/<linha><sufixo>" (sufixo a/b quando ha 2 na mesma linha).
CANONICAL_V8 = ("1/1a 1/1b 3/29 4/101 5/63 6/8 7/39 8/36 9/9 10/42 11/40 12/36 13/49 14/14 14/63 18/83 "
                "20/16 22/7 23/9 48/23 49/9 49/27 52/14 52/42 53/13 54/2 61/1 62/19").split()
CANONICAL_V10 = ("1/57 1/65 1/132 2/7 3/7 3/11 4/78 5/25 6/78 7/81 8/82 9/23 10/37 11/11 12/23 12/25 13/13 "
                 "15/17 19/18 23/27 27/83 28/7 31/53 39/61 40/8 42/15 43/4 47/36").split()
CANONICAL_IDS = tuple([f"v8:{i}" for i in CANONICAL_V8] + [f"v10:{i}" for i in CANONICAL_V10])

# Modelos do artigo: chave curta -> nome da pasta em LLMs/
MODELS = {
    "gpt-4.1": "gpt-4.1-2025-04-14",
    "gpt-5": "gpt-5-2025-08-07",
    "opus-4.1": "claude-opus-4-1-20250805",
}

# (detectadas, corrigidas) por modelo e snapshot (Tabelas 12-14 do artigo).
EXPECTED_COUNTS = {
    "gpt-4.1": {"v8": (23, 21), "v10": (23, 21)},
    "gpt-5": {"v8": (21, 22), "v10": (23, 22)},
    "opus-4.1": {"v8": (22, 23), "v10": (23, 20)},
}

# Issues que nenhum dos 3 modelos detectou.
NEVER_DETECTED = ("v8:8/36", "v8:14/63", "v8:52/42", "v10:4/78", "v10:6/78", "v10:28/7")

# Divergencia conhecida planilha x artigo (ver DIARIO): "Yes" na planilha de 2025, ausente da lista do artigo.
KNOWN_DIVERGENT = ("v8:2/14",)
EXPECTED_FILES = {"positive": 48, "negative": 66, "excluded": 1}
EXPECTED_SHEET_ROWS = {"v8": 74, "v10": 68}
EXPECTED_KNOWN_FP = 85
