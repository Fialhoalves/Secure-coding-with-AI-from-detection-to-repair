# F6 + F7 - correspondencia, metricas e estatistica da execucao principal

Repeticao `main` (temperatura 0, seed 0), 114 arquivos (48 positivos, 66 negativos), gabarito: 56 issues reais e 85 falsos alarmes conhecidos. Regra principal: linha +-3 e CWE compativel; 'uncertain' do verificador = rejeitado. IC de 95% por bootstrap por arquivo (2000 replicas).

## F6 - Correspondencia

### Classes dos achados aceitos (F6)

| config   |   dup |   fp_new |   out |   tp_new |   total aceitos |
|:---------|------:|---------:|------:|---------:|----------------:|
| B0       |     8 |       23 |   328 |       15 |             374 |
| B1       |     3 |       13 |   202 |       11 |             229 |
| C1       |     1 |        2 |    16 |        4 |              23 |
| C2       |     0 |        2 |    15 |        4 |              21 |
| C3       |     1 |        2 |    16 |        4 |              23 |

tp_new = primeiro achado sobre um issue real; fp_new = primeiro sobre um falso alarme conhecido; dup = repetido sobre algo ja acusado (fora do numerador e do denominador); out = fora do gabarito (nao julgado, D5).

Aceite da F6: todo achado aceito pertence a uma das classes: **sim**

B0: 106 de 374 achados extraidos (28%) nao tem linha (a resposta de texto livre nao cita) e nao podem casar pela regra estrita; ver a sensibilidade S6.
Falha de extracao do B0 (resposta sem achados por falha do extrator): ['v10:File_14', 'v10:File_20'].

## F7 - Resultado principal (114 arquivos, regra estrita)

Percentuais com IC de 95% [inferior; superior]. Recall = issues reais acusadas / 56; taxa de falsos alarmes conhecidos = locais acusados / 85.

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                 |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:--------------------|
| B0       | 15/56            | 23/85                     | 26.8 [15.1; 39.7] | 27.1 [18.2; 37.0]  | 39.5 [25.0; 54.1]  | 31.9 [19.4; 43.2] | 36.1 [23.1; 47.7] | -0.00 [-0.15; 0.14] |
| B1       | 11/56            | 13/85                     | 19.6 [10.2; 31.3] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 27.5 [14.8; 40.0] | 36.2 [20.5; 50.9] | 0.06 [-0.10; 0.22]  |
| C1       | 4/56             | 2/85                      | 7.1 [1.6; 15.2]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.0; 25.4]  | 25.0 [6.5; 43.8]  | 0.12 [-0.06; 0.26]  |
| C2       | 4/56             | 2/85                      | 7.1 [1.7; 14.6]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.2; 24.6]  | 25.0 [6.7; 42.6]  | 0.12 [-0.06; 0.26]  |
| C3       | 4/56             | 2/85                      | 7.1 [1.6; 15.2]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.0; 25.4]  | 25.0 [6.5; 43.8]  | 0.12 [-0.06; 0.26]  |

### Descritivas (sem julgamento dos achados fora do gabarito)

| config   | file_sensitivity     | neg_files_flagged_frac   | out_per_file_pos   | out_per_file_neg   | findings_per_file   | precision_overall_low   | precision_overall_high   |
|:---------|:---------------------|:-------------------------|:-------------------|:-------------------|:--------------------|:------------------------|:-------------------------|
| B0       | 100.0 [100.0; 100.0] | 93.9 [87.9; 98.6]        | 3.23 [2.74; 3.68]  | 2.62 [2.18; 3.12]  | 3.28 [2.98; 3.60]   | 4.1 [2.2; 6.3]          | 93.7 [91.1; 96.0]        |
| B1       | 83.3 [72.2; 92.9]    | 54.5 [42.0; 67.1]        | 2.23 [1.77; 2.67]  | 1.44 [1.04; 1.83]  | 2.01 [1.68; 2.32]   | 4.9 [2.4; 7.7]          | 94.2 [91.2; 96.9]        |
| C1       | 20.8 [9.8; 32.6]     | 9.1 [3.0; 17.1]          | 0.21 [0.07; 0.38]  | 0.09 [0.01; 0.21]  | 0.20 [0.11; 0.32]   | 18.2 [4.2; 37.5]        | 90.9 [73.7; 100.0]       |
| C2       | 18.8 [8.0; 30.0]     | 7.6 [1.6; 14.7]          | 0.19 [0.04; 0.36]  | 0.09 [0.00; 0.22]  | 0.18 [0.09; 0.30]   | 19.0 [4.3; 40.0]        | 90.5 [72.7; 100.0]       |
| C3       | 20.8 [9.8; 32.6]     | 9.1 [3.0; 17.1]          | 0.21 [0.07; 0.38]  | 0.09 [0.01; 0.21]  | 0.20 [0.11; 0.32]   | 18.2 [4.2; 37.5]        | 90.9 [73.7; 100.0]       |

### Efeito do verificador sobre os achados do A1 (referencia: B1)

| config   | falsos alarmes removidos   |   taxa de remocao | verdadeiros positivos perdidos   |   taxa de perda |   reducao de achados fora do gabarito | mantidos: reais x falsos alarmes   |   Fisher exato (mantem real x falso alarme) |
|:---------|:---------------------------|------------------:|:---------------------------------|----------------:|--------------------------------------:|:-----------------------------------|--------------------------------------------:|
| C1       | 11/13                      |             0.846 | 7/11                             |           0.636 |                                 0.921 | 4/11 x 2/13                        |                                       0.357 |
| C2       | 11/13                      |             0.846 | 7/11                             |           0.636 |                                 0.926 | 4/11 x 2/13                        |                                       0.357 |
| C3       | 11/13                      |             0.846 | 7/11                             |           0.636 |                                 0.921 | 4/11 x 2/13                        |                                       0.357 |

Taxas sobre locais (issues reais e falsos alarmes conhecidos) acusados pelo B1. O teste de Fisher compara a fracao mantida de reais com a de falsos alarmes: mede se o verificador discrimina, alem de apenas rejeitar muito.

### H4: o verificador contra um corte por confianca do detector (curva do B1)

| config   |   taxa de falsos alarmes |   recall |   melhor recall do B1 com taxa <= essa |   recall - curva (p.p.) |
|:---------|-------------------------:|---------:|---------------------------------------:|------------------------:|
| B0       |                    0.271 |    0.268 |                                  0.196 |                     7.1 |
| B1       |                    0.153 |    0.196 |                                  0.196 |                     0   |
| C1       |                    0.024 |    0.071 |                                  0.018 |                     5.4 |
| C2       |                    0.024 |    0.071 |                                  0.018 |                     5.4 |
| C3       |                    0.024 |    0.071 |                                  0.018 |                     5.4 |

Se 'recall - curva' for positivo, a configuracao acusa mais issues reais do que qualquer corte de confianca do B1 com a mesma taxa de falsos alarmes (valor agregador do verificador, H4).

## Comparacoes pareadas

### Comparacoes confirmatorias (H1 a H3), diferenca A - B por arquivo-bootstrap pareado

| hipotese   | A   | B   | recall (A-B, p.p.)   | false_alarm_rate (A-B, p.p.)   | precision (A-B, p.p.)   | f1 (A-B, p.p.)      |
|:-----------|:----|:----|:---------------------|:-------------------------------|:------------------------|:--------------------|
| H1         | C3  | B1  | -12.5 [-22.0; -4.7]  | -12.9 [-20.5; -6.1]            | +20.8 [-18.4; +58.6]    | -14.6 [-26.0; -4.1] |
| H2         | B1  | B0  | -7.1 [-20.0; +4.9]   | -11.8 [-20.2; -3.7]            | +6.4 [-10.3; +22.8]     | -4.4 [-18.0; +9.1]  |
| H3         | C3  | C2  | +0.0 [-5.7; +5.1]    | +0.0 [+0.0; +0.0]              | +0.0 [-25.0; +21.4]     | +0.0 [-9.3; +8.5]   |

H1 (C3 x B1): taxa de falsos alarmes conhecidos -12.9 p.p. (IC -20.5 a -6.1); recall -12.5 p.p. (IC -22.0 a -4.7). Criterio da H1: reducao dos falsos alarmes com perda de recall de no maximo 5 p.p.: reducao com IC abaixo de zero; perda pontual MAIOR que 5 p.p. (limite inferior do IC do recall: -22.0 p.p.).

### Todas as comparacoes (confirmatorias: H1 = C3 x B1, H2 = B1 x B0, H3 = C3 x C2; as demais sao exploratorias)

**detecao de issues reais (56)** - Q de Cochran = 28.43 (gl 4), p = 1.019e-05. McNemar exato par a par, com Holm:

| par     |   so_a |   so_b |      p |   p_Holm |
|:--------|-------:|-------:|-------:|---------:|
| B0 x B1 |      8 |      4 | 0.3877 |   1      |
| B0 x C1 |     12 |      1 | 0.0034 |   0.0308 |
| B0 x C2 |     11 |      0 | 0.001  |   0.0098 |
| B0 x C3 |     12 |      1 | 0.0034 |   0.0308 |
| B1 x C1 |      7 |      0 | 0.0156 |   0.1094 |
| B1 x C2 |      7 |      0 | 0.0156 |   0.1094 |
| B1 x C3 |      7 |      0 | 0.0156 |   0.1094 |
| C1 x C2 |      1 |      1 | 1      |   1      |
| C1 x C3 |      0 |      0 | 1      |   1      |
| C2 x C3 |      1 |      1 | 1      |   1      |

**acusacao de falsos alarmes conhecidos (85)** - Q de Cochran = 64.95 (gl 4), p = 2.642e-13. McNemar exato par a par, com Holm:

| par     |   so_a |   so_b |      p |   p_Holm |
|:--------|-------:|-------:|-------:|---------:|
| B0 x B1 |     12 |      2 | 0.0129 |   0.0518 |
| B0 x C1 |     21 |      0 | 0      |   0      |
| B0 x C2 |     21 |      0 | 0      |   0      |
| B0 x C3 |     21 |      0 | 0      |   0      |
| B1 x C1 |     11 |      0 | 0.001  |   0.0068 |
| B1 x C2 |     11 |      0 | 0.001  |   0.0068 |
| B1 x C3 |     11 |      0 | 0.001  |   0.0068 |
| C1 x C2 |      0 |      0 | 1      |   1      |
| C1 x C3 |      0 |      0 | 1      |   1      |
| C2 x C3 |      0 |      0 | 1      |   1      |

## Correcao (secundaria; limitacao: kappa do A3b contra 'Was issue fixed' = 0,28)

| config   |   accused |   with_patch |   fixed_combined |   fix_rate_conditional |   fix_rate_global |   verdict_valid_true |   verdict_valid_false |   verdict_valid_na |   rule_gone_true |   rule_gone_false |   rule_gone_na |   compiles_true |   compiles_false |   compiles_na |   no_new_warning_true |   no_new_warning_false |   no_new_warning_na |   patches desnecessarios |
|:---------|----------:|-------------:|-----------------:|-----------------------:|------------------:|---------------------:|----------------------:|-------------------:|-----------------:|------------------:|---------------:|----------------:|-----------------:|--------------:|----------------------:|-----------------------:|--------------------:|-------------------------:|
| C2       |         4 |            4 |                0 |                      0 |                 0 |                    1 |                     3 |                  0 |                2 |                 2 |              0 |               0 |                1 |             3 |                     3 |                      1 |                   0 |                       14 |
| C3       |         4 |            4 |                0 |                      0 |                 0 |                    1 |                     3 |                  0 |                2 |                 2 |              0 |               0 |                2 |             2 |                     3 |                      1 |                   0 |                        2 |

| config              |   accused |   rule_gone_true |   rule_gone_false |   rule_gone_na |   compiles_true |   compiles_false |   compiles_na |   no_new_warning_true |   no_new_warning_false |   no_new_warning_na |
|:--------------------|----------:|-----------------:|------------------:|---------------:|----------------:|-----------------:|--------------:|----------------------:|-----------------------:|--------------------:|
| B0 (so ferramentas) |        15 |                3 |                 9 |              3 |               4 |                1 |            10 |                    13 |                      1 |                   1 |

B0 (linha acima): so os criterios 2-4 das ferramentas, sobre o patch do arquivo inteiro.

### B0 com o A3b nos patches do B0 (o patch e o ultimo bloco de codigo da resposta; um por arquivo, usado para todos os achados do arquivo)

| B0 + A3b                    |   accused |   with_patch |   fixed_combined |   fix_rate_conditional |   fix_rate_global |   verdict_valid_true |   verdict_valid_false |   verdict_valid_na |   rule_gone_true |   rule_gone_false |   rule_gone_na |   compiles_true |   compiles_false |   compiles_na |   no_new_warning_true |   no_new_warning_false |   no_new_warning_na | vereditos do A3b nos achados que casam com issue real   |
|:----------------------------|----------:|-------------:|-----------------:|-----------------------:|------------------:|---------------------:|----------------------:|-------------------:|-----------------:|------------------:|---------------:|----------------:|-----------------:|--------------:|----------------------:|-----------------------:|--------------------:|:--------------------------------------------------------|
| regra estrita               |        15 |           15 |                3 |                  0.2   |             0.054 |                    5 |                    10 |                  0 |                3 |                 9 |              3 |               4 |                1 |            10 |                    13 |                      1 |                   1 | invalid: 7, partial: 5, valid: 5                        |
| so linha ±3 (sensibilidade) |        38 |           38 |               10 |                  0.263 |             0.179 |                   19 |                    19 |                  0 |                5 |                20 |             13 |              11 |                3 |            24 |                    34 |                      1 |                   3 | invalid: 25, partial: 14, valid: 25                     |

Julgamentos do A3b: 373 achados do B0 (invalid: 185, partial: 47, valid: 141); arquivos sem julgamento (sem patch ou sem achados extraidos): 5. A taxa condicional usa as issues reais acusadas pelo B0; `valid` do A3b so e valido com os criterios das ferramentas (a regra do scanner sumiu, compila, sem aviso novo). O A3b tem kappa baixo contra 'Was issue fixed' (0,28): leitura secundaria.

## Custo computacional (cada configuracao contada sozinha; o A1 e o A3a compartilhados contam em todas que os usam)

| config   |   chamadas/arq |   tokens entrada/arq |   tokens saida/arq |   s de chamada/arq |   tokens totais por issue real acusado |
|:---------|---------------:|---------------------:|-------------------:|-------------------:|---------------------------------------:|
| B0       |            2   |                 3294 |               2447 |              158.2 |                                  43632 |
| B1       |            1   |                 1193 |                353 |               23.1 |                                  16020 |
| C1       |            3   |                 4090 |               1373 |               53.7 |                                 155689 |
| C2       |            5   |                 8133 |               3944 |              197.4 |                                 344205 |
| C3       |            3.4 |                 4883 |               1728 |               71.8 |                                 188415 |

## Analises de sensibilidade (mesmas metricas, IC por arquivo)

### S1 so linha +-3 (sem checar CWE) (114 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B0       | 38/56            | 38/85                     | 67.9 [53.7; 81.6] | 44.7 [34.9; 55.7]  | 50.0 [39.0; 61.0]  | 57.6 [46.8; 67.1] | 52.8 [42.1; 63.0] | 0.23 [0.05; 0.39]  |
| B1       | 31/56            | 29/85                     | 55.4 [41.7; 67.9] | 34.1 [24.4; 44.2]  | 51.7 [38.2; 64.3]  | 53.4 [41.2; 63.4] | 52.4 [39.4; 63.6] | 0.21 [0.04; 0.37]  |
| C1       | 5/56             | 3/85                      | 8.9 [1.8; 17.5]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.3; 28.6]  | 28.4 [7.2; 46.4]  | 0.11 [-0.06; 0.27] |
| C2       | 5/56             | 3/85                      | 8.9 [2.0; 17.3]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.7; 28.1]  | 28.4 [7.4; 46.4]  | 0.11 [-0.07; 0.27] |
| C3       | 5/56             | 3/85                      | 8.9 [1.8; 17.5]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.3; 28.6]  | 28.4 [7.2; 46.4]  | 0.11 [-0.06; 0.27] |

### S2 'uncertain' do verificador aceito (114 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                 |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:--------------------|
| B0       | 15/56            | 23/85                     | 26.8 [15.1; 39.7] | 27.1 [18.2; 37.0]  | 39.5 [25.0; 54.1]  | 31.9 [19.4; 43.2] | 36.1 [23.1; 47.7] | -0.00 [-0.15; 0.14] |
| B1       | 11/56            | 13/85                     | 19.6 [10.2; 31.3] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 27.5 [14.8; 40.0] | 36.2 [20.5; 50.9] | 0.06 [-0.10; 0.22]  |
| C1       | 5/56             | 2/85                      | 8.9 [2.1; 17.6]   | 2.4 [0.0; 6.2]     | 71.4 [33.3; 100.0] | 15.9 [3.8; 29.0]  | 29.8 [8.6; 47.6]  | 0.15 [-0.02; 0.29]  |
| C2       | 4/56             | 2/85                      | 7.1 [1.7; 14.6]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.2; 24.6]  | 25.0 [6.7; 42.6]  | 0.12 [-0.06; 0.26]  |
| C3       | 5/56             | 2/85                      | 8.9 [2.1; 17.6]   | 2.4 [0.0; 6.2]     | 71.4 [33.3; 100.0] | 15.9 [3.8; 29.0]  | 29.8 [8.6; 47.6]  | 0.15 [-0.02; 0.29]  |

### S3 recorte so seguranca (sem CWE-561/1164) (114 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B0       | 15/54            | 23/85                     | 27.8 [15.7; 41.5] | 27.1 [18.2; 37.0]  | 39.5 [25.0; 54.1]  | 32.6 [19.8; 44.7] | 36.4 [23.3; 48.2] | 0.01 [-0.14; 0.16] |
| B1       | 11/54            | 13/85                     | 20.4 [10.3; 32.2] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 28.2 [15.2; 41.1] | 36.7 [20.7; 51.3] | 0.07 [-0.09; 0.23] |
| C1       | 4/54             | 2/85                      | 7.4 [1.7; 15.8]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 13.3 [3.2; 26.4]  | 25.6 [6.6; 44.3]  | 0.12 [-0.06; 0.27] |
| C2       | 4/54             | 2/85                      | 7.4 [1.7; 15.4]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 13.3 [3.3; 25.5]  | 25.6 [6.8; 43.5]  | 0.12 [-0.06; 0.27] |
| C3       | 4/54             | 2/85                      | 7.4 [1.7; 15.8]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 13.3 [3.2; 26.4]  | 25.6 [6.6; 44.3]  | 0.12 [-0.06; 0.27] |

### S4 104 arquivos fora do piloto (104 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B0       | 12/47            | 20/79                     | 25.5 [13.0; 40.0] | 25.3 [16.5; 34.5]  | 37.5 [21.2; 53.7]  | 30.4 [16.7; 43.2] | 34.3 [19.1; 48.1] | 0.00 [-0.16; 0.18] |
| B1       | 9/47             | 11/79                     | 19.1 [8.5; 31.8]  | 13.9 [6.9; 21.8]   | 45.0 [23.1; 66.7]  | 26.9 [12.5; 41.1] | 35.4 [17.5; 52.2] | 0.07 [-0.10; 0.25] |
| C1       | 4/47             | 2/79                      | 8.5 [2.0; 17.9]   | 2.5 [0.0; 6.6]     | 66.7 [25.0; 100.0] | 15.1 [3.7; 29.1]  | 28.2 [7.8; 47.9]  | 0.14 [-0.05; 0.30] |
| C2       | 4/47             | 2/79                      | 8.5 [1.9; 17.1]   | 2.5 [0.0; 6.6]     | 66.7 [20.0; 100.0] | 15.1 [3.6; 28.6]  | 28.2 [7.5; 47.6]  | 0.14 [-0.06; 0.30] |
| C3       | 4/47             | 2/79                      | 8.5 [2.0; 17.9]   | 2.5 [0.0; 6.6]     | 66.7 [25.0; 100.0] | 15.1 [3.7; 29.1]  | 28.2 [7.8; 47.9]  | 0.14 [-0.05; 0.30] |

### S5 sem os 2 arquivos do B0 com extracao falha (112 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                 |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:--------------------|
| B0       | 15/56            | 23/83                     | 26.8 [15.8; 38.8] | 27.7 [18.5; 37.3]  | 39.5 [25.0; 54.3]  | 31.9 [20.2; 43.1] | 36.1 [23.3; 48.5] | -0.01 [-0.16; 0.15] |
| B1       | 11/56            | 13/83                     | 19.6 [10.0; 31.1] | 15.7 [8.2; 23.8]   | 45.8 [26.3; 65.3]  | 27.5 [14.6; 40.5] | 36.2 [20.4; 50.8] | 0.05 [-0.11; 0.22]  |
| C1       | 4/56             | 2/83                      | 7.1 [1.6; 15.1]   | 2.4 [0.0; 6.2]     | 66.7 [20.0; 100.0] | 12.9 [3.1; 25.4]  | 25.0 [6.7; 44.3]  | 0.11 [-0.07; 0.28]  |
| C2       | 4/56             | 2/83                      | 7.1 [1.7; 15.0]   | 2.4 [0.0; 6.2]     | 66.7 [22.2; 100.0] | 12.9 [3.2; 25.5]  | 25.0 [6.8; 43.8]  | 0.11 [-0.07; 0.27]  |
| C3       | 4/56             | 2/83                      | 7.1 [1.6; 15.1]   | 2.4 [0.0; 6.2]     | 66.7 [20.0; 100.0] | 12.9 [3.1; 25.4]  | 25.0 [6.7; 44.3]  | 0.11 [-0.07; 0.28]  |

### S6 (exploratoria) arquivo + CWE, sem exigir linha (114 arquivos)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B0       | 24/56            | 34/85                     | 42.9 [29.2; 57.1] | 40.0 [29.8; 50.6]  | 41.4 [28.6; 54.4]  | 42.1 [29.6; 53.1] | 41.7 [29.3; 53.2] | 0.03 [-0.14; 0.19] |
| B1       | 16/56            | 20/85                     | 28.6 [16.7; 41.5] | 23.5 [15.0; 32.6]  | 44.4 [27.3; 61.1]  | 34.8 [21.4; 47.7] | 40.0 [24.8; 53.8] | 0.06 [-0.11; 0.23] |
| C1       | 5/56             | 4/85                      | 8.9 [1.9; 17.8]   | 4.7 [1.1; 9.8]     | 55.6 [20.0; 88.9]  | 15.4 [3.5; 28.6]  | 27.2 [7.2; 44.6]  | 0.08 [-0.09; 0.24] |
| C2       | 5/56             | 3/85                      | 8.9 [1.9; 17.5]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.6; 28.6]  | 28.4 [7.7; 45.9]  | 0.11 [-0.06; 0.27] |
| C3       | 5/56             | 4/85                      | 8.9 [1.9; 17.8]   | 4.7 [1.1; 9.8]     | 55.6 [20.0; 88.9]  | 15.4 [3.5; 28.6]  | 27.2 [7.2; 44.6]  | 0.08 [-0.09; 0.24] |

## E1 (exploratoria): pipeline com modelos abertos x respostas originais do artigo, no mesmo regime estruturado

Arquivos em comum: 114 (48 positivos, 66 negativos).
Respostas do artigo com extracao sem sucesso: GPT-4.1 (artigo): 1; GPT-5 (artigo): 0; Opus 4.1 (artigo): 0.
Diferencas importantes: os modelos do artigo sao outros (comerciais, maiores); as respostas do artigo foram escritas para o prompt original, sem linhas obrigatorias, e a extracao feita por um modelo de 14B pode errar; a regra da F6 teve kappa baixo contra os rotulos dos autores. Por isso a comparacao e exploratoria e so vale no mesmo regime.

### regra estrita (linha ±3 e CWE compativel)

| config            | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                 |
|:------------------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:--------------------|
| B0 (abertos)      | 15/56            | 23/85                     | 26.8 [15.1; 39.7] | 27.1 [18.2; 37.0]  | 39.5 [25.0; 54.1]  | 31.9 [19.4; 43.2] | 36.1 [23.1; 47.7] | -0.00 [-0.15; 0.14] |
| B1 (abertos)      | 11/56            | 13/85                     | 19.6 [10.2; 31.3] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 27.5 [14.8; 40.0] | 36.2 [20.5; 50.9] | 0.06 [-0.10; 0.22]  |
| C3 (abertos)      | 4/56             | 2/85                      | 7.1 [1.6; 15.2]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.0; 25.4]  | 25.0 [6.5; 43.8]  | 0.12 [-0.06; 0.26]  |
| GPT-4.1 (artigo)  | 24/56            | 27/85                     | 42.9 [30.6; 55.7] | 31.8 [21.7; 41.7]  | 47.1 [32.7; 61.5]  | 44.9 [32.3; 55.9] | 46.2 [32.9; 58.8] | 0.11 [-0.06; 0.29]  |
| GPT-5 (artigo)    | 27/56            | 24/85                     | 48.2 [34.8; 62.2] | 28.2 [19.0; 38.5]  | 52.9 [38.6; 66.7]  | 50.5 [38.1; 61.5] | 51.9 [39.0; 63.8] | 0.20 [0.03; 0.37]   |
| Opus 4.1 (artigo) | 25/56            | 28/85                     | 44.6 [31.5; 56.8] | 32.9 [23.3; 43.0]  | 47.2 [33.3; 60.3]  | 45.9 [33.3; 55.9] | 46.6 [33.2; 57.8] | 0.12 [-0.04; 0.27]  |

Diferenca pareada por arquivo (regra estrita), C3 menos cada modelo do artigo:

| comparacao                       | recall (p.p.)        | false_alarm_rate (p.p.)   | precision (p.p.)     |
|:---------------------------------|:---------------------|:--------------------------|:---------------------|
| C3 (abertos) - GPT-4.1 (artigo)  | -35.7 [-49.0; -22.2] | -29.4 [-39.1; -19.3]      | +19.6 [-24.0; +57.4] |
| C3 (abertos) - GPT-5 (artigo)    | -41.1 [-54.8; -28.0] | -25.9 [-35.9; -17.2]      | +13.7 [-29.8; +51.0] |
| C3 (abertos) - Opus 4.1 (artigo) | -37.5 [-50.0; -23.9] | -30.6 [-40.5; -20.9]      | +19.5 [-23.3; +56.3] |

### so linha ±3 (sensibilidade)

| config            | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:------------------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B0 (abertos)      | 38/56            | 38/85                     | 67.9 [53.7; 81.6] | 44.7 [34.9; 55.7]  | 50.0 [39.0; 61.0]  | 57.6 [46.8; 67.1] | 52.8 [42.1; 63.0] | 0.23 [0.05; 0.39]  |
| B1 (abertos)      | 31/56            | 29/85                     | 55.4 [41.7; 67.9] | 34.1 [24.4; 44.2]  | 51.7 [38.2; 64.3]  | 53.4 [41.2; 63.4] | 52.4 [39.4; 63.6] | 0.21 [0.04; 0.37]  |
| C3 (abertos)      | 5/56             | 3/85                      | 8.9 [1.8; 17.5]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.3; 28.6]  | 28.4 [7.2; 46.4]  | 0.11 [-0.06; 0.27] |
| GPT-4.1 (artigo)  | 47/56            | 51/85                     | 83.9 [72.7; 93.5] | 60.0 [49.4; 70.5]  | 48.0 [37.5; 58.2]  | 61.0 [51.2; 69.9] | 52.5 [42.0; 62.2] | 0.25 [0.10; 0.40]  |
| GPT-5 (artigo)    | 51/56            | 57/85                     | 91.1 [81.5; 98.3] | 67.1 [56.7; 77.1]  | 47.2 [37.6; 56.8]  | 62.2 [52.6; 70.5] | 52.3 [42.4; 61.5] | 0.28 [0.12; 0.42]  |
| Opus 4.1 (artigo) | 47/56            | 48/85                     | 83.9 [72.5; 93.8] | 56.5 [46.5; 67.5]  | 49.5 [39.2; 59.4]  | 62.3 [51.7; 71.0] | 53.9 [43.5; 63.5] | 0.29 [0.12; 0.42]  |

## Estudo de variancia (B1 e C3, repeticoes com amostragem)

Repeticoes disponiveis: var1, var2, var3 (seeds 1 a 3, temperatura do cartao: detector 0,7; verificador 1,0).

| repeticao   | config   |   arquivos | recall        | falsos alarmes conhecidos   | precisao   | F1    |   MCC |   achados aceitos | arquivos negativos sinalizados   |
|:------------|:---------|-----------:|:--------------|:----------------------------|:-----------|:------|------:|------------------:|:---------------------------------|
| var1        | B1       |        114 | 12.5% (7/56)  | 14.1% (12/85)               | 36.8%      | 18.7% | -0.02 |               229 | 54.5%                            |
| var1        | C3       |        114 | 5.4% (3/56)   | 2.4% (2/85)                 | 60.0%      | 9.8%  |  0.08 |                27 | 12.1%                            |
| var2        | B1       |        114 | 14.3% (8/56)  | 17.6% (15/85)               | 34.8%      | 20.3% | -0.04 |               270 | 57.6%                            |
| var2        | C3       |        114 | 1.8% (1/56)   | 4.7% (4/85)                 | 20.0%      | 3.3%  | -0.08 |                28 | 13.6%                            |
| var3        | B1       |        114 | 17.9% (10/56) | 15.3% (13/85)               | 43.5%      | 25.3% |  0.03 |               243 | 50.0%                            |
| var3        | C3       |        114 | 7.1% (4/56)   | 3.5% (3/85)                 | 57.1%      | 12.7% |  0.08 |                26 | 12.1%                            |

### Media ± desvio-padrao nas repeticoes (n pequeno: o desvio e uma estimativa grosseira)

| config   |   repeticoes | recall          | false_alarm_rate   | precision        | f1              | f05             | mcc          | referencia (T=0, principal): recall; falsos alarmes   |
|:---------|-------------:|:----------------|:-------------------|:-----------------|:----------------|:----------------|:-------------|:------------------------------------------------------|
| B1       |            3 | 14.9 ± 2.7 p.p. | 15.7 ± 1.8 p.p.    | 38.4 ± 4.5 p.p.  | 21.4 ± 3.5 p.p. | 29.1 ± 4.1 p.p. | -0.01 ± 0.04 | 19.6%; 15.3%                                          |
| C3       |            3 | 4.8 ± 2.7 p.p.  | 3.5 ± 1.2 p.p.     | 45.7 ± 22.3 p.p. | 8.6 ± 4.8 p.p.  | 16.7 ± 9.0 p.p. | 0.03 ± 0.09  | 7.1%; 2.4%                                            |

### H1 refeita em cada repeticao (C3 - B1, bootstrap pareado por arquivo)

| repeticao   | recall (C3-B1, p.p.)   | falsos alarmes (C3-B1, p.p.)   | precisao (C3-B1, p.p.)   | queda de falsos alarmes com IC < 0   | perda de recall <= 5 p.p. (pontual)   |
|:------------|:-----------------------|:-------------------------------|:-------------------------|:-------------------------------------|:--------------------------------------|
| var1        | -7.1 [-14.3; -1.6]     | -11.8 [-18.8; -5.3]            | +23.2 [-21.1; +69.2]     | sim                                  | nao                                   |
| var2        | -12.5 [-22.2; -4.8]    | -12.9 [-20.2; -6.1]            | -14.8 [-47.4; +26.7]     | sim                                  | nao                                   |
| var3        | -10.7 [-19.4; -3.4]    | -11.8 [-19.0; -5.1]            | +13.7 [-20.3; +48.2]     | sim                                  | nao                                   |

Criterio da H1 (queda dos falsos alarmes e perda de recall de no maximo 5 p.p.) cumprido em 0 de 3 repeticoes.

## H5 (exploratoria): verificador de outra familia (C3, gpt-oss) x da mesma familia do detector (C3-mf, qwen)

Arquivos: 114 (48 positivos, 66 negativos).
Achados do A1 identicos aos do C3 em 114 de 114 arquivos.
No C3 o verificador (A3a) e o juiz da correcao (A3b) sao o `gpt-oss:20b`; no C3-mf sao o `qwen2.5-coder:14b`, o mesmo modelo do detector. O corretor (A2) e o `qwen` nos dois. Aceito = veredito `confirmed`.

### regra estrita (linha ±3 e CWE compativel)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B1       | 11/56            | 13/85                     | 19.6 [10.2; 31.3] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 27.5 [14.8; 40.0] | 36.2 [20.5; 50.9] | 0.06 [-0.10; 0.22] |
| C3       | 4/56             | 2/85                      | 7.1 [1.6; 15.2]   | 2.4 [0.0; 6.2]     | 66.7 [25.0; 100.0] | 12.9 [3.0; 25.4]  | 25.0 [6.5; 43.8]  | 0.12 [-0.06; 0.26] |
| C3mf     | 0/56             | 0/85                      | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]     | n/d                | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]    | n/d                |

### so linha ±3 (sensibilidade)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B1       | 31/56            | 29/85                     | 55.4 [41.7; 67.9] | 34.1 [24.4; 44.2]  | 51.7 [38.2; 64.3]  | 53.4 [41.2; 63.4] | 52.4 [39.4; 63.6] | 0.21 [0.04; 0.37]  |
| C3       | 5/56             | 3/85                      | 8.9 [1.8; 17.5]   | 3.5 [0.0; 7.8]     | 62.5 [25.0; 100.0] | 15.6 [3.3; 28.6]  | 28.4 [7.2; 46.4]  | 0.11 [-0.06; 0.27] |
| C3mf     | 0/56             | 0/85                      | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]     | n/d                | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]    | n/d                |

### 'uncertain' aceito (sensibilidade S2)

| config   | acusados reais   | falsos alarmes acusados   | recall            | false_alarm_rate   | precision          | f1                | f05               | mcc                |
|:---------|:-----------------|:--------------------------|:------------------|:-------------------|:-------------------|:------------------|:------------------|:-------------------|
| B1       | 11/56            | 13/85                     | 19.6 [10.2; 31.3] | 15.3 [8.0; 23.5]   | 45.8 [26.3; 65.5]  | 27.5 [14.8; 40.0] | 36.2 [20.5; 50.9] | 0.06 [-0.10; 0.22] |
| C3       | 5/56             | 2/85                      | 8.9 [2.1; 17.6]   | 2.4 [0.0; 6.2]     | 71.4 [33.3; 100.0] | 15.9 [3.8; 29.0]  | 29.8 [8.6; 47.6]  | 0.15 [-0.02; 0.29] |
| C3mf     | 0/56             | 0/85                      | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]     | n/d                | 0.0 [0.0; 0.0]    | 0.0 [0.0; 0.0]    | n/d                |

### Diferenca pareada por arquivo (regra estrita; bootstrap por arquivo, IC de 95%)

| comparacao   | recall (p.p.)        | false_alarm_rate (p.p.)   | precision (p.p.)     |
|:-------------|:---------------------|:--------------------------|:---------------------|
| C3 - C3mf    | +7.1 [+1.6; +15.2]   | +2.4 [+0.0; +6.2]         | n/d                  |
| C3mf - B1    | -19.6 [-31.3; -10.2] | -15.3 [-23.5; -8.0]       | n/d                  |
| C3 - B1      | -12.5 [-22.0; -4.7]  | -12.9 [-20.5; -6.1]       | +20.8 [-18.4; +58.6] |

### McNemar exato por local, C3 x C3-mf (regra estrita; exploratorio, sem correcao de Holm)

| locais                         |   so no C3 |   so no C3-mf |   p (McNemar exato) |
|:-------------------------------|-----------:|--------------:|--------------------:|
| issues reais (56)              |          4 |             0 |               0.125 |
| falsos alarmes conhecidos (85) |          2 |             0 |               0.5   |

### Vereditos do A3a sobre os achados do A1 ('None' = veredito ausente por falha)

| config   |   achados do A1 | confirmed   | refuted    | uncertain   | None   |
|:---------|----------------:|:------------|:-----------|:------------|:-------|
| C3       |             229 | 23 (10%)    | 200 (87%)  | 6 (3%)      | 0 (0%) |
| C3mf     |             229 | 0 (0%)      | 229 (100%) | 0 (0%)      | 0 (0%) |

### Efeito de cada verificador sobre os achados do A1 (referencia: B1; regra estrita)

| config   | falsos alarmes removidos   |   taxa de remocao | verdadeiros positivos perdidos   |   taxa de perda |   reducao de achados fora do gabarito | mantidos: reais x falsos alarmes   |   Fisher exato (mantem real x falso alarme) |
|:---------|:---------------------------|------------------:|:---------------------------------|----------------:|--------------------------------------:|:-----------------------------------|--------------------------------------------:|
| C3       | 11/13                      |             0.846 | 7/11                             |           0.636 |                                 0.921 | 4/11 x 2/13                        |                                       0.357 |
| C3mf     | 13/13                      |             1     | 11/11                            |           1     |                                 1     | 0/11 x 0/13                        |                                       1     |

Taxas sobre locais (issues reais e falsos alarmes conhecidos) acusados pelo B1. O teste de Fisher compara a fracao mantida de reais com a de falsos alarmes: mede se o verificador discrimina, alem de apenas rejeitar muito.

### Correcao (secundaria; kappa do A3b contra 'Was issue fixed' = 0,28)

| config   |   accused |   with_patch |   fixed_combined |   fix_rate_conditional |   fix_rate_global |   verdict_valid_true |   verdict_valid_false |   verdict_valid_na |   rule_gone_true |   rule_gone_false |   rule_gone_na |   compiles_true |   compiles_false |   compiles_na |   no_new_warning_true |   no_new_warning_false |   no_new_warning_na |   patches desnecessarios |
|:---------|----------:|-------------:|-----------------:|-----------------------:|------------------:|---------------------:|----------------------:|-------------------:|-----------------:|------------------:|---------------:|----------------:|-----------------:|--------------:|----------------------:|-----------------------:|--------------------:|-------------------------:|
| C3       |         4 |            4 |                0 |                      0 |                 0 |                    1 |                     3 |                  0 |                2 |                 2 |              0 |               0 |                2 |             2 |                     3 |                      1 |                   0 |                        2 |
| C3mf     |         0 |            0 |                0 |                    nan |                 0 |                    0 |                     0 |                  0 |                0 |                 0 |              0 |               0 |                0 |             0 |                     0 |                      0 |                   0 |                        0 |

### Custo (A1 e A2 vindos do cache semeado contam com o tempo e os tokens da execucao original)

| config   |   chamadas/arq |   tokens entrada/arq |   tokens saida/arq |   s de chamada/arq |
|:---------|---------------:|---------------------:|-------------------:|-------------------:|
| C3       |            3.4 |                 4883 |               1728 |               71.8 |
| C3mf     |            3   |                 4069 |                626 |               46.8 |

Sintese mecanica (criterio fixado antes do resultado): **H5 nao apoiada**: o IC pareado da diferenca de falsos alarmes (C3 - C3-mf) inclui 0. Falsos alarmes conhecidos C3 - C3-mf = +2.4 p.p. (IC +0.0 a +6.2); recall +7.1 p.p. (IC +1.6 a +15.2); precisao n/d (o C3-mf nao aceita nenhum achado: precisao indefinida). Exploratoria: nao entra na familia com Holm.

