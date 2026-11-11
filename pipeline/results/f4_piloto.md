# F4 - piloto

## 1. Piloto: custo, falhas e exemplos

Arquivos: 10 (5 positivos, 5 negativos). Configuracoes: B0, B1, C1, C2, C3.

| config   |   arquivos |   chamadas/arq |   tokens entrada/arq |   tokens saida/arq |   s de chamada/arq |   falhas |   recusas |
|:---------|-----------:|---------------:|---------------------:|-------------------:|-------------------:|---------:|----------:|
| B0       |         10 |            2   |                 2187 |               1534 |              115   |        0 |         0 |
| B1       |         10 |            1   |                  895 |                100 |                8.5 |        0 |         0 |
| C1       |         10 |            1.5 |                 1954 |                324 |               15.4 |        0 |         0 |
| C2       |         10 |            2   |                 3761 |               1467 |               93.8 |        0 |         0 |
| C3       |         10 |            1.5 |                 1954 |                324 |               15.4 |        0 |         0 |

As chamadas compartilhadas (A1, A3a, A2) contam em todas as configuracoes que as usam; o custo real total e o das etapas unicas (tabela abaixo).

### Chamadas unicas por etapa (cache)

| etapa       |   chamadas unicas |   tokens saida/chamada |   tok/s por requisicao |   s/chamada |   falhas de schema |   chamadas sem sucesso |   recusas |   com repeticao |
|:------------|------------------:|-----------------------:|-----------------------:|------------:|-------------------:|-----------------------:|----------:|----------------:|
| a1          |                10 |                    100 |                   11.7 |         8.5 |                  0 |                      0 |         0 |               0 |
| a2          |                 5 |                   1973 |                   13.3 |       148.6 |                  0 |                      0 |         0 |               0 |
| a3a         |                 5 |                    449 |                   32.6 |        13.7 |                  0 |                      0 |         0 |               0 |
| a3b         |                56 |                   1022 |                   14.1 |        72.5 |                  0 |                      0 |         0 |               5 |
| a3joint     |                 5 |                    761 |                   34.7 |        21.9 |                  0 |                      0 |         0 |               0 |
| b0_extract  |               154 |                    399 |                   11.8 |        33.7 |                  0 |                      1 |         0 |               1 |
| b0_response |                10 |                   1339 |                   13.7 |        97.5 |                  0 |                      0 |         0 |               1 |

Total: 245 chamadas unicas; sem sucesso: 1 (0.4%); falhas de schema: 0; recusas: 0.

A1 (B1): media de achados por arquivo = 0.50 (positivos 0.80, negativos 0.20); respondeu 'nenhuma vulnerabilidade' em 7 de 10 arquivos.

### Descritivo no subconjunto do piloto (so ilustra: amostra pequena)

| config   | issues reais acusados   | falsos alarmes conhecidos acusados   |   achados fora do gabarito | arquivos negativos sinalizados   |
|:---------|:------------------------|:-------------------------------------|---------------------------:|:---------------------------------|
| B0       | 2/9                     | 2/6                                  |                         26 | 5/5                              |
| B1       | 0/9                     | 0/6                                  |                          5 | 1/5                              |
| C1       | 0/9                     | 0/6                                  |                          0 | 0/5                              |
| C2       | 0/9                     | 0/6                                  |                          0 | 0/5                              |
| C3       | 0/9                     | 0/6                                  |                          0 | 0/5                              |

### Exemplos de veredito do A3a (2 de cada tipo)

**confirmed** (0 exemplos)

**refuted** (2 exemplos)
- `v10:File_01` CWE-78 linhas [60, 62] - Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection'). Refutacao tentada: Reviewed the code around lines 60-62. The source is fgets reading from a file, which is untrusted. The sink is atoi(line.param_one), which simply converts a string to an integer. atoi is not an OS command execution function and does not pose an OS command injection risk. The only effect of an invali
- `v10:File_01` CWE-78 linhas [193, 195] - Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection'). Refutacao tentada: Checked the code for any OS command execution (e.g., system(), exec*, popen, etc.). No such calls are present. The only operations performed after parsing are string comparisons and calls to insert/delete/search/print, which are internal functions. Therefore the reported OS Command Injection claim i

**uncertain** (0 exemplos)

## 2. Determinismo (temperature=0, seed=0, repetido com cache novo)

Chamadas comparaveis (mesma entrada nas duas execucoes): 36; respostas identicas: 20 (55.6%). So na 1a execucao: 9; so na 2a: 9 (entradas que dependiam de saidas que mudaram).

| etapa       |   comparaveis |   identicas |   fracao |
|:------------|--------------:|------------:|---------:|
| a1          |            10 |          10 |      1   |
| b0_extract  |             1 |           1 |      1   |
| a2          |             5 |           5 |      1   |
| b0_response |            10 |           1 |      0.1 |
| a3a         |             5 |           2 |      0.4 |
| a3joint     |             5 |           1 |      0.2 |

Conjunto de achados aceitos por arquivo, igual nas duas execucoes:

| config   |   arquivos |   iguais |   fracao |
|:---------|-----------:|---------:|---------:|
| B0       |         10 |        4 |      0.4 |
| B1       |         10 |       10 |      1   |
| C1       |         10 |       10 |      1   |
| C2       |         10 |        9 |      0.9 |
| C3       |         10 |       10 |      1   |

## 3. Validacao do julgamento automatico de correcao (patches do GPT-4.1 do artigo, 56 issues)

Casos julgados: 56 de 56. Rotulo dos autores ('Was issue fixed', GPT-4.1, Tabelas 13/14): 42 corrigidos, 14 nao.

| variante                                                |   n |   acordo |   kappa |   TP |   FP |   FN |   TN |
|:--------------------------------------------------------|----:|---------:|--------:|-----:|-----:|-----:|-----:|
| A3b = valid                                             |  56 |    0.661 |   0.283 |   27 |    4 |   15 |   10 |
| A3b valid ou partial                                    |  56 |    0.768 |   0.422 |   34 |    5 |    8 |    9 |
| A3b valid e criterios 2-4 sem falha (plano)             |  56 |    0.571 |   0.273 |   18 |    0 |   24 |   14 |
| so ferramentas (regra sumiu, compila, sem novo warning) |  56 |    0.482 |   0.134 |   15 |    2 |   27 |   12 |
| todos os patches = corrigido (linha de base)            |  56 |    0.75  |   0     |   42 |   14 |    0 |    0 |

Cobertura dos criterios automaticos (True / False / nao verificavel):

| criterio       |   True |   False |   nao verificavel |
|:---------------|-------:|--------:|------------------:|
| verdict_valid  |     31 |      25 |                 0 |
| rule_gone      |     20 |      20 |                16 |
| compiles       |     20 |       3 |                33 |
| no_new_warning |     49 |       4 |                 3 |

Veredito do A3b x rotulo dos autores:

| verdict   |   corrigido |   nao corrigido |
|:----------|------------:|----------------:|
| invalid   |           8 |               9 |
| partial   |           7 |               1 |
| valid     |          27 |               4 |

Sensibilidade com o rotulo da planilha (onde ha; 56 casos): kappa de 'A3b = valid' = 0.283.

## 4. Calibracao do verificador (A3a sobre achados do scanner: 56 issues reais x 85 falsos alarmes conhecidos)

| classe       |   confirmed |   falha |   refuted |   uncertain |
|:-------------|------------:|--------:|----------:|------------:|
| falso alarme |           4 |       1 |        79 |           1 |
| real         |          22 |       1 |        30 |           3 |

- Sensibilidade (issue real confirmada): 22/56 = 0.39; com 'uncertain' como aceito: 25/56 = 0.45.
- Falso alarme conhecido confirmado: 4/85 = 0.05 (especificidade 0.95); com 'uncertain': 5/85.
- Fisher exato (confirmado: real x falso alarme): p = 2.9e-07.

Issues reais por tipo (rotulo dos autores):

| quality_only                 |   confirmed |   falha |   refuted |   uncertain |
|:-----------------------------|------------:|--------:|----------:|------------:|
| seguranca                    |          22 |       1 |        28 |           3 |
| so qualidade (nao seguranca) |           0 |       0 |         2 |           0 |

## 5. Regra da F6 (linha +-3 + CWE compativel) sobre as respostas do artigo, extraidas em forma estruturada

Concordancia com os rotulos 'detected' dos autores (referencia: kappa >= 0,7):

| modelo   | regra                                    |   n |   acordo |   kappa |   TP |   FP |   FN |   TN |
|:---------|:-----------------------------------------|----:|---------:|--------:|-----:|-----:|-----:|-----:|
| gpt-4.1  | linha +-3 e CWE compativel (regra da F6) |  56 |    0.5   |   0.084 |   21 |    3 |   25 |    7 |
| gpt-4.1  | so linha +-3 (sensibilidade)             |  56 |    0.732 |   0.05  |   39 |    8 |    7 |    2 |
| gpt-5    | linha +-3 e CWE compativel (regra da F6) |  56 |    0.625 |   0.265 |   25 |    2 |   19 |   10 |
| gpt-5    | so linha +-3 (sensibilidade)             |  56 |    0.839 |   0.394 |   43 |    8 |    1 |    4 |
| opus-4.1 | linha +-3 e CWE compativel (regra da F6) |  56 |    0.571 |   0.195 |   23 |    2 |   22 |    9 |
| opus-4.1 | so linha +-3 (sensibilidade)             |  56 |    0.714 |   0.028 |   38 |    9 |    7 |    2 |

Indicadores da configuracao original do artigo no regime estruturado (base de comparacao para a E1):

| modelo   |   arquivos |   extracoes sem sucesso |   achados/arquivo |   achados/arq. negativo | issues reais acusados   | falsos alarmes conhecidos acusados   | arquivos negativos sinalizados   |
|:---------|-----------:|------------------------:|------------------:|------------------------:|:------------------------|:-------------------------------------|:---------------------------------|
| gpt-4.1  |         48 |                       1 |              4.9  |                       0 | 24/56 (autores: 46)     | 3/16                                 | 0/0                              |
| gpt-5    |         48 |                       0 |              6.44 |                       0 | 27/56 (autores: 44)     | 3/16                                 | 0/0                              |
| opus-4.1 |         48 |                       0 |              5.77 |                       0 | 25/56 (autores: 45)     | 4/16                                 | 0/0                              |

## 6. Projecao de horas de GPU (execucao completa)

Piloto: 10 arquivos em 2054 s de parede (todas as configuracoes) -> 205 s/arquivo.

| item                                                            | horas                      |
|:----------------------------------------------------------------|:---------------------------|
| execucao principal (114 arquivos, B0+B1+C1+C2+C3)               | 6.5                        |
| 1 repeticao do estudo de variancia (B1+C3)                      | 1.0                        |
| estudo de variancia (3 repeticoes)                              | 2.9                        |
| principal + variancia                                           | 9.4                        |
| extracao das respostas dos 66 arquivos negativos (E1), estimada | ver etapa paper_extraction |
| cota semanal do Kaggle                                          | 30.0                       |

Carga dos servidores no piloto (s de chamada / paralelismo): detector 6992 s (paralelismo 1), verificador 1060 s (paralelismo 4).
Fracao dos patches do A2 que o C3 usa (confirmados): 1.00.

Estimativa linear: assume que os 114 arquivos se parecem com os 10 do piloto e que a vazao dos servidores nao muda.

## 7. Tempo de sessao

Sessao total: 2.764 h. Etapas: tune_detector=383.5s (ok), pipeline=2054.5s (ok), determinism=1711.8s (ok), fix_validation=1140.2s (ok), paper_extraction=5037.4s (ok)

Detector final: {'kv_cache_type': 'f16', 'num_parallel': 1}.

