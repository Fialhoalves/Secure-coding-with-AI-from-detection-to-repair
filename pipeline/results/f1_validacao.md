# F1 - validacao do gabarito

| # | Verificacao | Resultado | Detalhe |
|---|---|---|---|
| 1 | pastas File_XX | OK | obtido {'v8': 64, 'v10': 51} (Apendice A: 64 e 51) |
| 2 | codigo identico nos 3 modelos | OK |  |
| 3 | linhas da planilha por aba | OK | obtido {'v10': 68, 'v8': 74}, esperado {'v8': 74, 'v10': 68} |
| 4 | issue_id unico | OK |  |
| 5 | nenhum veredito/rotulo ficou sem resolver (celulas ambiguas dos 56 issues vem das Tabelas 13/14) | OK | 2 celulas ambiguas resolvidas pelo artigo; pendentes: [] |
| 6 | toda linha da planilha tem deteccao no Info.txt (exceto a divergente v8:2/14) | OK | sem correspondencia: ['v8:2/14']; ajustes/avisos: [('v8:58/36', 'linha da planilha (22) ausente no Info.txt; usada a unica deteccao de flawfinder (linha 36)'), ('v10:8/7', 'mesma linha no Info.txt, mas o scanner la e diferente do da planilha'), ('v10:8/82', 'mesma linha no Info.txt, mas o scanner la e diferente do da planilha')] |
| 7 | tabelas 13/14 do artigo: 56 issues = lista canonica | OK |  |
| 8 | contadores detectadas/corrigidas do artigo = Apendice A | OK | gpt-4.1/v8=(23, 21); gpt-4.1/v10=(23, 21); gpt-5/v8=(21, 22); gpt-5/v10=(23, 22); opus-4.1/v8=(22, 23); opus-4.1/v10=(23, 20) |
| 9 | (informativo) CWE planilha x artigo: diferencas (a uniao e usada no matcher) | OK | 5: ['v8:49/27', 'v8:53/13', 'v8:62/19', 'v10:3/11', 'v10:3/7'] |
| 10 | (informativo) origem planilha x artigo: conflitos e lacunas (o artigo prevalece) | OK | conflitos ['v10:7/81', 'v10:8/82']; planilha sem origem ['v8:49/9', 'v8:52/42'] |
| 11 | 56 issues reais = lista canonica | OK | 56 |
| 12 | divergente planilha x artigo = [v8:2/14] | OK | ['v8:2/14'] |
| 13 | falsos alarmes conhecidos = 85 | OK | 85 |
| 14 | deteccoes da planilha - divergente = 141 (Tabela 12) | OK | 142 - 1 |
| 15 | classes de arquivo = 48 positivos / 66 negativos / 1 excluido | OK | {'negative': 66, 'positive': 48, 'excluded': 1} |
| 16 | positivos por aba = 24 e 24 | OK | {'v8': 24, 'v10': 24} |
| 17 | (informativo) extensao do codigo vs linguagem da planilha: diferencas listadas | OK | 4 diferem (planilha chama de C++ arquivos .c): [('v8', 40, 'C', 'C++'), ('v8', 41, 'C', 'C++'), ('v8', 42, 'C', 'C++'), ('v8', 43, 'C', 'C++')] |
| 18 | issues nao detectadas por nenhum modelo = Apendice A | OK | ['v10:28/7', 'v10:4/78', 'v10:6/78', 'v8:14/63', 'v8:52/42', 'v8:8/36'] |

## Arquivos por classe

- negative: 66
- positive: 48
- excluded: 1

## Conflitos planilha x artigo (6 celulas)

| issue | modelo | campo | planilha | artigo | tipo | texto da planilha |
|---|---|---|---|---|---|---|
| v8:8/36 | gpt-4.1 | detected | True | False | difere | Yes, unvalidated input identified, CWE-20 for port, but not for wordlist_path |
| v8:8/36 | gpt-5 | detected | True | False | difere | Yes, unvalidated input identified, CWE-20 for port, but not for wordlist_path |
| v8:48/23 | gpt-5 | fixed | None | True | planilha_sem_rotulo_claro | There is attempt to fix it. Special method added to select port name from serial ports whi |
| v8:52/14 | opus-4.1 | fixed | None | True | planilha_sem_rotulo_claro | Buffers still fix sized but there was attempt to fix. Now two separate buffers for receive |
| v10:39/61 | gpt-5 | fixed | True | False | difere | Yes, problem fixed. String size calculated before copy. |
| v10:43/4 | opus-4.1 | fixed | True | False | difere | Yes, function added to sanitize filepath. |
