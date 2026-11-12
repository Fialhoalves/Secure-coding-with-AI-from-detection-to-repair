# F2 - reanalise dos dados do artigo

**Validacao do matcher de texto livre: NAO atingiu a meta (kappa >= 0,7).** Melhor variante: `cwe+ident/prosa (e)` com kappa = 0.304 (acordo 0.637). A regra adotada (`cwe+ident/prosa (ou)`) deu kappa = 0.169.

## Extracao de CWEs x planilha (v8)

- pares (arquivo,modelo) v8 com CWEs na planilha: 94
- conjunto igual: 74
- extraido contem o da planilha: 92
- planilha tem CWE que a regex nao achou: 0

## Validacao do matcher (variantes, 56 issues x 3 modelos = 168 pares)

| variante                          |   n |   acordo |   kappa |   TP |   FP |   FN |   TN |
|:----------------------------------|----:|---------:|--------:|-----:|-----:|-----:|-----:|
| cwe/igual                         | 168 |    0.613 |   0.215 |   78 |    8 |   57 |   25 |
| cwe/+familias                     | 168 |    0.702 |   0.233 |  100 |   15 |   35 |   18 |
| cwe/+hierarquia                   | 168 |    0.732 |   0.276 |  105 |   15 |   30 |   18 |
| cwe/+hierarquia c/ pilares        | 168 |    0.732 |   0.276 |  105 |   15 |   30 |   18 |
| ident/prosa                       | 168 |    0.679 |   0.242 |   93 |   12 |   42 |   21 |
| ident/completo                    | 168 |    0.792 |   0.131 |  128 |   28 |    7 |    5 |
| cwe+ident/prosa (ou)              | 168 |    0.774 |   0.169 |  122 |   25 |   13 |    8 |
| cwe+ident/completo (ou)           | 168 |    0.798 |   0.116 |  130 |   29 |    5 |    4 |
| cwe+ident/prosa (e)               | 168 |    0.637 |   0.304 |   76 |    2 |   59 |   31 |
| ident+nomes/prosa                 | 168 |    0.75  |   0.128 |  118 |   25 |   17 |    8 |
| cwe+ident+nomes/prosa (e)         | 168 |    0.667 |   0.214 |   92 |   13 |   43 |   20 |
| secao: cwe+ident/prosa (e)        | 168 |    0.565 |   0.25  |   62 |    0 |   73 |   33 |
| secao: cwe+ident+nomes/prosa (e)  | 168 |    0.595 |   0.208 |   74 |    7 |   61 |   26 |
| secao: cwe+ident+nomes/prosa (ou) | 168 |    0.815 |   0.207 |  131 |   27 |    4 |    6 |

## Indicadores de falso positivo (configuracao original do artigo)

Indicadores por arquivo nao dependem do matcher; os demais saem como intervalo estrita..leniente.

|                                                   | gpt-4.1       | gpt-5         | opus-4.1      |
|:--------------------------------------------------|:--------------|:--------------|:--------------|
| arquivos                                          | 114           | 114           | 114           |
| CWEs/arquivo (todos)                              | 4.85          | 6.46          | 4.82          |
| CWEs/arquivo (positivos, n=48)                    | 5.17          | 6.62          | 5.1           |
| CWEs/arquivo (negativos, n=66)                    | 4.62          | 6.35          | 4.61          |
| % negativos com >=1 CWE                           | 100.0         | 100.0         | 98.5          |
| % positivos com >=1 CWE                           | 100.0         | 100.0         | 100.0         |
| razao de alarmes (CWEs citadas / 56 issues)       | 9.88          | 13.16         | 9.8           |
| falsos alarmes conhecidos citados / 85 [estrita]  | 36/85 (42.4%) | 33/85 (38.8%) | 30/85 (35.3%) |
| ... so em arquivos negativos [estrita]            | 29/69 (42.0%) | 28/69 (40.6%) | 25/69 (36.2%) |
| issues reais citadas / 56 [estrita]               | 27/56 (48.2%) | 28/56 (50.0%) | 23/56 (41.1%) |
| falsos alarmes conhecidos citados / 85 [leniente] | 61/85 (71.8%) | 57/85 (67.1%) | 57/85 (67.1%) |
| ... so em arquivos negativos [leniente]           | 53/69 (76.8%) | 50/69 (72.5%) | 49/69 (71.0%) |
| issues reais citadas / 56 [leniente]              | 49/56 (87.5%) | 50/56 (89.3%) | 48/56 (85.7%) |
| issues reais detectadas segundo os autores / 56   | 46            | 44            | 45            |

Pares de linhas do gabarito a <= 3 linhas no mesmo arquivo: 5.
