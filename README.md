# Verificação adversarial com 3 agentes para reduzir falsos positivos na detecção de vulnerabilidades

> **Projeto derivado de um artigo.** Este repositório é um trabalho acadêmico construído a partir do artigo *Secure coding with AI – from detection to repair*, de Vladislav Belozerov, Peter J. Barclay e Ashkan Sami ([Empirical Software Engineering 31:93, 2026](https://link.springer.com/article/10.1007/s10664-026-10812-8)). Os dados e os rótulos que usamos são dos autores; a auditoria, o pipeline e as conclusões são nossos. Veja [Origem do projeto](#origem-do-projeto) e [Créditos e licenças de terceiros](#créditos-e-licenças-de-terceiros).

Projeto da disciplina TAES (Centro de Informática, UFPE, 2026). O trabalho tem duas partes:

1. **Auditoria** do artigo Belozerov, Barclay e Sami, *Secure coding with AI – from detection to repair*, Empirical Software Engineering 31:93 (2026), recalculando os números a partir dos dados publicados pelos autores.
2. **Experimento**: um pipeline de 3 papéis (A1 detector, A2 corretor, A3 verificador adversarial) que roda só com modelos abertos e gratuitos (`qwen2.5-coder:14b` e `gpt-oss:20b`, em GPUs gratuitas do Kaggle). Ele é avaliado em **precisão e recall** usando apenas os rótulos dos próprios autores: 56 issues reais e 85 falsos alarmes conhecidos.

**Resultado principal.** O verificador remove 85% dos falsos alarmes conhecidos que o detector acusava, mas também 64% das issues reais. A taxa de falsos alarmes cai de 15,3% para 2,4%, e o recall cai de 19,6% para 7,1%. A hipótese principal (H1: reduzir falsos alarmes perdendo no máximo 5 p.p. de recall) não foi confirmada, nem nas 3 repetições do estudo de variância. O verificador muda o ponto de operação, mas não separa melhor o real do falso.

| Documento | Onde |
|---|---|
| Relatório final | [`relatorio/RELATORIO.pdf`](relatorio/RELATORIO.pdf) ([fonte em Markdown](relatorio/RELATORIO.md)) |
| Resumo do projeto (material de estudo do grupo, 14 páginas) | [`Resumo_do_projeto.pdf`](Resumo_do_projeto.pdf) |
| Slides e guia da apresentação | [`apresentacao/`](apresentacao/) |
| Plano do experimento (hipóteses, desenho, métricas) | [`PLANO_EXECUCAO.md`](PLANO_EXECUCAO.md) |
| Diário de execução (cada decisão, hash dos prompts, horas de GPU) | [`pipeline/DIARIO.md`](pipeline/DIARIO.md) |
| Auditoria do artigo | [`pipeline/results/auditoria_artigo.md`](pipeline/results/auditoria_artigo.md) |
| Todas as métricas e testes | [`pipeline/results/f7_resultados.md`](pipeline/results/f7_resultados.md) |

## Origem do projeto

Este projeto é **derivado** do artigo de Belozerov, Barclay e Sami ([DOI](https://doi.org/10.1007/s10664-026-10812-8)), que avaliou se LLMs (GPT-4.1, GPT-5 e Claude Opus 4.1) detectam e corrigem vulnerabilidades em código C, C++ e C# vindo de conversas reais de desenvolvedores com o ChatGPT. Os autores publicaram os dados do estudo, e foi isso que permitiu o nosso trabalho. Não temos vínculo com os autores, e eles não revisaram nem endossam este repositório.

| Vem do artigo e dos dados dos autores | É contribuição nossa |
|---|---|
| A pergunta de partida: LLMs detectam e corrigem vulnerabilidades em código de conversas reais? | A auditoria dos números do artigo, recalculados a partir dos dados dos autores, sem LLM |
| O corpus: trechos do DevGPT, saídas dos 4 scanners estáticos e respostas dos modelos comerciais | O pipeline de 3 agentes (detector, corretor e verificador adversarial) e as 6 configurações do experimento |
| Os rótulos manuais: 56 issues reais e 85 falsos alarmes conhecidos | Precisão, recall e testes estatísticos sobre esses rótulos, o relatório, os slides e o código deste repositório |

## Equipe

Projeto da disciplina TAES, Centro de Informática, UFPE (novembro de 2026):

- Antonio Gabriel dos Santos Clemente
- Bianca Duarte Santos
- Caio Rocha Calado
- Vinicius Alves Fialho

## Estrutura do repositório

```
.
├── PLANO_EXECUCAO.md          plano: hipóteses H1–H5, configurações, métricas, fases F0–F8
├── artigo.pdf                 artigo analisado, cópia sem alterações (CC BY 4.0)
├── Resumo_do_projeto.pdf      resumo do projeto, do começo ao fim
├── requirements.txt           dependências Python do ambiente local
├── pipeline/
│   ├── config.yaml            modelos (tag e digest), parâmetros de inferência, prompts, repetições
│   ├── matching_families.yaml famílias de CWE usadas na regra de correspondência
│   ├── prompts/               prompts congelados dos agentes (a1_v2, a2_v1, a3_v1, a3b_v1, b0_paper, b0_extract_v1)
│   ├── src/                   código: agentes, runner, ferramentas do A3b, métricas e estatística, scripts por fase
│   ├── tests/                 158 testes automáticos (pytest)
│   ├── data/                  gabarito derivado dos dados dos autores (gt_issues.csv, gt_scanner_fp.csv, ...) e CWE-1000
│   ├── runs/                  saída do pipeline por configuração e repetição: runs/<config>/<rep>/<arquivo>.json
│   ├── cache/                 respostas brutas dos modelos (chave SHA-256 da chamada)
│   ├── results/               métricas, testes, figuras, auditoria, extrações do artigo, relatórios dos kernels (f5/)
│   └── DIARIO.md              diário de execução
├── kaggle/
│   ├── run/run.py             modelo de kernel (sobe o Ollama, roda o job, empacota as saídas)
│   ├── make_job.py            gera kaggle/<job>/ a partir do modelo, com os parâmetros de cada job
│   ├── build_dataset.py       monta o Dataset privado com o código e os dados mínimos
│   ├── import_outputs.py      traz as saídas de um kernel para pipeline/
│   ├── <job>/                 scripts exatamente como foram enviados ao Kaggle (pilot, f5a, f5b, f5var, ...)
│   └── infer.py               kernel da F0 (teste dos modelos na T4)
├── relatorio/                 relatório (Markdown e PDF) e o conversor md2html.py
└── apresentacao/              slides (.pptx e .pdf), guia de apresentação e estudo, e os geradores em fonte/
```

## Instalação

Requisitos: Python 3.12 e Git. Testado no Windows 11; os comandos para Linux e macOS estão ao lado.

```bash
git clone <url-deste-repositorio>
cd <pasta-do-repositorio>

# Windows
python -m venv pipeline\.venv
pipeline\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Linux / macOS
python3 -m venv pipeline/.venv
pipeline/.venv/bin/python -m pip install -r requirements.txt
```

Nos exemplos abaixo, `PY` é o Python do ambiente: `pipeline\.venv\Scripts\python.exe` no Windows ou `pipeline/.venv/bin/python` no Linux e no macOS. Rode tudo a partir da raiz do repositório. O `-I` (modo isolado) é usado em todos os comandos para que o Python não carregue nada da pasta atual nem dos dados baixados.

## 1. Reproduzir a análise sem GPU

O repositório já traz as saídas de todas as execuções (`pipeline/runs/`, `pipeline/cache/`, `pipeline/results/`). Com elas, as métricas, os testes estatísticos e as figuras podem ser refeitos em poucos minutos, sem chamar nenhum modelo:

```bash
PY -m pytest pipeline/tests -q                 # 158 testes
PY -I pipeline/src/f7_analyze.py               # correspondência com o gabarito (F6) e métricas/estatística (F7)
PY -I pipeline/src/f8_figures.py               # figuras em pipeline/results/figs/
```

O `f7_analyze.py` escreve `pipeline/results/f6_findings.csv`, `metrics.csv`, `tests.csv` e `f7_resultados.md`. As opções são `--rep main|var1|var2|var3` e `--n-boot 2000`.

## 2. Dados

| Dado | Origem | No repositório? |
|---|---|---|
| Repositório de dados dos autores (código do DevGPT, saídas dos scanners, respostas dos modelos, planilha de rótulos) | <https://github.com/vlad2010/MSc_DataEngineering_Results>, commit `bbbc1ec9f823` (2026-01-31) | **Não** (71 MB). Baixe como abaixo. |
| Gabarito derivado (`files.jsonl`, `gt_issues.csv`, `gt_scanner_fp.csv`, `paper_labels.csv`, casos da F4) | gerado por `f1_build.py` e `f4_prepare.py` | Sim, em `pipeline/data/` |
| CWE Research View 1000 (MITRE, v5.0) | <https://cwe.mitre.org/data/xml/views/1000.xml.zip> | Sim, `pipeline/data/cwe/1000.xml` |
| Artigo | Empirical Software Engineering 31:93 (2026), acesso aberto | Sim, `artigo.pdf` |

Os dados dos autores só são necessários para refazer o gabarito (F1), a auditoria (F2) e para rodar o pipeline. Para baixá-los:

```bash
git clone https://github.com/vlad2010/MSc_DataEngineering_Results pipeline/data/raw/MSc_DataEngineering_Results
git -C pipeline/data/raw/MSc_DataEngineering_Results checkout bbbc1ec9f823
```

No Windows, algumas pastas têm caminho com mais de 260 caracteres. Se o checkout falhar, rode `git -C pipeline/data/raw/MSc_DataEngineering_Results config core.longpaths true` e depois `git -C pipeline/data/raw/MSc_DataEngineering_Results restore --source=HEAD :/`.

**Segurança.** Trate esses dados como não confiáveis. O pipeline nunca executa o código dos autores: compila só para checar sintaxe (`-fsyntax-only`), e os scanners só leem o arquivo. Não rode scripts que venham dessa pasta.

## 3. Executar o experimento do zero

As fases seguem o `PLANO_EXECUCAO.md`. As fases locais (F1, F2, F6–F8) não usam LLM. A inferência (F4 e F5) roda no Kaggle: o projeto teve custo financeiro zero.

### 3.1 Fases locais antes da inferência

```bash
PY -I pipeline/src/f1_build.py        # F1: files.jsonl e gabarito em pipeline/data/, validação em results/f1_validacao.md
PY -I pipeline/src/f2_reanalysis.py   # F2: indicadores de falso positivo das respostas do artigo, validação do matcher
PY -I pipeline/src/f2_audit.py        # F2: auditoria do artigo (lê artigo.pdf) -> results/auditoria_artigo.md
PY -I pipeline/src/f4_prepare.py      # F4: casos de validação do julgamento de correção e da calibração do verificador
PY -I pipeline/src/runner.py --dry-run --select first:3   # teste de fumaça: modelos e ferramentas simulados
```

### 3.2 Preparar o Kaggle

1. Crie uma conta no Kaggle e **verifique o telefone**. Sem isso, os notebooks não têm GPU nem internet.
2. Gere um token de API (*Settings → API*) e configure o `kaggle` CLI, conforme a documentação do Kaggle. Não coloque o token dentro do repositório.
3. Defina o seu usuário na variável `KAGGLE_USERNAME`. Os scripts usam esse valor para nomear o Dataset e os kernels, todos **privados**:

   ```bash
   set KAGGLE_USERNAME=seu_usuario        # Windows (cmd)
   $env:KAGGLE_USERNAME="seu_usuario"     # Windows (PowerShell)
   export KAGGLE_USERNAME=seu_usuario     # Linux / macOS
   ```

4. Monte e publique o Dataset com o código, os prompts e os dados mínimos. O gabarito não vai para o Kaggle.

   ```bash
   PY -I kaggle/build_dataset.py
   kaggle datasets create -p kaggle/dataset_build --dir-mode zip                         # primeira vez
   kaggle datasets version -p kaggle/dataset_build --dir-mode zip -m "o que mudou"       # depois de mudar código ou prompts
   ```

### 3.3 Rodar os jobs

Cada job é gerado, enviado, acompanhado e importado assim (exemplo com `f5a`):

```bash
PY -I kaggle/make_job.py f5a                          # gera kaggle/f5a/run.py e kernel-metadata.json
kaggle kernels push -p kaggle/f5a                     # envia; o kernel sobe o Ollama, baixa os modelos e roda
kaggle kernels status <seu_usuario>/taes-f5a          # QUEUED, RUNNING, COMPLETE ou ERROR
kaggle kernels output <seu_usuario>/taes-f5a -p saidas/f5a
PY -I kaggle/import_outputs.py saidas/f5a --job f5a   # copia runs/, cache/ etc. para pipeline/ sem sobrescrever nada
```

O `import_outputs.py` tem `--dry-run` para conferir antes. Um status COMPLETE também aparece quando o script falhou: confira se a saída tem `run_error.txt`.

| Job | O que faz | GPU (sessão) | Saída usada em |
|---|---|---|---|
| `rehearsal` | ensaio em CPU, modelo minúsculo, 2 arquivos | 0 (CPU) | depuração |
| `pilot` | piloto da F4: 10 arquivos, todas as etapas, extração estruturada das respostas do artigo nos positivos, validação do julgamento de correção | ~3,0 h | `f4_analyze.py --out saidas/pilot`; E1 (positivos) |
| `tune1` | ajuste do prompt do detector (`a1_v1` → `a1_v2`) | ~0,3 h | escolha do prompt |
| `verif` | calibração do verificador sobre os 141 locais rotulados | ~0,6 h | relatório, seção 4 |
| `f5a`, `f5b` | **execução principal**: 114 arquivos em duas metades; B0, B1, C1, C2, C3 | 5,6 h + 4,1 h | tudo |
| `f5var` | estudo de variância: B1 e C3, seeds 1 a 3 | 3,94 h | variância |
| `f5neg` | extração das respostas do artigo nos 66 negativos | 1,03 h | E1 |
| `f5mfa`, `f5mfb` | ablação H5 (C3-mf): verificador = modelo do detector | 0,36 h + 0,40 h | H5 |
| `f5b0fix` | A3b nos patches do B0 | 2,17 h | correção |

**Limites do Kaggle.** A cota de GPU é de cerca de 30 h por semana. Cada sessão dura no máximo 12 h, e os jobs param de iniciar arquivos novos depois de 10 h. Só **2 sessões de GPU** podem rodar ao mesmo tempo, e um kernel pode ficar mais de 1 hora na fila (a fila não gasta cota). Os jobs `f5mfa` e `f5mfb` reaproveitam o A1 e o A2 da execução principal pelo cache, e o `f5b0fix` usa os patches do B0 dela: depois de importar a `f5a` e a `f5b`, rode `build_dataset.py` e publique uma nova versão do Dataset antes de enviar esses jobs.

### 3.4 Rodar fora do Kaggle (não testado)

O runner fala com dois servidores compatíveis com a API da OpenAI (o Ollama serve os dois modelos) e usa `gcc`/`g++`, `cppcheck`, `flawfinder` e `semgrep` do PATH para o A3b. Uma ferramenta ausente aparece no relatório como "não disponível".

```bash
PY -I pipeline/src/runner.py --select all --reps main --det-url http://127.0.0.1:11434/v1 --ver-url http://127.0.0.1:11435/v1
```

Para reproduzir os números, use os mesmos modelos. O `config.yaml` registra o digest de cada um, e o kernel confere o digest antes de rodar. O detector com cache KV f16 e contexto de 16 mil tokens precisa de uma GPU de 16 GB, e o verificador, de outra.

### 3.5 Análise, relatório e apresentação

```bash
PY -I pipeline/src/f4_analyze.py --out saidas/pilot   # piloto (F4)
PY -I pipeline/src/f7_analyze.py                      # F6 + F7
PY -I pipeline/src/f8_figures.py                      # F8: figuras
PY -I relatorio/md2html.py relatorio/RELATORIO.md relatorio/RELATORIO.html   # depois: abrir no navegador e imprimir em PDF
```

Os slides são gerados por `apresentacao/fonte/build_slides.js`, que precisa do Node.js 18 ou superior. Para trocar os nomes dos apresentadores, edite `NOMES` no início do arquivo.

```bash
cd apresentacao/fonte && npm install && cd ../..
node apresentacao/fonte/build_slides.js --html apresentacao/fonte/slides.html   # .pptx e um HTML com o mesmo layout
```

O PDF dos slides é a impressão desse HTML: abra-o no Edge ou no Chrome e imprima, ou use `msedge --headless --print-to-pdf=...`. O guia é montado com `apresentacao/fonte/build_guia.py`, a partir de `guia.md`, `notas.json` e do PDF dos slides.

## Reprodutibilidade

- **Prompts congelados.** Os prompts foram fixados antes da execução principal, e o hash de cada um está no `DIARIO.md`. A versão do prompt faz parte da chave do cache: mudar um prompt gera chamadas novas.
- **Cache.** Cada chamada é guardada em `pipeline/cache/` por uma chave SHA-256 que inclui modelo, digest, prompt, mensagens, temperatura, seed e schema. Repetir uma execução com a mesma configuração reaproveita as respostas sem chamar o modelo. Os arquivos `pipeline/results/f5/taes_outputs_<job>.tar.gz` guardam a saída completa de cada kernel.
- **Parâmetros.** A execução principal usa `temperature=0` e `seed=0`. Mesmo assim, respostas longas não são 100% determinísticas; por isso existe o estudo de variância.
- **Decisões.** Todas as decisões, os desvios do plano e os critérios fixados antes de cada análise estão em `pipeline/DIARIO.md`.

## Créditos e licenças de terceiros

- **Artigo (base deste trabalho):** Belozerov, V.; Barclay, P. J.; Sami, A. *Secure coding with AI – from detection to repair*. Empirical Software Engineering 31:93 (2026). DOI: [10.1007/s10664-026-10812-8](https://doi.org/10.1007/s10664-026-10812-8). Versão em preprint: [arXiv:2504.20814](https://arxiv.org/abs/2504.20814). Publicado em acesso aberto sob a licença [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). O `artigo.pdf` é uma cópia sem alterações. A auditoria, o pipeline, as figuras e as conclusões deste repositório são trabalho nosso, feito a partir do artigo e dos dados dos autores, e não representam a opinião deles.
- **Dados dos autores:** repositório de resultados do estudo, <https://github.com/vlad2010/MSc_DataEngineering_Results>. Este repositório não inclui o clone. Inclui só arquivos derivados (gabarito, extrações e saídas do pipeline, que citam trechos do código analisado), para permitir a reprodução da análise.
- **DevGPT:** conjunto público de conversas de desenvolvedores com o ChatGPT (Xiao, Treude, Hata e Matsumoto, MSR 2024), de onde vêm os trechos de código: <https://github.com/NAIST-SE/DevGPT>.
- **CWE:** Common Weakness Enumeration, © The MITRE Corporation; usado conforme os termos de uso do CWE.
- **Modelos:** `qwen2.5-coder:14b` (Alibaba, Qwen) e `gpt-oss:20b` (OpenAI), servidos pelo Ollama.
- **Identidade visual:** os slides seguem o modelo de apresentação do Centro de Informática da UFPE.

## Como citar o artigo original

Se você usar este repositório, cite também o artigo em que ele se baseia:

```bibtex
@article{belozerov2026secure,
  title   = {Secure coding with {AI} -- from detection to repair},
  author  = {Belozerov, Vladislav and Barclay, Peter J. and Sami, Ashkan},
  journal = {Empirical Software Engineering},
  volume  = {31},
  number  = {93},
  year    = {2026},
  doi     = {10.1007/s10664-026-10812-8}
}
```
