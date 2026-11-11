# Auditoria do artigo (recalculada a partir dos dados)

Artigo: Belozerov, Barclay, Sami, *Secure coding with AI - from detection to repair*, Empirical Software Engineering (2026) 31:93. Tabelas 11-14, 17 e 18 foram extraidas do PDF (`paper_tables.py`); os rotulos por issue vem das Tabelas 13 e 14; as paginas citadas sao as do PDF. Nenhum LLM foi usado.

## Resumo

| # | Item | Veredito |
|---|---|---|
| 1 | Tabela 11 (GPT-4o, 2024): corrigidas na tabela x texto | CONFIRMADO |
| 2 | Tabelas 17 e 18 (codigo do usuario x codigo gerado por GPT) | 3 de 6 celulas divergem |
| 3 | Finding 15 ('todos os modelos vao melhor em codigo do usuario') | REFUTADO para GPT-4.1, Claude Opus 4.1 |
| 4 | 'GPT-5 ... successfully fixing every 44 issue it detected' | REFUTADO |
| 5 | O gabarito mudou entre 2024 e 2025 (mesmo snapshot v8) | CONFIRMADO |
| 6 | Significancia da 'melhora' de 2024 para 2025 | NAO SIGNIFICATIVA a 5% (nenhum teste confirmatorio passa) |
| 7 | 'Re-scanning of the modified code' (resumo) x trabalho futuro | CONFIRMADO (inconsistencia interna) |
| 8 | Numero de scanners e criterio de selecao de arquivos | CONFIRMADO (inconsistencia) |
| 9 | 'Accuracy' nos Findings 4 e 15 | CONFIRMADO (rotulo inadequado) |
| 10 | (achado novo) CWEs trocadas na Tabela 14 | CONFIRMADO |
| 11 | Verificacoes que NAO acharam problema | CONSISTENTE |

## 1. Tabela 11 (GPT-4o, 2024): corrigidas na tabela x texto

**Veredito: CONFIRMADO**

- Texto (p. 17): 'GPT-4o successfully detected 18 ... successfully resolved 17 issues but failed to fix 15' (32 issues).
- Recontagem das 32 linhas da Tabela 11 (p. 19): **18 detectadas e 16 corrigidas** (16 nao corrigidas).
- O texto diz 17 corrigidas / 15 nao corrigidas; a tabela mostra 16 / 16. A detecao (18/14) bate.

## 2. Tabelas 17 e 18 (codigo do usuario x codigo gerado por GPT)

**Veredito: 3 de 6 celulas divergem**

Grupos pela coluna 'Source' das Tabelas 13/14: user = 25 issues, gerado por LLM = 31 (o artigo diz 25 e 31).

| modelo          | grupo   |   n |   detectadas (recontagem) |   corrigidas (recontagem) |   detectadas (artigo) |   corrigidas (artigo) |   dif det |   dif fix |
|:----------------|:--------|----:|--------------------------:|--------------------------:|----------------------:|----------------------:|----------:|----------:|
| GPT-4.1         | user    |  25 |                        20 |                        20 |                    22 |                    22 |        -2 |        -2 |
| GPT-4.1         | gpt     |  31 |                        26 |                        22 |                    26 |                    23 |         0 |        -1 |
| GPT-5           | user    |  25 |                        21 |                        21 |                    21 |                    21 |         0 |         0 |
| GPT-5           | gpt     |  31 |                        23 |                        23 |                    23 |                    23 |         0 |         0 |
| Claude Opus 4.1 | user    |  25 |                        19 |                        19 |                    19 |                    19 |         0 |         0 |
| Claude Opus 4.1 | gpt     |  31 |                        26 |                        24 |                    26 |                    25 |         0 |        -1 |

Soma das Tabelas 17 + 18 (artigo) x Tabela 12 (e x recontagem):

- GPT-4.1: 17+18 = 48 detectadas / 45 corrigidas; Tabela 12 = 46 / 42.
- GPT-5: 17+18 = 44 detectadas / 44 corrigidas; Tabela 12 = 44 / 44.
- Claude Opus 4.1: 17+18 = 45 detectadas / 44 corrigidas; Tabela 12 = 45 / 43.

Na Tabela 17 (p. 31), a linha 'Not fixed Issues' do GPT-4.1 traz o percentual **90,91**; 3 de 25 e 12,00%.

## 3. Finding 15 ('todos os modelos vao melhor em codigo do usuario')

**Veredito: REFUTADO para GPT-4.1, Claude Opus 4.1**

Finding 15 (p. 32): todos os modelos tem acuracia 'slightly higher' em codigo do usuario do que em codigo gerado por IA.

| modelo | usuario: det / corr | gerado: det / corr | usuario > gerado em AMBAS? (numeros do artigo) | idem (recontagem) |
|---|---|---|---|---|
| GPT-4.1 | 80% / 80% | 84% / 71% | sim (88/88 vs 83.9/74.2) | **nao** |
| GPT-5 | 84% / 84% | 74% / 74% | sim (84/84 vs 74.2/74.2) | sim |
| Claude Opus 4.1 | 76% / 76% | 84% / 77% | **nao** (76/76 vs 83.9/80.6) | **nao** |

## 4. 'GPT-5 ... successfully fixing every 44 issue it detected'

**Veredito: REFUTADO**

Texto (p. 21). Recontagem nas Tabelas 13/14: GPT-5 detectou 44 e corrigiu 44 (mesmo numero, mas nao sao os mesmos issues).
- Detectadas **e nao corrigidas**: ['v10:39/61'].
- Corrigidas **sem terem sido detectadas**: ['v8:1/1a'].

## 5. O gabarito mudou entre 2024 e 2025 (mesmo snapshot v8)

**Veredito: CONFIRMADO**

- Tabela 11 (2024): 32 issues; Tabela 13 (2025): 28. Presentes so em 2024: **['v8:2/14', 'v8:4/21', 'v8:55/22', 'v8:8/14']**; so em 2025: nenhum.
- As removidas: v8:2/14 (CWE 352, C#, GPT-4o detectou=nao); v8:4/21 (CWE 119/120, C, GPT-4o detectou=sim); v8:8/14 (CWE 119/120, C, GPT-4o detectou=sim); v8:55/22 (CWE 126, C, GPT-4o detectou=nao).
- Mudancas nos issues comuns: v8:62/19: origem 'gpt3.5' (2024) -> 'user' (2025); v8:9/9: CWE '120/20' (2024) -> '20/120' (2025).
- Consequencia: a comparacao 2024 x 2025 so e pareavel nos 28 issues comuns; as taxas globais (18/32 = 56.2% em 2024 vs 80,4%, 78,6%, 82,1% em 2025) usam bases diferentes.

## 6. Significancia da 'melhora' de 2024 para 2025

**Veredito: NAO SIGNIFICATIVA a 5% (nenhum teste confirmatorio passa)**

Detecao, issues pareados (mesmo issue nas duas rodadas), McNemar exato bilateral:

| comparacao                                  |   n |   detectadas 1o |   detectadas 2o |   so o 1o |   so o 2o |   p (McNemar exato) |
|:--------------------------------------------|----:|----------------:|----------------:|----------:|----------:|--------------------:|
| GPT-4o (2024) x GPT-4.1 (2025)              |  28 |              16 |              23 |         2 |         9 |               0.065 |
| GPT-4o (2024) x GPT-5 (2025)                |  28 |              16 |              21 |         4 |         9 |               0.267 |
| GPT-4o (2024) x Claude Opus 4.1 (2025)      |  28 |              16 |              22 |         2 |         8 |               0.109 |
| GPT-4.1 x GPT-5 (2025, 56 issues)           |  56 |              46 |              44 |         4 |         2 |               0.688 |
| GPT-4.1 x Claude Opus 4.1 (2025, 56 issues) |  56 |              46 |              45 |         3 |         2 |               1     |
| GPT-5 x Claude Opus 4.1 (2025, 56 issues)   |  56 |              44 |              45 |         4 |         5 |               1     |

Intervalos de confianca da detecao de 2025 (o artigo nao reporta nenhum):

- GPT-4.1: 46/56 = 82.1%, IC95% (Clopper-Pearson) [69.6%, 91.1%]
- GPT-5: 44/56 = 78.6%, IC95% (Clopper-Pearson) [65.6%, 88.4%]
- Claude Opus 4.1: 45/56 = 80.4%, IC95% (Clopper-Pearson) [67.6%, 89.8%]

Cada modelo foi rodado uma unica vez (`llm_config.json`: `repetitions: 1`), entao a variancia de amostragem nao esta nos IC acima.

## 7. 'Re-scanning of the modified code' (resumo) x trabalho futuro

**Veredito: CONFIRMADO (inconsistencia interna)**

- Resumo (p. 1): 'Manual review and re-scanning of the modified code showed that GPT-4.1, GPT-5, and Claude Opus 4.1 correctly detected 46, 44, and 45 vulnerabilities, and successfully repaired 42, 44, and 43'.
- Trabalho futuro (p. 35): 'Re-evaluating Fixed Code with Static Scanners: We plan to re-run the static scanners on the source code files modified by LLM, where security issues were purportedly fixed, to determine if t...'
- Nao ha, no corpo do artigo, descricao de um re-scan do codigo corrigido; a correcao foi avaliada por revisao manual.

## 8. Numero de scanners e criterio de selecao de arquivos

**Veredito: CONFIRMADO (inconsistencia)**

- Ameacas a validade (p. 33): 'we employed three different static analysis tools'. O artigo usa quatro: Flawfinder, Semgrep, Snyk e Cppcheck (resumo, metodo e colunas S/Sg/F/C das Tabelas 15-16).
- Criterio de selecao (p. 13): 'A file is selected if multiple scanners detected an issue on the same line'. Nos 56 issues confirmados, **49 (87.5%) foram apontados por um unico scanner** e 7 por dois ou mais (coluna 'Scanner' das Tabelas 13/14). Nos 85 falsos alarmes conhecidos, 85 (100.0%) tambem vem de um unico scanner.
- Pela coluna 'Scanners' da planilha (que junta os scanners que apontaram a mesma linha), so 7 dos 114 arquivos analisados tem alguma linha apontada por mais de um scanner. Portanto, o criterio, lido literalmente, nao explica a selecao da maioria dos arquivos (ressalva: a ferramenta dos autores pode casar deteccoes por uma janela de linhas, o que nao da para verificar nos dados publicos).
- Observacao descritiva (util para a proposta de verificador): das 141 deteccoes julgadas, 7 tiveram 2+ scanners e **todas foram reais** (7 reais, 0 falsas); entre as deteccoes de um unico scanner, 49 de 134 (36.6%) foram reais.

## 9. 'Accuracy' nos Findings 4 e 15

**Veredito: CONFIRMADO (rotulo inadequado)**

Finding 4 (p. 23): 'approximately 78% accuracy in both vulnerability detection and code correction'.
- A metrica e detectadas / 56 (e corrigidas / 56): **recall relativo ao gabarito**. Nao ha verdadeiros negativos nem precisao; o artigo nao mede falsos positivos.
- Os dados para medir falso positivo existem: 66 dos 114 arquivos sao negativos (todas as deteccoes de scanner neles foram julgadas falsas pelos autores), e todos foram enviados aos LLMs com o prompt 'You must find security issues'.
- Detecao/correcao: GPT-4.1 82.1%/75.0%; GPT-5 78.6%/78.6%; Claude Opus 4.1 80.4%/76.8% (faixa 75-82%, nao 'approximately 78% in both').

## 10. (achado novo) CWEs trocadas na Tabela 14

**Veredito: CONFIRMADO**

Das 56 CWEs, 5 diferem entre a planilha e as Tabelas 13/14 (ver DIARIO, F1). A mais clara e uma troca entre dois issues do mesmo arquivo:
- v10:3/7: planilha dos autores = CWE 119|120 (flawfinder, 'Statically-sized arrays...'); Tabela 14 do artigo = CWE 665.
- v10:3/11: planilha = CWE 665 (cppcheck, 'Improper Initialisation'); Tabela 14 = CWE 119|120.
O tipo de scanner e a descricao da regra concordam com a planilha; as CWEs da Tabela 14 parecem trocadas.

## 11. Verificacoes que NAO acharam problema

**Veredito: CONSISTENTE**

- Tabela 12: 63 + 51 = 114 arquivos; os dados dao 63 + 51 (a pasta File_02 de v8 esta no repositorio mas fora da analise; ver DIARIO, F1).
- Tabela 12: 24 + 24 = 48 arquivos com issue; os dados dao 24 + 24.
- Tabela 12: 73 + 68 = 141 deteccoes de scanner; a planilha tem 74 + 68 = 142, e a diferenca e exatamente o item removido v8:2/14.
- Contadores detectadas/corrigidas por modelo (Tabela 12) = soma das Tabelas 13 e 14 (46/42, 44/44, 45/43).
- Limite de verificacao: a afirmacao do resumo de que 'LLM-generated code is about as likely to contain vulnerabilities as developer-written code' nao pode ser recalculada, porque a origem do codigo nao esta registrada em 37 dos 66 arquivos negativos.

