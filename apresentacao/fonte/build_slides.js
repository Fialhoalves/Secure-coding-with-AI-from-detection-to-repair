// Gera os slides da apresentação do projeto TAES no padrão visual do CIn-UFPE.
//
// Uma única descrição dos slides produz duas saídas:
//   1. apresentacao/Apresentacao_TAES.pptx (editável, com notas do apresentador), via pptxgenjs;
//   2. um HTML com as mesmas coordenadas, que o Edge imprime em PDF (versão para projetar e conferir).
// Também grava apresentacao/fonte/notas.json (roteiro por slide), usado pelo guia.
//
// Uso (na raiz do projeto, com o pptxgenjs instalado em <dir>/node_modules):
//   set NODE_PATH=<dir>\node_modules
//   node apresentacao\fonte\build_slides.js --html <saida.html> [--apply-theme <skill>\scripts\apply_theme.js]
//
// Para trocar os nomes dos apresentadores, edite NOMES abaixo e gere de novo.
"use strict";
const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");

const NOMES = ["Apresentador 1", "Apresentador 2", "Apresentador 3", "Apresentador 4"];
const TEMPOS = ["~8 min", "~9 min", "~11 min", "~10 min"];

const ARGS = process.argv.slice(2);
const arg = (k) => (ARGS.indexOf(k) >= 0 ? ARGS[ARGS.indexOf(k) + 1] : null);
const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const ASSETS = path.join(HERE, "assets");
const OUT_PPTX = path.join(ROOT, "apresentacao", "Apresentacao_TAES.pptx");
const OUT_HTML = arg("--html");
const APPLY_THEME = arg("--apply-theme");

// ---------------------------------------------------------------- cores e fontes (padrão CIn)
const HEX = {
  ink: "231F20", dred: "AF0421", white: "FFFFFF", gray: "EEEEEE", red: "DB1E2F", muted: "595959",
  b1: "4D4D4D", b0: "8C8C8C", pink: "E76C77", tint: "FBE3E5",
  light: "D9D9D9", grid: "E3E3E3", rule: "D0D0D0", zebra: "F6F6F6",
};
const SCHEME = {
  ink: "tx1", dred: "tx2", white: "bg1", gray: "bg2", red: "accent1", muted: "accent2",
  b1: "accent3", b0: "accent4", pink: "accent5", tint: "accent6",
};
const THEME = {
  name: "CIn UFPE",
  headFontFace: "Segoe UI",
  bodyFontFace: "Segoe UI",
  colors: {
    dk1: HEX.ink, lt1: HEX.white, dk2: HEX.dred, lt2: HEX.gray,
    accent1: HEX.red, accent2: HEX.muted, accent3: HEX.b1, accent4: HEX.b0, accent5: HEX.pink, accent6: HEX.tint,
    hlink: HEX.dred, folHlink: HEX.muted,
  },
};
const pc = (c) => SCHEME[c] || HEX[c] || c; // cor para o pptx (cor do tema quando houver)
const hx = (c) => HEX[c] || c; // hexadecimal puro (bordas, grades, fundos)
const hc = (c) => "#" + hx(c); // cor para o HTML
const FONT = "Segoe UI";
const fontFace = (font, bold) => (font === "semi" && !bold ? "Segoe UI Semibold" : FONT);

// ---------------------------------------------------------------- layouts (molduras)
const LAYOUTS = {
  CAPA: {
    bgImage: "bg_capa.png",
    rects: [{ x: 0.75, y: 1.2, w: 8.5, h: 1.45, fill: "white" }],
    images: [{ file: "logo_branco.png", x: 7.55, y: 4.72, w: 1.95 }],
    title: { x: 1.05, y: 1.2, w: 7.9, h: 1.45, size: 24, color: "red", bold: true, align: "left", valign: "middle" },
  },
  CONTEUDO: {
    bgColor: "white",
    title: { x: 0.45, y: 0.28, w: 9.1, h: 0.62, size: 28, color: "red", bold: true, align: "left", valign: "middle" },
    num: "muted",
  },
  ESCURO: {
    bgColor: "ink",
    title: { x: 0.45, y: 0.42, w: 9.1, h: 0.66, size: 26, color: "white", bold: true, align: "left", valign: "middle" },
    num: "light",
  },
  DIVIDIDO: {
    bgColor: "white",
    rects: [{ x: 4.5, y: 0, w: 5.5, h: 5.625, fill: "dred" }],
    title: { x: 0.6, y: 0.75, w: 3.6, h: 0.75, size: 32, color: "red", bold: true, align: "left", valign: "middle" },
    num: "light",
  },
  DIVISOR: {
    bgImage: "bg_divisor.png",
    rects: [{ x: 0, y: 1.0, w: 5.35, h: 0.95, fill: "white" }],
    title: { x: 0.45, y: 1.0, w: 4.85, h: 0.95, size: 30, color: "red", bold: true, align: "left", valign: "middle" },
  },
  CIRCULO: {
    bgImage: "bg_circulo.png",
    title: { x: 0.35, y: 0.75, w: 3.0, h: 0.5, size: 24, color: "white", bold: true, align: "center", valign: "middle" },
  },
  FIM: {
    bgImage: "bg_fim.png",
    title: { x: 0.2, y: 2.35, w: 3.68, h: 1.2, size: 30, color: "white", bold: true, align: "center", valign: "top" },
  },
  LOGO: { bgImage: "bg_logo.png" },
};
const NUM_BOX = { x: 9.0, y: 5.22, w: 0.55, h: 0.28, size: 10 };

// ---------------------------------------------------------------- descrição dos slides
const slides = [];
let cur = null;
let section = null;

function sec(title) {
  section = title;
}
function slide(layout, title, presenter, time, notes) {
  cur = { layout, title, presenter, time, notes, section, els: [] };
  slides.push(cur);
  return cur;
}

function parseRuns(s0, base) {
  // espaço inseparável entre número e unidade ("17,6 h", "5 p.p.") para a unidade não cair na linha seguinte
  const s = String(s0).replace(/(\d) (p\.p\.|h\b|mil\b|min\b|%)/g, "$1 $2");
  const out = [];
  const re = /\*\*(.+?)\*\*|==(.+?)==|\^\^(.+?)\^\^/g;
  let last = 0;
  let m;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push({ ...base, t: s.slice(last, m.index) });
    if (m[1] != null) out.push({ ...base, t: m[1], b: true });
    else if (m[2] != null) out.push({ ...base, t: m[2], b: true, c: base.em || "red" });
    else out.push({ ...base, t: m[3], i: true });
    last = re.lastIndex;
  }
  if (last < s.length) out.push({ ...base, t: s.slice(last) });
  if (!out.length) out.push({ ...base, t: "" });
  return out;
}

function paras(content, st) {
  const arr = Array.isArray(content) ? content : [content];
  return arr.map((p0) => {
    const p = typeof p0 === "string" ? { t: p0 } : p0;
    const base = {
      b: p.b ?? st.b, i: p.i ?? st.i, c: p.c ?? st.color ?? "ink",
      size: p.size ?? st.size ?? 14, font: p.font ?? st.font, em: st.em,
    };
    return {
      runs: parseRuns(p.t, base),
      bullet: p.bullet ?? st.bullet ?? false,
      indent: p.indent ?? st.indent ?? 14,
      sa: p.sa ?? st.sa ?? 0,
      sb: p.sb ?? 0,
    };
  });
}

// elementos
function T(x, y, w, h, content, st = {}) {
  cur.els.push({ k: "text", x, y, w, h, paras: paras(content, st), st });
}
function R(x, y, w, h, st = {}) {
  cur.els.push({ k: "rect", x, y, w, h, st });
}
function O(x, y, w, h, st = {}) {
  cur.els.push({ k: "oval", x, y, w, h, st });
}
function L(x1, y1, x2, y2, st = {}) {
  cur.els.push({ k: "line", x1, y1, x2, y2, st });
}
function I(file, x, y, w, h) {
  cur.els.push({ k: "img", file, x, y, w, h });
}
function TB(x, y, colW, rows, st = {}) {
  cur.els.push({ k: "table", x, y, colW, rows, st });
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// ---------------------------------------------------------------- componentes
function chip(x, y, w, text, fill = "ink", color = "white", size = 11) {
  T(x, y, w, 0.3, text, { size, b: true, color, fill, align: "center", valign: "middle", pad: [4, 1, 4, 1] });
}

function card(x, y, w, h, fill = "gray") {
  R(x, y, w, h, { fill });
}

function stat(x, y, w, big, label, o = {}) {
  T(x, y, w, o.bigH || 0.62, big, { size: o.bigSize || 30, b: true, color: o.bigColor || "red", valign: "bottom", align: o.align || "left" });
  T(x, y + (o.bigH || 0.62) + 0.04, w, o.labelH || 0.9, label, { size: o.labelSize || 13, color: o.labelColor || "ink", align: o.align || "left" });
}

function arrow(x1, y1, x2, y2, color = "b0", w = 1.5) {
  L(x1, y1, x2, y2, { color, w, arrow: true });
}

// dot plot com IC: cats = [{label, sub, color}], panels = [{title, max, vals: [{v, lo, hi, txt}]}]
function dotPanels(x, y, w, h, cats, panels, o = {}) {
  const labW = o.labW || 1.6;
  const gap = o.gap || 0.45;
  const pw = (w - labW - gap * (panels.length - 1)) / panels.length;
  const headH = 0.4;
  const axisH = 0.28;
  const rowH = (h - headH - axisH) / cats.length;
  const plotTop = y + headH;
  const plotBottom = plotTop + rowH * cats.length;
  cats.forEach((c, i) => {
    const content = c.sub ? [{ t: c.label, b: true, size: 13 }, { t: c.sub, size: 10.5, c: "muted" }] : [{ t: c.label, b: true, size: 13 }];
    T(x, plotTop + i * rowH, labW - 0.12, rowH, content, { valign: "middle" });
  });
  panels.forEach((p, j) => {
    const px = x + labW + j * (pw + gap);
    const sx = (v) => px + (pw * v) / p.max;
    T(px, y, pw, headH - 0.06, p.title, { size: 13, b: true, valign: "bottom" });
    const ticks = p.ticks || [0, 25, 50, 75, 100];
    ticks.forEach((t) => {
      L(sx(t), plotTop, sx(t), plotBottom, { color: t === 0 ? "rule" : "grid", w: 0.75 });
      if (t % 50 === 0) T(sx(t) - 0.3, plotBottom + 0.03, 0.6, axisH - 0.05, `${t}%`, { size: 10, color: "muted", align: "center" });
    });
    p.vals.forEach((v, i) => {
      if (v == null) return;
      const color = cats[i].color;
      const cy = plotTop + i * rowH + rowH / 2;
      if (v.lo != null) L(sx(v.lo), cy, sx(v.hi), cy, { color, w: 2.25 });
      O(sx(v.v) - 0.08, cy - 0.08, 0.16, 0.16, { fill: color, line: "white", lw: 1 });
      const lw = Math.max(0.45, v.txt.length * 0.078 + 0.12);
      const right = Math.max(v.hi ?? v.v, v.v);
      const left = Math.min(v.lo ?? v.v, v.v);
      const rx = sx(right) + 0.07;
      const lx = sx(left) - 0.07 - lw;
      if (rx + lw <= px + pw + 0.05) T(rx, cy - 0.14, lw, 0.28, v.txt, { size: 11, valign: "middle" });
      else if (lx >= px - 0.02) T(lx, cy - 0.14, lw, 0.28, v.txt, { size: 11, valign: "middle", align: "right" });
      else {
        const cx = Math.min(Math.max(sx(v.v) - lw / 2, px), px + pw - lw);
        T(cx, cy - 0.4, lw, 0.26, v.txt, { size: 11, valign: "bottom", align: "center" });
      }
    });
  });
}

// ---------------------------------------------------------------- cores por entidade (fixas no deck)
const CB0 = "b0";
const CB1 = "b1";
const CC3 = "red";
const CC2 = "dred";
const CART = "ink";

// =========================================================================================
// BLOCO 1 — Contexto e auditoria
// =========================================================================================
sec("Bloco 1 · Contexto e auditoria");

slide("CAPA", "Verificação adversarial com 3 agentes para reduzir falsos positivos na detecção de vulnerabilidades", 1, "0:45",
  `Boa tarde. Somos ${NOMES.join(", ")}. Nosso trabalho parte de um artigo publicado em 2026 na Empirical Software Engineering, que avaliou LLMs na detecção e na correção de vulnerabilidades em código C, C++ e C#. Fizemos duas coisas: auditamos os números do artigo com os dados dos próprios autores e testamos uma proposta para reduzir falsos positivos, um pipeline de três agentes que roda só com modelos abertos e gratuitos.`);
T(0.75, 2.85, 8.5, 0.8, "Auditoria de Belozerov et al. (EMSE, 2026) e teste de um pipeline com modelos abertos", { size: 17, i: true, color: "white", font: "semi" });
T(0.75, 3.75, 6.6, 0.4, NOMES.join("  ·  "), { size: 14, b: true, color: "white" });
T(0.75, 4.18, 6.6, 0.36, "Projeto da disciplina TAES  ·  Centro de Informática, UFPE  ·  novembro de 2026", { size: 12, color: "white" });

slide("CONTEUDO", "Roteiro", 1, "0:45",
  `A apresentação tem quatro blocos. Eu começo pelo contexto e pela auditoria do artigo. ${NOMES[1]} explica a proposta e o método. ${NOMES[2]} mostra os resultados. ${NOMES[3]} fecha com as análises complementares, os limites e a conclusão. A mensagem central, que vamos sustentar com números, é esta: o verificador corta falsos alarmes, mas corta issues reais junto, e não separa melhor o real do falso.`);
{
  const blocks = [
    ["01", "Contexto e auditoria", "O artigo, o que ele mede e o que a auditoria encontrou"],
    ["02", "Proposta e método", "Os 3 agentes, as 6 configurações, o gabarito e as métricas"],
    ["03", "Resultados", "O que o verificador faz com os achados, hipóteses e variância"],
    ["04", "Análises e conclusão", "Modelos do artigo, peso do modelo, correção e limites"],
  ];
  const w = 2.11;
  const gap = (9.1 - 4 * w) / 3;
  blocks.forEach((b, i) => {
    const x = 0.45 + i * (w + gap);
    card(x, 1.3, w, 3.2);
    T(x + 0.2, 1.42, w - 0.4, 0.62, b[0], { size: 30, b: true, color: "red", valign: "bottom" });
    T(x + 0.2, 2.1, w - 0.4, 0.62, b[1], { size: 16, b: true });
    T(x + 0.2, 2.75, w - 0.4, 0.5, [{ t: NOMES[i], b: true, size: 12 }, { t: TEMPOS[i], size: 12, c: "muted" }], {});
    T(x + 0.2, 3.35, w - 0.4, 1.15, b[2], { size: 13 });
  });
  T(0.45, 4.62, 8.5, 0.58, "**Mensagem central:** o verificador corta falsos alarmes, mas corta issues reais junto, e não separa melhor o real do falso.", { size: 14, valign: "middle" });
}

slide("CONTEUDO", "O artigo analisado", 1, "1:45",
  "O artigo pegou 2.315 trechos de C, C++ e C# do DevGPT, um conjunto de conversas reais de desenvolvedores com o ChatGPT, e passou esses trechos por quatro scanners estáticos. Daí saíram 114 arquivos. Na revisão manual, os autores confirmaram 56 vulnerabilidades reais em 48 arquivos e julgaram seguros 85 alertas dos scanners. Depois pediram a GPT-4.1, GPT-5 e Claude Opus 4.1, com um único prompt, que achassem e corrigissem os problemas. O resultado divulgado foi cerca de 80% de detecção e 77% de correção. Nosso trabalho foi auditar esses números e medir o que o artigo não mede: os falsos positivos.");
T(0.45, 1.0, 9.1, 0.36, "Belozerov, Barclay e Sami (2026). ^^Secure coding with AI – from detection to repair^^. EMSE 31:93.", { size: 12.5, color: "muted" });
T(0.45, 1.45, 9.1, 0.66, "**Pergunta do artigo:** LLMs conseguem detectar e corrigir vulnerabilidades em código que veio de conversas reais com o ChatGPT?", { size: 16 });
{
  const steps = [
    ["2.315", "trechos de C, C++ e C# do DevGPT"],
    ["4", "scanners estáticos: Snyk, Semgrep, Flawfinder e Cppcheck"],
    ["114", "arquivos: 48 com issue real e 66 negativos"],
    ["56 + 85", "revisão manual: 56 issues reais e 85 alertas julgados seguros"],
    ["~80%", "de “acurácia” na detecção (e ~77% na correção) com GPT-4.1, GPT-5 e Opus 4.1"],
  ];
  const w = 1.6;
  const gap = (9.1 - 5 * w) / 4;
  steps.forEach((s, i) => {
    const x = 0.45 + i * (w + gap);
    card(x, 2.3, w, 2.05, i === 4 ? "ink" : "gray");
    T(x + 0.12, 2.38, w - 0.24, 0.55, s[0], { size: 22, b: true, color: i === 4 ? "white" : "red", valign: "bottom" });
    T(x + 0.12, 2.98, w - 0.24, 1.3, s[1], { size: 12, color: i === 4 ? "white" : "ink" });
    if (i < 4) arrow(x + w + 0.03, 3.32, x + w + gap - 0.03, 3.32, "b0", 1.5);
  });
}
T(0.45, 4.55, 9.1, 0.6, "**Nosso trabalho:** auditar esses números com os dados dos autores e medir o que o artigo não mede: ==os falsos positivos==.", { size: 15, valign: "middle" });

slide("ESCURO", "O que o artigo mede, e o que não mede", 1, "1:45",
  "O que o artigo chama de acurácia é, na verdade, recall relativo: quantas das 56 issues do gabarito o modelo encontrou. Precisão e falso positivo nunca foram medidos, embora 66 dos 114 arquivos sejam negativos, ou seja, arquivos sem nenhuma vulnerabilidade real. Os indícios de falso positivo estão nos próprios dados: os modelos citam de 4,8 a 6,5 CWEs por arquivo, contra cerca de 1,2 issue real por arquivo positivo, e quase todos os arquivos negativos recebem pelo menos uma CWE. O prompt original manda encontrar problemas de segurança, o que incentiva o modelo a sempre achar alguma coisa. E cada modelo rodou uma única vez, sem intervalo de confiança.");
{
  const items = [
    ["~80%", "de “acurácia” = issues detectadas ÷ 56. É recall relativo ao gabarito dos scanners."],
    ["66 de 114", "arquivos são negativos, e mesmo assim precisão e falso positivo nunca foram medidos."],
    ["4,8 a 6,5", "CWEs citadas por arquivo, contra ~1,2 issue real por arquivo positivo."],
    ["98,5 a 100%", "dos arquivos negativos recebem ao menos uma CWE; 35% a 42% dos 85 falsos alarmes são citados."],
  ];
  const w = 2.12;
  const gap = (9.1 - 4 * w) / 3;
  items.forEach((it, i) => {
    const x = 0.45 + i * (w + gap);
    stat(x, 1.45, w, it[0], it[1], { bigSize: 26, bigColor: "pink", labelColor: "white", labelSize: 13, labelH: 1.6 });
  });
}
T(0.45, 3.95, 9.1, 0.8, "O prompt original manda o modelo **“encontrar problemas de segurança”**. Cada modelo rodou **uma única vez**, sem intervalo de confiança.", { size: 15, color: "light" });

slide("CONTEUDO", "Auditoria: o que não bate no artigo", 1, "1:45",
  "Recalculamos as tabelas do artigo a partir dos dados dos autores, sem usar LLM. Destaco seis pontos. Duas afirmações foram refutadas: o GPT-5 não corrigiu todas as 44 issues que detectou, porque detectou 44 e corrigiu 44, mas não as mesmas; e o Finding 15 não vale para GPT-4.1 nem para Opus 4.1. A melhora de 2024 para 2025 não é estatisticamente significativa. Há erros em tabelas, inconsistências no texto, e o gabarito mudou entre as duas versões no mesmo snapshot. Nada disso invalida o artigo, mas mostra que os números precisam ser lidos com cuidado.");
{
  const cards = [
    ["REFUTADO", "red", "“GPT-5 corrigiu todas as 44 issues que detectou”: detectou 44 e corrigiu 44, mas não as mesmas."],
    ["REFUTADO", "red", "Finding 15, “todos vão melhor em código do usuário”: falso para GPT-4.1 e Opus 4.1."],
    ["NÃO SIGNIFICATIVO", "ink", "A “melhora” de 2024 para 2025: McNemar exato nas 28 issues comuns, p = 0,065 a 0,267."],
    ["TABELAS COM ERROS", "ink", "Tabela 11 diverge do texto (16/16 × 17/15); 3 de 6 células das Tabelas 17–18; CWEs trocadas na 14."],
    ["INCONSISTÊNCIAS", "ink", "“3 scanners” no texto, 4 no estudo; “reescaneamento” no resumo, mas é trabalho futuro."],
    ["GABARITO MUDOU", "ink", "Entre 2024 e 2025, no mesmo snapshot: 4 issues saíram e 2 mudaram de metadados."],
  ];
  const w = 2.9;
  const gap = (9.1 - 3 * w) / 2;
  cards.forEach((c, i) => {
    const x = 0.45 + (i % 3) * (w + gap);
    const y = 1.1 + Math.floor(i / 3) * 1.92;
    card(x, y, w, 1.8);
    chip(x + 0.18, y + 0.18, c[0].length * 0.1 + 0.35, c[0], c[1]);
    T(x + 0.18, y + 0.6, w - 0.36, 1.15, c[2], { size: 14 });
  });
}
T(0.45, 4.98, 8.5, 0.3, "Recontagem com os dados dos autores, sem LLM. Detalhes: pipeline/results/auditoria_artigo.md", { size: 11, color: "muted" });

slide("DIVIDIDO", "Pergunta", 1, "1:15",
  `Daí a nossa pergunta: um verificador adversarial, ou seja, um agente cujo trabalho é tentar refutar cada achado, reduz falsos positivos sem perder detecção? Transformamos isso em hipóteses fixadas antes de rodar. A H1 é a principal: o pipeline completo reduz os falsos alarmes perdendo no máximo 5 pontos de recall. A H2 testa se só o prompt neutro já ajuda; a H3, se verificar antes de corrigir é melhor; a H4, se o verificador vale mais que um simples corte por confiança; a H5, se a família do verificador importa. A E1 compara com os modelos do artigo. Passo para ${NOMES[1]}, que explica como montamos o experimento.`);
T(0.6, 1.65, 3.6, 1.7, "Um verificador adversarial reduz falsos positivos ==sem perder detecção==?", { size: 21, b: true, color: "ink" });
T(0.6, 3.5, 3.6, 1.2, "Medimos precisão **e** recall usando só os rótulos dos autores: 56 issues reais e 85 falsos alarmes conhecidos.", { size: 14, color: "muted" });
T(4.95, 0.55, 4.65, 4.2, [
  { t: "**H1** · C3 × B1: o verificador reduz os falsos alarmes perdendo no máximo 5 p.p. de recall" },
  { t: "**H2** · B1 × B0: o prompt neutro (aceita “nenhuma vulnerabilidade”) já reduz falsos alarmes" },
  { t: "**H3** · C3 × C2: verificar sem ver a correção rejeita mais falsos alarmes" },
  { t: "**H4** · C1/C3 × curva do B1: o verificador vale mais que um corte por confiança" },
  { t: "**H5** · C3 × C3-mf: um verificador de outra família remove mais falsos positivos" },
  { t: "**E1** · C3 × modelos do artigo (exploratória)" },
], { size: 14, color: "white", sa: 9, bullet: false });
T(4.95, 4.62, 4.4, 0.55, "H1 a H3 são confirmatórias; critérios fixados antes dos resultados.", { size: 12, i: true, color: "white" });

// =========================================================================================
// BLOCO 2 — Proposta e método
// =========================================================================================
sec("Bloco 2 · Proposta e método");

function divisor(title, n, topics, notes, time = "0:15") {
  slide("DIVISOR", title, n, time, notes);
  T(0.45, 2.15, 5.0, 0.45, `Bloco ${n}  ·  ${NOMES[n - 1]}`, { size: 18, b: true, i: true, color: "white" });
  T(0.45, 2.6, 5.0, 0.38, `${TEMPOS[n - 1].replace("~", "≈ ")}utos`, { size: 14, i: true, color: "white" });
  T(6.35, 1.0, 3.3, 0.45, "Neste bloco", { size: 16, b: true, color: "red" });
  topics.forEach((t, i) => {
    T(6.35, 1.6 + i * 0.62, 0.45, 0.5, String(i + 1), { size: 20, b: true, color: "red" });
    T(6.8, 1.66 + i * 0.62, 2.85, 0.55, t, { size: 14, color: "ink" });
  });
}

divisor("Proposta e método", 2, ["Os 3 agentes", "As 6 configurações", "Dados e gabarito", "Correspondência e métricas", "Modelos e infraestrutura"],
  "Obrigado. Neste bloco eu mostro a proposta e como medimos.");

slide("CONTEUDO", "Três papéis: detectar, corrigir, verificar", 2, "2:00",
  "O pipeline tem três papéis. O A1, detector, recebe o código com linhas numeradas e devolve achados estruturados: a CWE, as linhas, de onde vem o dado do atacante, onde ele chega, qual o gatilho e uma confiança. Diferente do prompt do artigo, dizer “nenhuma vulnerabilidade” é uma resposta aceitável. O A2 é o corretor: gera um patch mínimo por achado. O A3 é o verificador adversarial, em duas versões. O A3a julga o achado tentando refutá-lo: o veredito padrão é “refutado”, e ele só confirma se houver fonte não confiável, caminho até a operação perigosa e um gatilho concreto. O A3b julga a correção, com compilação e scanners. Regras importantes: o verificador vê um achado por vez, e nenhum agente vê o gabarito, a saída dos scanners ou a confiança do detector.");
{
  const ags = [
    ["A1", "ink", "Detector", "Lê o código com linhas numeradas e lista achados: CWE, linhas, fonte → sink, gatilho e confiança. “Nenhuma vulnerabilidade” é resposta aceitável.", "qwen2.5-coder 14B"],
    ["A2", "b0", "Corretor", "Gera um patch mínimo para cada achado e explica como o gatilho fica bloqueado, preservando o comportamento.", "qwen2.5-coder 14B"],
    ["A3", "red", "Verificador adversarial", "A3a tenta refutar o achado (padrão: refutado), sem ver a correção. A3b julga a correção com compilação e scanners.", "gpt-oss 20B"],
  ];
  const w = 2.9;
  const gap = (9.1 - 3 * w) / 2;
  ags.forEach((a, i) => {
    const x = 0.45 + i * (w + gap);
    card(x, 1.15, w, 3.45);
    O(x + 0.22, 1.35, 0.72, 0.72, { fill: a[1] });
    T(x + 0.22, 1.35, 0.72, 0.72, a[0], { size: 18, b: true, color: "white", align: "center", valign: "middle" });
    T(x + 1.08, 1.35, w - 1.25, 0.72, a[2], { size: 17, b: true, valign: "middle" });
    T(x + 0.22, 2.25, w - 0.44, 1.75, a[3], { size: 14 });
    T(x + 0.22, 4.1, w - 0.44, 0.35, `Modelo: **${a[4]}**`, { size: 12, color: "muted" });
  });
}
T(0.45, 4.7, 8.5, 0.55, "Um achado por chamada no A3  ·  nenhum agente vê o gabarito, a saída dos scanners ou a confiança do A1  ·  ferramentas só no A3b", { size: 12.5, color: "muted", valign: "middle" });

slide("CONTEUDO", "Seis configurações, o mesmo detector", 2, "2:00",
  "Com esses papéis montamos seis configurações. O B0 é o prompt original do artigo, rodando no nosso modelo, seguido de uma extração estruturada para podermos comparar. O B1 é só o detector. O C1 acrescenta o verificador. O C2 corrige tudo primeiro e depois verifica achado e correção juntos, que era a ordem da proposta original. O C3 verifica antes e só corrige o que foi confirmado. O C3-mf é a ablação da H5: o verificador passa a ser o mesmo modelo do detector. Um detalhe de desenho: a saída do A1 é gerada uma vez e reaproveitada, então qualquer diferença entre B1, C1, C2 e C3 vem só das etapas depois do detector.");
{
  const rows = [
    ["B0", [["Prompt do artigo", "ink"], ["Extração estruturada", "b0"]], "linha de base comparável ao artigo"],
    ["B1", [["A1", "ink"]], "efeito do prompt neutro"],
    ["C1", [["A1", "ink"], ["A3a", "red"]], "efeito do verificador, sem correção"],
    ["C2", [["A1", "ink"], ["A2 (todos)", "b0"], ["A3 conjunto", "red"]], "verificar com a correção à vista"],
    ["C3", [["A1", "ink"], ["A3a", "red"], ["A2 (aceitos)", "b0"], ["A3b + ferramentas", "red"]], "verificar antes de corrigir"],
    ["C3-mf", [["A1", "ink"], ["A3a (qwen)", "pink"], ["A2 (aceitos)", "b0"], ["A3b (qwen)", "pink"]], "verificador = modelo do detector (H5)"],
  ];
  T(6.4, 1.0, 3.15, 0.32, "O que isola", { size: 12, b: true, color: "muted" });
  rows.forEach((r, i) => {
    const y = 1.38 + i * 0.57;
    T(0.45, y, 0.9, 0.44, r[0], { size: 16, b: true, valign: "middle" });
    let x = 1.4;
    r[1].forEach((b, j) => {
      const w = Math.max(0.62, b[0].length * 0.083 + 0.24);
      T(x, y, w, 0.44, b[0], { size: 11.5, b: true, color: "white", fill: b[1], align: "center", valign: "middle" });
      x += w;
      if (j < r[1].length - 1) {
        arrow(x + 0.03, y + 0.22, x + 0.19, y + 0.22, "b0", 1.25);
        x += 0.22;
      }
    });
    T(6.4, y, 3.15, 0.44, r[2], { size: 12.5, color: "ink", valign: "middle" });
  });
}
T(0.45, 4.85, 8.5, 0.38, "A saída do A1 é gerada uma vez e reaproveitada: as diferenças vêm só das etapas seguintes.", { size: 12.5, color: "muted", valign: "middle" });

slide("CONTEUDO", "Gabarito: só os rótulos dos autores", 2, "1:30",
  "Não tínhamos um especialista para anotar, então usamos só o julgamento que os autores já tinham feito. São 114 arquivos: 48 com issue real e 66 negativos. E são 141 locais de código rotulados: 56 issues reais e 85 falsos alarmes conhecidos, que são alertas de scanner que os autores examinaram e julgaram seguros. Cada achado do pipeline cai em uma de três classes: casa com uma issue real, casa com um falso alarme conhecido, ou fica fora do gabarito. Essa terceira classe não é julgada: pode ser uma alucinação ou uma vulnerabilidade que o scanner não viu. Por isso a precisão é calculada só no conjunto rotulado.");
{
  const bw = 4.2;
  T(0.45, 1.05, bw, 0.36, "114 arquivos", { size: 15, b: true });
  const a = (bw * 48) / 114;
  T(0.45, 1.45, a, 0.5, "48 com issue real", { size: 12, b: true, color: "white", fill: "ink", align: "center", valign: "middle" });
  T(0.45 + a, 1.45, bw - a, 0.5, "66 negativos", { size: 12, b: true, color: "white", fill: "b0", align: "center", valign: "middle" });
  T(0.45, 2.2, bw, 0.36, "141 locais rotulados pelos autores", { size: 15, b: true });
  const c = (bw * 56) / 141;
  T(0.45, 2.6, c, 0.5, "56 issues reais", { size: 12, b: true, color: "white", fill: "red", align: "center", valign: "middle" });
  T(0.45 + c, 2.6, bw - c, 0.5, "85 falsos alarmes conhecidos", { size: 12, b: true, color: "white", fill: "dred", align: "center", valign: "middle" });
  T(0.45, 3.3, bw, 1.0, "**Falso alarme conhecido:** alerta de scanner que os autores examinaram e julgaram seguro (ex.: um ^^printf^^ com formato constante).", { size: 13 });

  T(5.1, 1.05, 4.45, 0.36, "Três classes de achado", { size: 15, b: true });
  const cls = [
    ["Issue real", "red", "white", "casa com uma das 56: conta no recall"],
    ["Falso alarme conhecido", "dred", "white", "casa com um dos 85: conta como falso positivo"],
    ["Fora do gabarito", "gray", "ink", "não casa com nada: não é julgado (sem anotador), só entra nas descritivas"],
  ];
  cls.forEach((k, i) => {
    const y = 1.5 + i * 0.95;
    T(5.1, y, 1.65, 0.78, k[0], { size: 12.5, b: true, color: k[2], fill: k[1], align: "center", valign: "middle", pad: 4 });
    T(6.9, y, 2.65, 0.78, k[3], { size: 13, valign: "middle" });
  });
}
T(0.45, 4.6, 9.1, 0.6, "Sem anotador humano: a ==precisão== é calculada só no conjunto rotulado (141 locais). Os achados fora do gabarito ficam como limite superior e inferior.", { size: 14, valign: "middle" });

slide("CONTEUDO", "Como contamos acertos", 2, "1:45",
  "Para dizer que um achado casa com o gabarito, usamos uma regra estrita: mesmo arquivo, até três linhas de distância e CWE compatível, ou seja, igual, ancestral ou descendente na hierarquia oficial da MITRE, ou da mesma família. Cada issue conta uma vez. Como a regra pesa muito, rodamos análises de sensibilidade; a principal é a S1, que ignora a CWE. As métricas são o recall sobre as 56, a taxa de falsos alarmes sobre as 85 e a precisão no conjunto rotulado, além de F1, F0,5 e MCC. Os intervalos de confiança vêm de bootstrap sobre arquivos, e as comparações pareadas usam McNemar e Cochran com correção de Holm. Só H1 a H3 são confirmatórias.");
card(0.45, 1.1, 4.35, 3.75);
T(0.7, 1.25, 3.9, 0.4, "Regra de correspondência (estrita)", { size: 16, b: true });
[["1", "Mesmo arquivo", 0.45], ["2", "Até 3 linhas de distância", 0.45], ["3", "CWE compatível: igual, ancestral ou descendente na CWE-1000, ou da mesma família", 0.85]].forEach((r, i) => {
  const y = [1.8, 2.32, 2.84][i];
  O(0.7, y, 0.4, 0.4, { fill: "red" });
  T(0.7, y, 0.4, 0.4, r[0], { size: 14, b: true, color: "white", align: "center", valign: "middle" });
  T(1.25, y + 0.06, 3.4, r[2], r[1], { size: 14 });
});
T(0.7, 3.85, 3.9, 0.95, ["Cada issue conta no máximo uma vez.", "**Sensibilidade S1:** só a linha ±3, sem checar a CWE."], { size: 13, sa: 4 });

T(5.1, 1.1, 4.45, 0.4, "Métricas", { size: 16, b: true });
TB(5.1, 1.55, [1.75, 2.7], [
  ["Recall", "issues reais acusadas ÷ 56"],
  ["Falsos alarmes", "falsos alarmes acusados ÷ 85"],
  ["Precisão", "reais ÷ (reais + falsos alarmes)"],
  ["Também", "F1, F0,5 e MCC"],
], { size: 13, firstColBold: true, rowH: 0.4, noHeader: true });
T(5.1, 3.35, 4.45, 0.4, "Estatística", { size: 16, b: true });
T(5.1, 3.75, 4.45, 1.2, [
  { t: "IC de 95% por bootstrap sobre arquivos (2.000 réplicas)", bullet: true },
  { t: "McNemar exato, Q de Cochran, correção de Holm", bullet: true },
  { t: "H1 a H3 confirmatórias; o resto é exploratório", bullet: true },
], { size: 13, sa: 3 });

slide("CONTEUDO", "Modelos abertos, custo zero", 2, "1:30",
  `Tudo rodou com custo zero. Detector e corretor: qwen2.5-coder, de 14 bilhões de parâmetros, quantizado. Verificador: gpt-oss, de 20 bilhões, de outra família, com raciocínio médio. Usamos as GPUs gratuitas do Kaggle, duas T4, com o Ollama servindo os modelos: foram 17,6 horas de GPU nas execuções. Para controlar a variação, a execução principal usa temperatura zero e seed fixa; os prompts foram congelados com hash antes de rodar, e cada decisão ficou registrada num diário. Um ponto de transparência: ajustamos o prompt do detector num piloto de 10 arquivos, e a sensibilidade S4 refaz a análise sem esses arquivos. Passo para ${NOMES[2]}, com os resultados.`);
{
  const tiles = [
    ["14B", "**qwen2.5-coder** (Q4_K_M): detector e corretor"],
    ["20B", "**gpt-oss** (MXFP4, raciocínio médio): verificador, de outra família"],
    ["2 × T4", "GPUs gratuitas do **Kaggle**, modelos servidos pelo Ollama"],
    ["R$ 0", "**17,6 h** de GPU nas execuções, mais ~3,4 h de piloto e ajustes"],
  ];
  const w = 2.12;
  const gap = (9.1 - 4 * w) / 3;
  tiles.forEach((t, i) => {
    const x = 0.45 + i * (w + gap);
    card(x, 1.1, w, 1.85);
    T(x + 0.18, 1.18, w - 0.36, 0.62, t[0], { size: 26, b: true, color: "red", valign: "bottom" });
    T(x + 0.18, 1.86, w - 0.36, 1.0, t[1], { size: 12.5 });
  });
}
T(0.45, 3.15, 4.4, 0.36, "Controle", { size: 15, b: true });
T(0.45, 3.52, 4.4, 1.6, [
  { t: "temperature = 0 e seed = 0 na execução principal", bullet: true },
  { t: "até 4 achados por arquivo; achados repetidos removidos", bullet: true },
  { t: "verificador e corretor não veem a confiança do A1 nem os rótulos", bullet: true },
], { size: 13, sa: 4 });
T(5.15, 3.15, 4.4, 0.36, "Reprodutibilidade", { size: 15, b: true });
T(5.15, 3.52, 4.4, 1.6, [
  { t: "prompts congelados com hash antes da execução", bullet: true },
  { t: "piloto de 10 arquivos: a1_v1 → a1_v2 (S4 refaz tudo nos outros 104)", bullet: true },
  { t: "158 testes automáticos; cada decisão no DIARIO.md", bullet: true },
], { size: 13, sa: 4 });

// =========================================================================================
// BLOCO 3 — Resultados
// =========================================================================================
sec("Bloco 3 · Resultados");

divisor("Resultados", 3, ["Resultado principal", "O que o verificador remove", "Verificador × corte de confiança", "Hipóteses e variância", "Ruído, custo e balanço"],
  "Obrigado. Agora os resultados.");

slide("CIRCULO", "RESULTADO", 3, "0:45",
  "Começo pelo resultado em uma frase. Dos falsos alarmes conhecidos que o detector acusava, o verificador removeu 85%. Mas também removeu 64% das issues reais. A H1 admitia perder no máximo 5 pontos de recall; perdemos 12,5.");
T(0.35, 1.25, 3.0, 0.42, "em uma frase", { size: 18, font: "semi", color: "white", align: "center", valign: "middle" });
O(0.83, 1.95, 2.05, 2.05, { fill: "gray" });
T(0.83, 2.3, 2.05, 0.75, "85%", { size: 38, b: true, color: "red", align: "center", valign: "bottom" });
T(1.0, 3.07, 1.71, 0.6, "dos falsos alarmes removidos", { size: 12, b: true, color: "ink", align: "center" });
T(0.25, 4.15, 3.2, 0.75, "e 64% das issues reais perdidas", { size: 16, b: true, color: "white", align: "center", valign: "middle" });
T(4.9, 1.45, 4.6, 1.8, "O verificador adversarial cortou os falsos alarmes, e cortou as issues reais junto.", { size: 24, b: true, i: true, color: "white" });
T(4.9, 3.35, 4.6, 1.2, "A H1 admitia perder no máximo 5 p.p. de recall. Perdemos **12,5 p.p.**, e o ganho de precisão não é significativo.", { size: 16, color: "white" });

slide("CONTEUDO", "Resultado principal (regra estrita)", 3, "1:45",
  "Aqui estão as três métricas principais, com intervalos de 95%. O B0, com o prompt do artigo, acusa 27% das issues reais e 27% dos falsos alarmes. O B1, só o detector com prompt neutro, já cai para 15% de falsos alarmes, com 20% de recall. Com o verificador, em C1 e C3, os falsos alarmes vão para 2,4%, mas o recall vai para 7%: são 4 issues reais em 56. A precisão sobe para 67%, mas o intervalo vai de 25% a 100%, porque se apoia em 6 locais. O C2 fica igual ao C3. E o C3-mf, que veremos no bloco 4, não aceita nenhum achado.");
T(0.45, 0.92, 9.1, 0.32, "114 arquivos  ·  ponto = estimativa; linha = IC de 95% (bootstrap sobre arquivos)", { size: 12, color: "muted" });
dotPanels(0.45, 1.3, 9.1, 3.4, [
  { label: "B0", sub: "prompt do artigo", color: CB0 },
  { label: "B1", sub: "só o detector", color: CB1 },
  { label: "C1 = C3", sub: "com verificador", color: CC3 },
  { label: "C2", sub: "corrige e depois verifica", color: CC2 },
], [
  { title: "Recall (de 56)", max: 100, vals: [
    { v: 26.8, lo: 15.1, hi: 39.7, txt: "26,8% (15)" }, { v: 19.6, lo: 10.2, hi: 31.3, txt: "19,6% (11)" },
    { v: 7.1, lo: 1.6, hi: 15.2, txt: "7,1% (4)" }, { v: 7.1, lo: 1.7, hi: 14.6, txt: "7,1% (4)" }] },
  { title: "Falsos alarmes (de 85)", max: 100, vals: [
    { v: 27.1, lo: 18.2, hi: 37.0, txt: "27,1% (23)" }, { v: 15.3, lo: 8.0, hi: 23.5, txt: "15,3% (13)" },
    { v: 2.4, lo: 0, hi: 6.2, txt: "2,4% (2)" }, { v: 2.4, lo: 0, hi: 6.2, txt: "2,4% (2)" }] },
  { title: "Precisão", max: 100, vals: [
    { v: 39.5, lo: 25.0, hi: 54.1, txt: "39,5%" }, { v: 45.8, lo: 26.3, hi: 65.5, txt: "45,8%" },
    { v: 66.7, lo: 25.0, hi: 100, txt: "66,7%" }, { v: 66.7, lo: 25.0, hi: 100, txt: "66,7%" }] },
], { labW: 1.75 });
T(0.45, 4.82, 8.5, 0.4, "C1 e C3 aceitam o mesmo conjunto. C3-mf (verificador qwen): nenhum achado aceito (0 de 56, 0 de 85).", { size: 12, color: "muted", valign: "middle" });

slide("CONTEUDO", "Remove muito, discrimina pouco", 3, "1:45",
  "Este gráfico mostra o que o verificador fez com os locais rotulados que o detector acusava. Eram 11 issues reais, e ele manteve 4. Eram 13 falsos alarmes, e ele manteve 2. Proporcionalmente, manteve mais reais que falsos, 36% contra 15%, mas com números tão pequenos o teste exato de Fisher dá p = 0,36: não dá para distinguir isso de um filtro que rejeita quase tudo. O contraste interessante: na calibração, sobre os achados que os scanners geram, o mesmo verificador discrimina bem, 39% contra 5%. Ou seja, a capacidade de separar depende do tipo de achado que ele recebe.");
{
  const sq = 0.3;
  const g = 0.075;
  const x0 = 3.0;
  O(0.45, 1.06, 0.2, 0.2, { fill: "red" });
  T(0.72, 0.98, 2.4, 0.36, "mantido pelo verificador", { size: 12, valign: "middle" });
  O(3.1, 1.06, 0.2, 0.2, { fill: "white", line: "b0", lw: 1.25 });
  T(3.37, 0.98, 2.6, 0.36, "removido pelo verificador", { size: 12, valign: "middle" });
  const rowsW = [
    ["Issues reais que o detector acusava", 11, 4, "mantém 4 (36%)"],
    ["Falsos alarmes conhecidos que o detector acusava", 13, 2, "mantém 2 (15%)"],
  ];
  rowsW.forEach((r, i) => {
    const y = 1.55 + i * 0.85;
    T(0.45, y - 0.1, 2.45, 0.6, r[0], { size: 13, b: true, valign: "middle" });
    for (let k = 0; k < r[1]; k++) {
      const kept = k < r[2];
      R(x0 + k * (sq + g), y + 0.05, sq, sq, kept ? { fill: "red" } : { fill: "white", line: "b0", lw: 1.25 });
    }
    T(x0 + 13 * (sq + g) + 0.12, y - 0.05, 1.7, 0.5, r[3], { size: 14, b: true, valign: "middle" });
  });
}
R(0.45, 3.35, 4.4, 1.6, { fill: "ink" });
T(0.65, 3.45, 4.0, 1.4, ["**Fisher exato: p = 0,36**", "Não dá para distinguir isso de um filtro que rejeita quase tudo. Só pela linha (S1): mantém 16% dos reais e 10% dos falsos."], { size: 14, color: "white", sa: 6, valign: "middle" });
card(5.15, 3.35, 4.4, 1.6);
T(5.35, 3.45, 4.0, 1.4, ["**Contraste: calibração**", "Sobre os achados dos scanners, o mesmo verificador confirmou 39% dos reais (22/56) e 5% dos falsos (4/85), p = 3 × 10⁻⁷."], { size: 14, sa: 6, valign: "middle" });

slide("CONTEUDO", "Verificador × corte de confiança (H4)", 3, "1:15",
  "A H4 pergunta se o verificador vale mais que um corte simples. A linha laranja é o B1 aceitando só achados com confiança acima de um limiar. No mesmo nível de falsos alarmes do C3, 2,4%, o melhor corte do B1 acusa 1 issue real; o verificador acusa 4. É evidência a favor do verificador, mas fraca: 4 contra 1 locais.");
{
  const f = path.join(ASSETS, "fig_h4.png");
  const sz = pngSize(f);
  const h = 4.05;
  const w = (h * sz.w) / sz.h;
  I("fig_h4.png", 0.45, 1.05, w, h);
  const xr = 0.45 + w + 0.35;
  const wr = 9.55 - xr;
  T(xr, 1.1, wr, 1.0, "**Linha laranja:** o B1 aceitando só achados com confiança do A1 acima de um limiar (cada ponto é um limiar).", { size: 13 });
  card(xr, 2.2, wr, 1.75);
  T(xr + 0.2, 2.28, wr - 0.4, 0.4, "Com a taxa de falsos alarmes do C3 (2,4%):", { size: 12.5, b: true, valign: "middle" });
  T(xr + 0.2, 2.72, (wr - 0.4) / 2, 0.55, "1 de 56", { size: 24, b: true, color: "b1", valign: "bottom" });
  T(xr + 0.2, 3.28, (wr - 0.4) / 2, 0.55, "melhor corte de confiança do B1", { size: 11 });
  T(xr + 0.2 + (wr - 0.4) / 2, 2.72, (wr - 0.4) / 2, 0.55, "4 de 56", { size: 24, b: true, color: "red", valign: "bottom" });
  T(xr + 0.2 + (wr - 0.4) / 2, 3.28, (wr - 0.4) / 2, 0.55, "verificador (C1/C3)", { size: 11 });
  chip(xr, 4.15, 2.45, "H4 · EVIDÊNCIA FRACA", "ink");
  T(xr, 4.5, wr, 0.6, "+5,4 p.p., mas com base em 4 contra 1 locais.", { size: 13, valign: "middle" });
}

slide("CONTEUDO", "Hipóteses: o veredito", 3, "1:30",
  "Resumindo as hipóteses. A H1 não foi confirmada: os falsos alarmes caem, mas o recall cai bem mais que 5 pontos e a precisão não melhora de forma significativa. A H2 foi apoiada com ressalva: só o prompt neutro já reduz os falsos alarmes em quase 12 pontos, sem perda significativa de recall; a ressalva é que 28% dos achados do B0 não têm linha. A H3 não foi confirmada: verificar antes ou depois de corrigir deu o mesmo resultado, e a vantagem do C3 é de custo. A H4 tem evidência fraca. A H5 fica para o bloco 4.");
T(0.45, 0.92, 9.1, 0.32, "Diferenças A − B em p.p.; IC de 95% por bootstrap pareado por arquivo", { size: 12, color: "muted" });
TB(0.45, 1.32, [0.62, 1.38, 4.6, 2.5], [
  ["", "Comparação", "O que medimos", "Veredito"],
  ["H1", "C3 − B1", "Recall −12,5 [−22,0; −4,7]; falsos alarmes −12,9 [−20,5; −6,1]; precisão +20,8 [−18,4; +58,6]", "==Não confirmada:== recall cai mais que 5 p.p."],
  ["H2", "B1 − B0", "Falsos alarmes −11,8 [−20,2; −3,7]; recall −7,1 [−20,0; +4,9]; McNemar p = 0,013 (Holm 0,052)", "**Apoiada, com ressalva:** 28% dos achados do B0 sem linha"],
  ["H3", "C3 − C2", "Zero em tudo: os dois acusam os mesmos 2 falsos alarmes", "==Não confirmada;== C3 só é mais barato"],
  ["H4", "C1/C3 × curva do B1", "Na mesma taxa de falsos alarmes: 4/56 contra 1/56", "**Evidência fraca** (+5,4 p.p.)"],
  ["H5", "C3 − C3-mf", "O qwen como verificador refutou 229 de 229 achados", "==Não apoiada;== teste degenerado (bloco 4)"],
], { size: 12, firstColBold: true, rowH: 0.56 });

slide("CONTEUDO", "Variância: a conclusão se repete", 3, "1:15",
  "Como a execução principal é única, repetimos B1 e C3 três vezes com amostragem. Em nenhuma das três o critério da H1 foi cumprido. A queda de falsos alarmes é consistente, cerca de 12 pontos com intervalo abaixo de zero em todas, e a perda de recall também. Já a precisão do C3 oscila de 20% a 60%, porque se apoia em 5 a 7 locais. A execução principal fica dentro dessa variação.");
T(0.45, 0.92, 9.1, 0.32, "B1 e C3 repetidos 3 vezes com amostragem: detector com temperatura 0,7, verificador 1,0, seeds 1 a 3", { size: 12, color: "muted" });
TB(0.45, 1.35, [1.5, 0.88, 0.88, 0.88, 0.88, 1.15], [
  ["Repetição", "B1 recall", "B1 falsos alarmes", "C3 recall", "C3 falsos alarmes", "C3 precisão"],
  ["var1", "12,5%", "14,1%", "5,4%", "2,4%", "60,0%"],
  ["var2", "14,3%", "17,6%", "1,8%", "4,7%", "20,0%"],
  ["var3", "17,9%", "15,3%", "7,1%", "3,5%", "57,1%"],
  ["Média ± dp", "14,9 ± 2,7", "15,7 ± 1,8", "4,8 ± 2,7", "3,5 ± 1,2", "45,7 ± 22,3"],
  ["Principal (T = 0)", "19,6%", "15,3%", "7,1%", "2,4%", "66,7%"],
], { size: 12, firstColBold: true, rowH: 0.5, align: "center" });
T(6.9, 1.2, 2.65, 0.9, "0 de 3", { size: 44, b: true, color: "red", valign: "bottom" });
T(6.9, 2.12, 2.65, 0.65, "repetições cumprem o critério da H1", { size: 15, b: true });
T(6.9, 2.85, 2.65, 2.3, [
  { t: "falsos alarmes: −11,8 a −12,9 p.p. (IC abaixo de 0 nas três)", bullet: true },
  { t: "recall: −7,1 a −12,5 p.p.", bullet: true },
  { t: "precisão do C3: de 20% a 60%", bullet: true },
], { size: 13, sa: 5 });

slide("CONTEUDO", "O que se ganha e o que se paga", 3, "1:15",
  "Há um ganho claro: ruído. O B0 sinaliza 94% dos arquivos negativos; o C3, 9%. E os achados fora do gabarito caem de 202 no B1 para 16 no C3. Mas não sabemos quantos desses eram reais, porque não houve anotador. E há custo: o C3 gasta cerca de 12 vezes mais tokens por issue real acusada do que o detector sozinho; o C2, 21 vezes.");
{
  T(0.45, 1.0, 4.3, 0.42, "Menos ruído", { size: 18, b: true, color: "red" });
  const cols = [["B0", "93,9%", "328", "ink"], ["B1", "54,5%", "202", "ink"], ["C3", "9,1%", "16", "red"]];
  cols.forEach((c, i) => {
    const x = 0.45 + i * 1.45;
    T(x, 1.5, 1.35, 0.32, c[0], { size: 13, b: true, color: "muted" });
    T(x, 1.82, 1.35, 0.6, c[1], { size: 26, b: true, color: c[3], valign: "bottom" });
    T(x, 3.08, 1.35, 0.6, c[2], { size: 26, b: true, color: c[3], valign: "bottom" });
  });
  T(0.45, 2.45, 4.3, 0.4, "arquivos negativos sinalizados", { size: 12.5 });
  T(0.45, 3.7, 4.3, 0.62, "achados fora do gabarito (não julgados)", { size: 12.5 });
  T(0.45, 4.35, 4.3, 0.8, "Não sabemos quantos dos removidos eram vulnerabilidades reais que os scanners não viram.", { size: 12, color: "muted" });

  T(5.15, 1.0, 4.4, 0.42, "Mais custo", { size: 18, b: true });
  T(5.15, 1.45, 4.4, 0.32, "tokens por issue real acusada (milhares)", { size: 12.5, color: "muted" });
  const bars = [["B1", 16.0, CB1], ["B0", 43.6, CB0], ["C1", 155.7, CC3], ["C3", 188.4, CC3], ["C2", 344.2, CC2]];
  const bx = 5.75;
  const bwMax = 2.75;
  bars.forEach((b, i) => {
    const y = 1.9 + i * 0.5;
    T(5.15, y, 0.55, 0.34, b[0], { size: 13, b: true, valign: "middle" });
    const bw = (bwMax * b[1]) / 344.2;
    R(bx, y + 0.04, bw, 0.26, { fill: b[2] });
    T(bx + bw + 0.08, y, 0.9, 0.34, `${Math.round(b[1])} mil`, { size: 12, valign: "middle" });
  });
  T(5.15, 4.5, 4.4, 0.7, "Segundos de chamada por arquivo: B1 23  ·  C1 54  ·  C3 72  ·  B0 158  ·  C2 197", { size: 12, color: "muted" });
}

slide("CONTEUDO", "A redução valeu a pena?", 3, "1:15",
  `Então, a redução valeu a pena? Na conta absoluta, o C3 evita 11 falsos alarmes e perde 7 vulnerabilidades reais. Isso só compensa se perder uma vulnerabilidade custar menos do que revisar 1,6 alarme falso; em segurança, normalmente é o contrário. As métricas combinadas concordam: o F1 cai 14,6 pontos de forma significativa, e até o F0,5, que dá mais peso à precisão, cai. O C3 só venceria se a precisão valesse mais de 3,6 vezes o recall. O ganho real é de ruído. Passo para ${NOMES[3]}.`);
{
  card(0.45, 1.1, 4.35, 3.0);
  T(0.7, 1.2, 1.6, 0.85, "11", { size: 44, b: true, color: "red", valign: "bottom" });
  T(0.7, 2.07, 1.6, 0.62, "falsos alarmes conhecidos evitados", { size: 12.5 });
  T(2.25, 1.2, 0.5, 0.85, "×", { size: 30, b: true, color: "muted", align: "center", valign: "bottom" });
  T(2.85, 1.2, 1.7, 0.85, "7", { size: 44, b: true, color: "ink", valign: "bottom" });
  T(2.85, 2.07, 1.75, 0.62, "issues reais perdidas", { size: 12.5 });
  T(0.7, 2.95, 3.9, 1.05, "Compensa só se perder 1 vulnerabilidade custar menos que revisar **~1,6 alarme falso** (11 ÷ 7).", { size: 14 });
  T(0.45, 4.3, 4.35, 0.9, "Em segurança, deixar passar uma vulnerabilidade costuma custar bem mais que revisar um alarme.", { size: 13, color: "muted" });

  TB(5.15, 1.1, [1.0, 0.8, 0.8, 1.8], [
    ["Métrica", "B1", "C3", "Leitura"],
    ["F1", "27,5%", "12,9%", "−14,6 p.p. (IC < 0)"],
    ["F0,5", "36,2%", "25,0%", "também cai"],
    ["MCC", "0,06", "0,12", "IC inclui 0"],
    ["Precisão", "45,8%", "66,7%", "IC de 25% a 100%"],
  ], { size: 12, firstColBold: true, rowH: 0.44, align: "center" });
  T(5.15, 3.5, 4.4, 1.65, [
    "O C3 só vence no Fβ se a precisão valer **mais de 3,6 vezes** o recall (β < 0,28).",
    "**Ganho claro:** ruído. Arquivos negativos sinalizados: 54,5% → 9,1%.",
  ], { size: 13.5, sa: 8 });
}

// =========================================================================================
// BLOCO 4 — Análises complementares e conclusão
// =========================================================================================
sec("Bloco 4 · Análises e conclusão");

divisor("Análises e conclusão", 4, ["Contra os modelos do artigo (E1)", "O peso do modelo", "H5 (C3-mf)", "Correção com o mesmo juiz", "Limites e conclusão"],
  "Obrigado. Neste último bloco mostro as análises complementares, os limites e a conclusão.");

slide("CONTEUDO", "Contra os modelos do artigo (E1)", 4, "1:30",
  "Comparamos também com as respostas originais dos modelos do artigo, passando todas pelo mesmo extrator e pela mesma regra. GPT-4.1, GPT-5 e Opus acusam de 43% a 48% das issues reais e de 28% a 33% dos falsos alarmes. O C3 acusa 7% e 2%. Ou seja, o C3 tem muito menos falsos alarmes, mas só porque acusa muito menos de tudo; a precisão dele não se distingue da dos modelos comerciais. É outro ponto de operação, não um pipeline melhor.");
T(0.45, 0.92, 9.1, 0.32, "Mesmo extrator estruturado e mesma regra estrita para todos; 114 arquivos; análise exploratória", { size: 12, color: "muted" });
dotPanels(0.45, 1.28, 9.1, 3.5, [
  { label: "GPT-4.1", sub: "artigo", color: CART },
  { label: "GPT-5", sub: "artigo", color: CART },
  { label: "Opus 4.1", sub: "artigo", color: CART },
  { label: "B0", sub: "qwen, prompt do artigo", color: CB0 },
  { label: "B1", sub: "qwen, prompt neutro", color: CB1 },
  { label: "C3", sub: "pipeline completo", color: CC3 },
], [
  { title: "Recall (de 56)", max: 100, vals: [
    { v: 42.9, lo: 30.6, hi: 55.7, txt: "42,9%" }, { v: 48.2, lo: 34.8, hi: 62.2, txt: "48,2%" }, { v: 44.6, lo: 31.5, hi: 56.8, txt: "44,6%" },
    { v: 26.8, lo: 15.1, hi: 39.7, txt: "26,8%" }, { v: 19.6, lo: 10.2, hi: 31.3, txt: "19,6%" }, { v: 7.1, lo: 1.6, hi: 15.2, txt: "7,1%" }] },
  { title: "Falsos alarmes (de 85)", max: 100, vals: [
    { v: 31.8, lo: 21.7, hi: 41.7, txt: "31,8%" }, { v: 28.2, lo: 19.0, hi: 38.5, txt: "28,2%" }, { v: 32.9, lo: 23.3, hi: 43.0, txt: "32,9%" },
    { v: 27.1, lo: 18.2, hi: 37.0, txt: "27,1%" }, { v: 15.3, lo: 8.0, hi: 23.5, txt: "15,3%" }, { v: 2.4, lo: 0, hi: 6.2, txt: "2,4%" }] },
  { title: "Precisão", max: 100, vals: [
    { v: 47.1, lo: 32.7, hi: 61.5, txt: "47,1%" }, { v: 52.9, lo: 38.6, hi: 66.7, txt: "52,9%" }, { v: 47.2, lo: 33.3, hi: 60.3, txt: "47,2%" },
    { v: 39.5, lo: 25.0, hi: 54.1, txt: "39,5%" }, { v: 45.8, lo: 26.3, hi: 65.5, txt: "45,8%" }, { v: 66.7, lo: 25.0, hi: 100, txt: "66,7%" }] },
], { labW: 1.75 });
T(0.45, 4.85, 9.1, 0.4, "C3 − artigo: recall −36 a −41 p.p. e falsos alarmes −26 a −31 p.p. (IC exclui 0); precisão: IC de cerca de −30 a +57 p.p.", { size: 12, color: "muted", valign: "middle" });

slide("CONTEUDO", "O peso do modelo", 4, "1:45",
  "Usar modelos menores muda os resultados? Com o mesmo prompt, o qwen de 14B acusa de 16 a 21 pontos menos issues reais que os modelos do artigo, mas com taxa de falsos alarmes parecida. Olhando só a linha, os modelos maiores acham mais de tudo, reais e falsos, com a mesma precisão. Daí quatro conclusões: os números absolutos dependem do modelo; o modelo maior não resolve o falso positivo; o efeito do verificador depende de quem verifica; e em nenhuma troca o verificador separou melhor o real do falso. As comparações internas, como a H1, continuam válidas, porque usam o mesmo modelo em todas as configurações.");
T(0.45, 0.92, 9.1, 0.32, "Comparação exploratória, feita depois dos resultados; os modelos do artigo nunca rodaram dentro do pipeline", { size: 12, color: "muted" });
TB(0.45, 1.35, [1.6, 2.65], [
  ["Troca", "Efeito"],
  ["Detector: qwen 14B × GPT-4.1, GPT-5, Opus (mesmo prompt)", "Recall **−16 a −21 p.p.**; falsos alarmes parecidos (−1 a −6 p.p., IC inclui 0)"],
  ["Só a linha (sem CWE)", "Os maiores apontam mais de tudo, com a **mesma precisão** (+0,5 a +2,8 p.p.)"],
  ["Verificador: qwen 14B × gpt-oss 20B", "Confirma **0%** × **10%** dos achados"],
], { size: 12, firstColBold: true, rowH: 0.8 });
T(5.05, 1.3, 4.5, 0.4, "O que se conclui", { size: 16, b: true, color: "red" });
{
  const concl = [
    "Os números absolutos dependem do modelo; o recall baixo é, em boa parte, efeito do detector pequeno.",
    "O modelo maior não resolve o falso positivo: acusa 28% a 33% dos falsos alarmes, contra 27%.",
    "O efeito do verificador depende de quem verifica: o mesmo prompt dá 10% ou 0% de confirmações.",
    "Em nenhuma troca o verificador separou melhor o real do falso.",
  ];
  concl.forEach((c, i) => {
    const y = 1.78 + i * 0.84;
    O(5.05, y + 0.04, 0.38, 0.38, { fill: "red" });
    T(5.05, y + 0.04, 0.38, 0.38, String(i + 1), { size: 13, b: true, color: "white", align: "center", valign: "middle" });
    T(5.55, y, 4.0, 0.8, c, { size: 13 });
  });
}

slide("CONTEUDO", "H5: o verificador do mesmo modelo refuta tudo", 4, "1:15",
  "A H5 pergunta se usar um verificador de outra família ajuda. No C3-mf, o verificador é o próprio qwen. Resultado: ele refutou os 229 achados, todos, com confiança alta e argumentos plausíveis. O gpt-oss tinha confirmado 23. Formalmente a H5 não é apoiada, mas o teste é degenerado: um verificador que rejeita tudo remove todos os falsos alarmes. E a comparação troca família e capacidade ao mesmo tempo, então não dá para concluir nada sobre erros correlacionados.");
{
  card(0.45, 1.1, 2.9, 2.2);
  T(0.65, 1.2, 2.5, 0.8, "229 de 229", { size: 30, b: true, color: "red", valign: "bottom" });
  T(0.65, 2.05, 2.5, 1.15, "achados **refutados** pelo qwen como verificador (confiança 0,8 a 1,0)", { size: 13 });
  card(3.55, 1.1, 2.9, 2.2);
  T(3.75, 1.2, 2.5, 0.8, "23 de 229", { size: 30, b: true, color: "ink", valign: "bottom" });
  T(3.75, 2.05, 2.5, 1.15, "achados **confirmados** pelo gpt-oss (10%) no C3", { size: 13 });
  R(6.65, 1.1, 2.9, 2.2, { fill: "ink" });
  T(6.85, 1.2, 2.5, 0.8, "0 e 0", { size: 30, b: true, color: "pink", valign: "bottom" });
  T(6.85, 2.05, 2.5, 1.15, "issues reais (de 56) e falsos alarmes (de 85) acusados pelo C3-mf", { size: 13, color: "white" });
  chip(0.45, 3.55, 3.6, "NÃO APOIADA · TESTE DEGENERADO", "red");
  T(0.45, 3.95, 9.1, 1.25, [
    { t: "C3 − C3-mf: falsos alarmes +2,4 p.p. [0,0; +6,2]; recall +7,1 p.p. [+1,6; +15,2]. O C3-mf “remove mais” só porque remove tudo.", bullet: true },
    { t: "A comparação troca família **e** capacidade (14B sem raciocínio × 20B com raciocínio). Separar exigiria outra variante.", bullet: true },
  ], { size: 13.5, sa: 5 });
}

slide("CONTEUDO", "Correção, com o mesmo juiz (A3b)", 4, "1:15",
  "Na correção, usamos o mesmo juiz, o A3b, para todos. O B0 corrigiu 3 das 15 issues reais que acusou; C2 e C3, nenhuma das 4. Isso reflete mais quantas issues cada um acusa do que a qualidade do patch. Duas ressalvas: o juiz automático concorda pouco com os rótulos dos autores, kappa de 0,28; e o B0 gera um patch por arquivo, enquanto o pipeline gera um por achado. Não há evidência de que verificar antes de corrigir melhore a correção.");
{
  card(0.45, 1.1, 2.9, 1.9);
  T(0.65, 1.18, 2.5, 0.7, "3 de 15", { size: 30, b: true, color: "b1", valign: "bottom" });
  T(0.65, 1.92, 2.5, 1.0, "issues reais acusadas e corrigidas pelo **B0** (20%; 5,4% das 56)", { size: 12.5 });
  card(3.55, 1.1, 2.9, 1.9);
  T(3.75, 1.18, 2.5, 0.7, "0 de 4", { size: 30, b: true, color: "red", valign: "bottom" });
  T(3.75, 1.92, 2.5, 1.0, "no **C2** e no **C3** (taxa não informativa com 4 issues)", { size: 12.5 });
  T(6.65, 1.1, 2.9, 0.36, "A3b nos 373 achados do B0", { size: 12.5, b: true });
  const parts = [["válido", 141, "ink", "white"], ["parcial", 47, "b0", "white"], ["inválido", 185, "gray", "ink"]];
  let yy = 1.5;
  parts.forEach((p) => {
    const hh = (2.0 * p[1]) / 373;
    T(6.65, yy, 1.1, hh, `${p[1]}`, { size: 12, b: true, color: p[3], fill: p[2], align: "center", valign: "middle" });
    T(7.85, yy, 1.7, hh, `${p[0]} (${Math.round((100 * p[1]) / 373)}%)`, { size: 12, valign: "middle" });
    yy += hh;
  });
}
T(0.45, 3.68, 9.1, 1.5, [
  { t: "O juiz concorda pouco com os autores: **κ = 0,28** contra “Was issue fixed” (0,42 se “parcial” conta).", bullet: true },
  { t: "O B0 gera **um patch por arquivo**; C2 e C3, um por achado: a comparação não é um para um.", bullet: true },
  { t: "Patches desnecessários (para falsos alarmes conhecidos): **14 no C2**, 2 no C3.", bullet: true },
  { t: "Sem evidência de que verificar antes de corrigir melhore a correção.", bullet: true, b: true },
], { size: 13.5, sa: 5 });

slide("CONTEUDO", "Limites do estudo", 4, "1:30",
  "Os limites mais importantes. O gabarito mistura riscos de padrão, como um strlen ou um printf que o scanner marca, com vulnerabilidades exploráveis, e o verificador procura explorabilidade; parte da perda pode ser rejeição correta, mas sem anotador não dá para afirmar. Os falsos alarmes conhecidos são só do tipo scanner. A amostra é pequena. A regra de correspondência concorda pouco com os rótulos de detecção dos autores, por isso fizemos sensibilidades. E os modelos são menores, com risco de contaminação, porque tudo é público.");
{
  const lim = [
    ["Gabarito", "Mistura riscos de padrão (strlen, printf) com falhas exploráveis; o verificador busca explorabilidade."],
    ["Tipo de falso alarme", "Só falsos alarmes de scanner: alucinações livres do modelo ficam fora do gabarito."],
    ["Amostra pequena", "56 reais e 85 falsos; o C3 acusa 4 e 2. Precisão do C3: IC de 25% a 100%."],
    ["Correspondência", "A regra concorda pouco com o “detected” dos autores (κ de 0,08 a 0,27); S1 e S6 medem o efeito."],
    ["Modelos e execução", "Modelos menores que os do artigo; execução única, com variância repetida só em B1 e C3."],
    ["Contaminação", "DevGPT, artigo e dados são públicos; os modelos podem ter visto os rótulos."],
  ];
  const w = 2.9;
  const gap = (9.1 - 3 * w) / 2;
  lim.forEach((l, i) => {
    const x = 0.45 + (i % 3) * (w + gap);
    const y = 1.1 + Math.floor(i / 3) * 2.05;
    card(x, y, w, 1.95);
    T(x + 0.18, y + 0.14, w - 0.36, 0.4, l[0], { size: 15, b: true, color: "red" });
    T(x + 0.18, y + 0.58, w - 0.36, 1.3, l[1], { size: 13.5 });
  });
}

slide("ESCURO", "Conclusão", 4, "2:00",
  "Concluindo: neste experimento, o verificador adversarial desloca o ponto de operação, com menos alarmes e menos detecção, em vez de separar melhor o real do falso. A premissa de que mais um agente resolve o falso positivo sem perder detecção não se confirmou. O que fica de contribuição: a auditoria do artigo, um pipeline reprodutível a custo zero e uma avaliação que mede precisão e recall com os rótulos que já existiam. Como próximos passos: um anotador humano para os achados fora do gabarito, um verificador mais forte e uma variante que separe família de capacidade, e um detector maior.");
T(0.45, 1.3, 9.1, 1.0, "O verificador adversarial ==desloca o ponto de operação==, com menos alarmes e menos detecção, em vez de separar melhor o real do falso.", { size: 20, b: true, color: "white", em: "pink" });
{
  const cols = [
    ["O que mostramos", [
      "H1 não confirmada, também nas 3 repetições",
      "O verificador discrimina achados de scanner (39% × 5%), mas não os do detector (36% × 15%, p = 0,36)",
      "O artigo mede só recall relativo",
    ]],
    ["Contribuições", [
      "Auditoria dos números do artigo",
      "Pipeline reprodutível a custo zero",
      "Precisão e recall com os rótulos existentes",
    ]],
    ["Próximos passos", [
      "Anotador humano para os achados fora do gabarito",
      "Verificador mais forte; separar família de capacidade",
      "Detector maior, para errar menos a CWE",
    ]],
  ];
  const w = 2.9;
  const gap = (9.1 - 3 * w) / 2;
  cols.forEach((c, i) => {
    const x = 0.45 + i * (w + gap);
    T(x, 2.55, w, 0.4, c[0], { size: 15, b: true, color: "pink" });
    T(x, 3.0, w, 2.15, c[1].map((t) => ({ t, bullet: true })), { size: 13, color: "white", sa: 6 });
  });
}

slide("FIM", "Muito obrigado!", 4, "0:30",
  "Obrigado. Ficamos à disposição para perguntas. Temos slides de apêndice com a sensibilidade, os custos, os testes pareados e a auditoria completa.");
T(4.55, 0.85, 5.0, 0.7, "Perguntas?", { size: 32, b: true, color: "red" });
T(4.55, 1.65, 5.0, 1.3, NOMES.map((n) => ({ t: n })), { size: 15, b: true, sa: 2 });
T(4.55, 3.05, 5.0, 0.36, "Materiais", { size: 14, b: true, color: "muted" });
T(4.55, 3.42, 5.0, 1.6, [
  { t: "Relatório final: relatorio/RELATORIO.pdf", bullet: true },
  { t: "Decisões e execuções: pipeline/DIARIO.md", bullet: true },
  { t: "Código, prompts e resultados: pipeline/", bullet: true },
  { t: "Artigo: Belozerov et al., EMSE 31:93 (2026)", bullet: true },
], { size: 12.5, sa: 3 });

// =========================================================================================
// APÊNDICE
// =========================================================================================
sec("Apêndice");

slide("CONTEUDO", "Apêndice A · Sensibilidade", 0, "",
  "Para perguntas sobre a regra de correspondência. Cada célula é recall / taxa de falsos alarmes. A conclusão qualitativa não muda em nenhuma variante: o verificador corta os dois juntos. A S1 mostra quanto a regra estrita mede a CWE que o modelo escolhe: o B1 sobe de 19,6% para 55,4% de recall quando a CWE é ignorada, porque o detector usa CWE-78 em quase tudo.");
TB(0.45, 1.1, [3.5, 1.4, 1.4, 1.4, 1.4], [
  ["Variante (recall / falsos alarmes)", "B0", "B1", "C1 = C3", "C2"],
  ["Principal (regra estrita)", "26,8 / 27,1", "19,6 / 15,3", "7,1 / 2,4", "7,1 / 2,4"],
  ["S1: só linha ±3, sem CWE", "67,9 / 44,7", "55,4 / 34,1", "8,9 / 3,5", "8,9 / 3,5"],
  ["S2: “uncertain” aceito", "26,8 / 27,1", "19,6 / 15,3", "8,9 / 2,4", "7,1 / 2,4"],
  ["S3: só segurança (54 issues)", "27,8 / 27,1", "20,4 / 15,3", "7,4 / 2,4", "7,4 / 2,4"],
  ["S4: 104 arquivos fora do piloto", "25,5 / 25,3", "19,1 / 13,9", "8,5 / 2,5", "8,5 / 2,5"],
  ["S5: sem as 2 extrações falhas do B0", "26,8 / 27,7", "19,6 / 15,7", "7,1 / 2,4", "7,1 / 2,4"],
  ["S6: arquivo + CWE, sem linha", "42,9 / 40,0", "28,6 / 23,5", "8,9 / 4,7", "8,9 / 3,5"],
], { size: 12, firstColBold: true, rowH: 0.42, align: "center" });
T(0.45, 4.6, 9.1, 0.6, "Na S1, dos 31 locais reais e 29 falsos alarmes que o B1 acusava só pela linha, o verificador mantém 5 e 3 (16% e 10%).", { size: 12.5, color: "muted", valign: "middle" });

slide("CONTEUDO", "Apêndice B · Custo por configuração", 0, "",
  "Para perguntas sobre custo. Cada configuração é contada sozinha: o A1 e o A3a compartilhados entram em todas as que os usam. A execução principal inteira levou 9,7 horas de GPU; somando variância, E1, C3-mf e A3b no B0, foram 17,6 horas, sem pagamento.");
TB(0.45, 1.1, [1.1, 1.5, 1.6, 1.6, 1.6, 1.7], [
  ["Config", "Chamadas por arquivo", "Tokens de entrada por arquivo", "Tokens de saída por arquivo", "Segundos de chamada por arquivo", "Tokens por issue real acusada"],
  ["B0", "2", "3.294", "2.447", "158", "43.632"],
  ["B1", "1", "1.193", "353", "23", "16.020"],
  ["C1", "3", "4.090", "1.373", "54", "155.689"],
  ["C2", "5", "8.133", "3.944", "197", "344.205"],
  ["C3", "3,4", "4.883", "1.728", "72", "188.415"],
], { size: 12, firstColBold: true, rowH: 0.45, align: "center" });
T(0.45, 4.3, 8.5, 0.85, [
  "GPU: execução principal 9,7 h; extração das respostas do artigo nos negativos 1,03 h; variância 3,94 h; C3-mf 0,76 h; A3b no B0 2,17 h. Total: 17,6 h, mais ~3,4 h de piloto e ajustes.",
], { size: 12.5, color: "muted" });

slide("CONTEUDO", "Apêndice C · Testes pareados por local", 0, "",
  "Para perguntas sobre os testes estatísticos. O Q de Cochran compara as cinco configurações ao mesmo tempo; o McNemar exato compara pares, contando os locais acusados por uma e não pela outra. A correção de Holm controla as comparações múltiplas.");
TB(0.45, 1.1, [2.6, 3.25, 3.25], [
  ["Teste", "Issues reais (56 locais)", "Falsos alarmes conhecidos (85 locais)"],
  ["Q de Cochran (5 configurações)", "Q = 28,4 (gl 4), p = 1,0 × 10⁻⁵", "Q = 65,0 (gl 4), p = 2,6 × 10⁻¹³"],
  ["McNemar B1 × C3", "7 só no B1, 0 só no C3: p = 0,016 (Holm 0,11)", "11 contra 0: p = 0,001 (Holm 0,007)"],
  ["McNemar B0 × B1", "8 contra 4: p = 0,39", "12 contra 2: p = 0,013 (Holm 0,052)"],
  ["McNemar C2 × C3", "1 contra 1: p = 1", "0 contra 0: p = 1"],
  ["Fisher (o que o verificador manteve)", "4 de 11 reais", "2 de 13 falsos: p = 0,36"],
], { size: 12, firstColBold: true, rowH: 0.55 });

slide("CONTEUDO", "Apêndice D · Auditoria completa", 0, "",
  "Para perguntas sobre a auditoria. Todos os itens foram recalculados a partir das tabelas do PDF e dos dados dos autores, sem LLM. Detalhes em pipeline/results/auditoria_artigo.md.");
TB(0.45, 1.0, [7.2, 1.9], [
  ["Item", "Veredito"],
  ["Tabela 11 (GPT-4o, 2024): o texto diz 17 corrigidas e 15 não; a tabela tem 16 e 16", "confirmado"],
  ["Tabelas 17 e 18 (código do usuário × gerado): 3 de 6 células divergem da recontagem", "confirmado"],
  ["Finding 15 (“todos os modelos vão melhor em código do usuário”)", "refutado (GPT-4.1, Opus)"],
  ["“GPT-5 corrigiu todas as 44 issues que detectou”: as 44 corrigidas não são as mesmas", "refutado"],
  ["O gabarito mudou entre 2024 e 2025 no mesmo snapshot (4 saíram; 2 com metadados alterados)", "confirmado"],
  ["“Melhora” de 2024 para 2025: McNemar exato nos 28 itens comuns, p = 0,065 a 0,267", "não significativa"],
  ["“Re-scanning of the modified code” no resumo × reescaneamento como trabalho futuro", "inconsistência"],
  ["Número de scanners (texto diz 3, o estudo usa 4); 49 das 56 issues vêm de um só scanner", "inconsistência"],
  ["“Accuracy” nos Findings 4 e 15 é recall relativo, sem precisão nem falso positivo", "rótulo inadequado"],
  ["CWEs trocadas na Tabela 14 (v10:3/7 e v10:3/11)", "confirmado"],
], { size: 11, rowH: 0.37 });

slide("LOGO", "", 0, "", "");

// =========================================================================================
// SAÍDA 1: PPTX
// =========================================================================================
function pptxRuns(ps) {
  const out = [];
  ps.forEach((p, pi) => {
    p.runs.forEach((r, ri) => {
      const o = {
        fontFace: fontFace(r.font, r.b),
        fontSize: r.size,
        color: pc(r.c),
        bold: !!r.b,
        italic: !!r.i,
      };
      if (ri === 0) {
        if (p.bullet) o.bullet = { indent: p.indent };
        if (p.sa) o.paraSpaceAfter = p.sa;
        if (p.sb) o.paraSpaceBefore = p.sb;
      }
      if (ri === p.runs.length - 1 && pi < ps.length - 1) o.breakLine = true;
      out.push({ text: r.t, options: o });
    });
  });
  return out;
}

// margem em pt, na ordem do pptxgenjs para caixas de texto: [esquerda, direita, baixo, cima]
function padArr(pad) {
  if (pad == null) return [0, 0, 0, 0];
  if (typeof pad === "number") return [pad, pad, pad, pad];
  const [l, t, r, b] = pad; // nossa ordem: esquerda, cima, direita, baixo
  return [l, r, b, t];
}

function pptxCell(c, st, isHeader, rowIdx, colIdx) {
  const cell = typeof c === "string" ? { t: c } : c;
  const bold = isHeader || (st.firstColBold && colIdx === 0);
  const ps = paras([{ t: cell.t, b: bold }], { size: st.size || 12, color: isHeader ? "white" : "ink" });
  let fill = isHeader ? hx("ink") : rowIdx % 2 === 0 ? hx("zebra") : hx("white");
  if (cell.fill) fill = hx(cell.fill);
  return {
    text: pptxRuns(ps),
    options: {
      fill: { color: fill },
      align: colIdx === 0 ? "left" : st.align || "left",
      valign: "middle",
      margin: [3, 5, 3, 5], // pt: cima, direita, baixo, esquerda
      border: [{ type: "solid", pt: 0.75, color: hx("rule") }, { type: "solid", pt: 0.75, color: hx("rule") }, { type: "solid", pt: 0.75, color: hx("rule") }, { type: "solid", pt: 0.75, color: hx("rule") }],
    },
  };
}

function textOpts(lay, extra = {}) {
  return {
    fontFace: FONT,
    fontSize: lay.size,
    color: pc(lay.color),
    bold: !!lay.bold,
    align: lay.align || "left",
    valign: lay.valign || "top",
    margin: 0,
    ...extra,
  };
}

async function buildPptx() {
  const pres = new PptxGenJS();
  pres.layout = "LAYOUT_16x9";
  pres.author = NOMES.join(", ");
  pres.company = "CIn-UFPE";
  pres.title = "Verificação adversarial com 3 agentes para reduzir falsos positivos";
  pres.subject = "Projeto TAES: auditoria de Belozerov et al. (2026) e pipeline de 3 agentes";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

  for (const [name, lay] of Object.entries(LAYOUTS)) {
    const objects = [];
    (lay.rects || []).forEach((r) => objects.push({ rect: { x: r.x, y: r.y, w: r.w, h: r.h, fill: { color: pc(r.fill) } } }));
    (lay.images || []).forEach((im) => {
      const sz = pngSize(path.join(ASSETS, im.file));
      objects.push({ image: { x: im.x, y: im.y, w: im.w, h: (im.w * sz.h) / sz.w, path: path.join(ASSETS, im.file) } });
    });
    if (lay.title) {
      objects.push({ placeholder: { options: { name: "title", type: "title", x: lay.title.x, y: lay.title.y, w: lay.title.w, h: lay.title.h, ...textOpts(lay.title) }, text: "" } });
    }
    const def = { title: name, objects };
    if (lay.bgImage) def.background = { path: path.join(ASSETS, lay.bgImage) };
    else def.background = { color: hx(lay.bgColor) };
    if (lay.num) def.slideNumber = { x: NUM_BOX.x, y: NUM_BOX.y, w: NUM_BOX.w, h: NUM_BOX.h, fontFace: FONT, fontSize: NUM_BOX.size, color: pc(lay.num), align: "right" };
    pres.defineSlideMaster(def);
  }

  let lastSection = null;
  for (const s of slides) {
    if (s.section !== lastSection) {
      pres.addSection({ title: s.section });
      lastSection = s.section;
    }
    const sl = pres.addSlide({ masterName: s.layout, sectionTitle: s.section });
    const lay = LAYOUTS[s.layout];
    // título no padrão escuro: etiqueta vermelha sob o texto
    if (s.layout === "ESCURO") sl.addShape(pres.shapes.RECTANGLE, { x: 0, y: lay.title.y, w: tagWidth(s.title, lay.title), h: lay.title.h, fill: { color: pc("red") } });
    if (lay.title && s.title) sl.addText(s.title, { placeholder: "title" });
    for (const e of s.els) {
      if (e.k === "rect") {
        const o = { x: e.x, y: e.y, w: e.w, h: e.h, fill: { color: pc(e.st.fill || "gray") } };
        if (e.st.line) o.line = { color: pc(e.st.line), width: e.st.lw || 1 };
        sl.addShape(pres.shapes.RECTANGLE, o);
      } else if (e.k === "oval") {
        const o = { x: e.x, y: e.y, w: e.w, h: e.h, fill: { color: pc(e.st.fill || "gray") } };
        if (e.st.line) o.line = { color: pc(e.st.line), width: e.st.lw || 1 };
        sl.addShape(pres.shapes.OVAL, o);
      } else if (e.k === "line") {
        const o = { x: e.x1, y: e.y1, w: Math.max(e.x2 - e.x1, 0), h: Math.max(e.y2 - e.y1, 0), line: { color: pc(e.st.color || "rule"), width: e.st.w || 1 } };
        if (e.st.arrow) o.line.endArrowType = "triangle";
        sl.addShape(pres.shapes.LINE, o);
      } else if (e.k === "img") {
        sl.addImage({ path: path.join(ASSETS, e.file), x: e.x, y: e.y, w: e.w, h: e.h });
      } else if (e.k === "text") {
        const o = {
          x: e.x, y: e.y, w: e.w, h: e.h,
          fontFace: FONT,
          align: e.st.align || "left",
          valign: e.st.valign || "top",
          margin: padArr(e.st.pad),
          isTextBox: true,
          fit: "none",
        };
        if (e.st.fill) o.fill = { color: pc(e.st.fill) };
        sl.addText(pptxRuns(e.paras), o);
      } else if (e.k === "table") {
        const st = e.st;
        const rows = e.rows.map((row, ri) => row.map((c, ci) => pptxCell(c, st, !st.noHeader && ri === 0, st.noHeader ? ri : ri - 1, ci)));
        const w = e.colW.reduce((a, b) => a + b, 0);
        sl.addTable(rows, { x: e.x, y: e.y, w, colW: e.colW, rowH: st.rowH || 0.4, fontFace: FONT, fontSize: st.size || 12, autoPage: false });
      }
    }
    if (s.notes) {
      const who = s.presenter ? `[${NOMES[s.presenter - 1]} · ${s.time}] ` : "";
      sl.addNotes(who + s.notes);
    }
  }
  await pres.writeFile({ fileName: OUT_PPTX });
  await postProcess(OUT_PPTX);
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT_PPTX, THEME);
  }
  console.log("pptx:", OUT_PPTX);
}

// pptxgenjs escreve um <a:pPr> por trecho de texto; um parágrafo só pode ter o primeiro.
async function postProcess(file) {
  const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  let fixed = 0;
  for (const name of Object.keys(zip.files)) {
    if (!/^ppt\/(slides|slideLayouts|slideMasters)\/[^/]+\.xml$/.test(name)) continue;
    const xml = await zip.file(name).async("string");
    const out = xml.replace(/<a:p>([\s\S]*?)<\/a:p>/g, (m, inner) => {
      let first = true;
      const inner2 = inner.replace(/<a:pPr\b[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g, (pm) => {
        if (first) {
          first = false;
          return pm;
        }
        fixed++;
        return "";
      });
      return `<a:p>${inner2}</a:p>`;
    });
    if (out !== xml) zip.file(name, out);
  }
  // cores do tema (mesmo que o apply_theme do skill; garante o tema mesmo sem ele)
  const tname = "ppt/theme/theme1.xml";
  const txml = await zip.file(tname).async("string");
  const slots = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"];
  const scheme = `<a:clrScheme name="${THEME.name}">` + slots.map((k) => `<a:${k}><a:srgbClr val="${THEME.colors[k]}"/></a:${k}>`).join("") + "</a:clrScheme>";
  zip.file(tname, txml.replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme));
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  console.log(`pós-processamento: ${fixed} <a:pPr> repetidos removidos`);
}

function tagWidth(title, st) {
  // largura estimada do texto em Segoe UI negrito + respiro; conferida no HTML (data-tag)
  return Math.min(10, st.x + title.length * st.size * 0.0071 + 0.45);
}

// =========================================================================================
// SAÍDA 2: HTML (mesmas coordenadas) para imprimir em PDF e conferir
// =========================================================================================
const PX = 96;
const px = (inch) => (inch * PX).toFixed(2) + "px";
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const fileUrl = (p) => "file:///" + p.replace(/\\/g, "/").split("/").map((seg, i) => (i === 0 ? seg : encodeURIComponent(seg))).join("/");

function htmlRuns(ps, st) {
  return ps.map((p) => {
    const spans = p.runs.map((r) => {
      const weight = r.b ? 700 : r.font === "semi" ? 600 : 400;
      return `<span style="font-size:${r.size}pt;color:${hc(r.c)};font-weight:${weight};${r.i ? "font-style:italic;" : ""}">${esc(r.t) || "&#8203;"}</span>`;
    }).join("");
    const first = p.runs[0];
    const bullet = p.bullet ? ` class="bl" style="padding-left:${p.indent}pt;--bsz:${first.size}pt;--bcol:${hc(first.c)};margin:${p.sb}pt 0 ${p.sa}pt 0"` : ` style="margin:${p.sb}pt 0 ${p.sa}pt 0"`;
    return `<p${bullet}>${spans}</p>`;
  }).join("");
}

function htmlText(x, y, w, h, ps, st, extraCls = "") {
  const [l, r, b, t] = padArr(st.pad);
  const jc = { top: "flex-start", middle: "center", bottom: "flex-end" }[st.valign || "top"];
  const bg = st.fill ? `background:${hc(st.fill)};` : "";
  return `<div class="tx ${extraCls}" style="left:${px(x)};top:${px(y)};width:${px(w)};height:${px(h)};padding:${t}pt ${r}pt ${b}pt ${l}pt;justify-content:${jc};text-align:${st.align || "left"};${bg}"><div class="in">${htmlRuns(ps, st)}</div></div>`;
}

function htmlTable(e) {
  const st = e.st;
  const cols = e.colW.map((w) => `<col style="width:${px(w)}">`).join("");
  const rows = e.rows.map((row, ri) => {
    const isHeader = !st.noHeader && ri === 0;
    const dataIdx = st.noHeader ? ri : ri - 1;
    const tds = row.map((c, ci) => {
      const cell = typeof c === "string" ? { t: c } : c;
      const bold = isHeader || (st.firstColBold && ci === 0);
      const ps = paras([{ t: cell.t, b: bold }], { size: st.size || 12, color: isHeader ? "white" : "ink" });
      let fill = isHeader ? hx("ink") : dataIdx % 2 === 0 ? hx("zebra") : hx("white");
      if (cell.fill) fill = hx(cell.fill);
      const align = ci === 0 ? "left" : st.align || "left";
      return `<td style="background:#${fill};text-align:${align};height:${px(st.rowH || 0.4)}">${htmlRuns(ps, {})}</td>`;
    }).join("");
    return `<tr>${tds}</tr>`;
  }).join("");
  const w = e.colW.reduce((a, b) => a + b, 0);
  return `<table class="tb" style="left:${px(e.x)};top:${px(e.y)};width:${px(w)}"><colgroup>${cols}</colgroup>${rows}</table>`;
}

function htmlLine(e) {
  const c = hc(e.st.color || "rule");
  const id = "a" + Math.random().toString(36).slice(2, 8);
  const marker = e.st.arrow ? `<defs><marker id="${id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="3" markerHeight="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker></defs>` : "";
  const sw = ((e.st.w || 1) * 96) / 72;
  return `<svg class="ln" width="960" height="540" viewBox="0 0 960 540">${marker}<line x1="${e.x1 * PX}" y1="${e.y1 * PX}" x2="${e.x2 * PX}" y2="${e.y2 * PX}" stroke="${c}" stroke-width="${sw}"${e.st.arrow ? ` marker-end="url(#${id})"` : ""}/></svg>`;
}

function buildHtml(outFile) {
  const parts = [];
  slides.forEach((s, idx) => {
    const lay = LAYOUTS[s.layout];
    const els = [];
    if (lay.bgImage) els.push(`<img class="bg" src="${fileUrl(path.join(ASSETS, lay.bgImage))}">`);
    (lay.rects || []).forEach((r) => els.push(`<div class="sh" style="left:${px(r.x)};top:${px(r.y)};width:${px(r.w)};height:${px(r.h)};background:${hc(r.fill)}"></div>`));
    (lay.images || []).forEach((im) => {
      const sz = pngSize(path.join(ASSETS, im.file));
      els.push(`<img class="im" src="${fileUrl(path.join(ASSETS, im.file))}" style="left:${px(im.x)};top:${px(im.y)};width:${px(im.w)};height:${px((im.w * sz.h) / sz.w)}">`);
    });
    if (s.layout === "ESCURO") {
      els.push(`<div class="sh tag" style="left:0;top:${px(lay.title.y)};width:${px(tagWidth(s.title, lay.title))};height:${px(lay.title.h)};background:${hc("red")}"></div>`);
    }
    if (lay.title && s.title) {
      const t = lay.title;
      els.push(htmlText(t.x, t.y, t.w, t.h, paras(s.title, { size: t.size, color: t.color, b: t.bold }), { align: t.align, valign: t.valign }, s.layout === "ESCURO" ? "ttl tagtitle" : "ttl"));
    }
    for (const e of s.els) {
      if (e.k === "rect" || e.k === "oval") {
        const border = e.st.line ? `box-shadow: inset 0 0 0 ${((e.st.lw || 1) * 96) / 72}px ${hc(e.st.line)};` : "";
        const rad = e.k === "oval" ? "border-radius:50%;" : "";
        els.push(`<div class="sh" style="left:${px(e.x)};top:${px(e.y)};width:${px(e.w)};height:${px(e.h)};background:${hc(e.st.fill || "gray")};${border}${rad}"></div>`);
      } else if (e.k === "line") els.push(htmlLine(e));
      else if (e.k === "img") els.push(`<img class="im" src="${fileUrl(path.join(ASSETS, e.file))}" style="left:${px(e.x)};top:${px(e.y)};width:${px(e.w)};height:${px(e.h)}">`);
      else if (e.k === "text") els.push(htmlText(e.x, e.y, e.w, e.h, e.paras, e.st));
      else if (e.k === "table") els.push(htmlTable(e));
    }
    if (lay.num) els.push(htmlText(NUM_BOX.x, NUM_BOX.y, NUM_BOX.w, NUM_BOX.h, paras(String(idx + 1), { size: NUM_BOX.size, color: lay.num }), { align: "right" }, "num"));
    const bg = lay.bgColor ? hc(lay.bgColor) : "#ffffff";
    parts.push(`<section class="slide" data-n="${idx + 1}" style="background:${bg}">${els.join("")}</section>`);
  });
  const css = `
@page { size: 10in 5.625in; margin: 0; }
html, body { margin: 0; padding: 0; background: #ffffff; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", sans-serif; color: #231F20; }
.slide { position: relative; width: 960px; height: 540px; overflow: hidden; page-break-after: always; break-after: page; }
.slide:last-child { page-break-after: auto; break-after: auto; }
.bg { position: absolute; left: 0; top: 0; width: 960px; height: 540px; }
.sh, .im, .tx, .tb, .ln { position: absolute; }
.ln { left: 0; top: 0; overflow: visible; }
.tx { display: flex; flex-direction: column; overflow: visible; }
.tx p { margin: 0; line-height: normal; }
.tx p.bl { position: relative; }
.tx p.bl::before { content: "\\2022"; position: absolute; left: 0; font-size: var(--bsz); color: var(--bcol); }
.tb { border-collapse: collapse; table-layout: fixed; }
.tb td { border: 0.75pt solid #D0D0D0; padding: 3pt 5pt; vertical-align: middle; }
.tb td p { margin: 0; line-height: normal; }
body.qa .tx.over, body.qa .tb.over { outline: 2px solid #00B0F0; }
`;
  const qa = `
<script>
(function () {
  if (location.hash !== "#qa") return;
  document.body.classList.add("qa");
  var res = [];
  document.querySelectorAll(".slide").forEach(function (sl) {
    var n = sl.getAttribute("data-n");
    var sr = sl.getBoundingClientRect();
    sl.querySelectorAll(".tx").forEach(function (el) {
      var inn = el.firstElementChild, cs = getComputedStyle(el);
      var availH = el.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
      var availW = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      var ratio = inn.scrollHeight / Math.max(availH, 1);
      var r = el.getBoundingClientRect();
      var txt = el.textContent.slice(0, 60);
      if (inn.scrollHeight > availH + 1 || inn.scrollWidth > availW + 1) { el.classList.add("over"); res.push({ n: n, kind: "TRANSBORDA", ratio: +ratio.toFixed(2), text: txt }); }
      else if (ratio > 0.9 && availH > 30) res.push({ n: n, kind: "apertado", ratio: +ratio.toFixed(2), text: txt });
      if (r.right > sr.right + 1 || r.bottom > sr.bottom + 1 || r.left < sr.left - 1) res.push({ n: n, kind: "FORA DO SLIDE", text: txt });
    });
    sl.querySelectorAll(".tb").forEach(function (t) {
      var r = t.getBoundingClientRect();
      if (r.bottom > sr.bottom - 10) { t.classList.add("over"); res.push({ n: n, kind: "TABELA PERTO DA BORDA", bottom: Math.round(r.bottom - sr.top) }); }
      res.push({ n: n, kind: "tabela", bottom_in: +((r.bottom - sr.top) / 96).toFixed(2) });
    });
    var tg = sl.querySelector(".tag"), tt = sl.querySelector(".tagtitle");
    if (tg && tt) {
      var span = tt.querySelector("span"), sw = span.getBoundingClientRect();
      var tr = tg.getBoundingClientRect();
      res.push({ n: n, kind: "etiqueta", folga_in: +((tr.right - sw.right) / 96).toFixed(2) });
    }
  });
  var pre = document.createElement("pre"); pre.id = "qa"; pre.textContent = JSON.stringify(res); document.body.appendChild(pre);
})();
</script>`;
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Apresentação TAES</title><style>${css}</style></head><body>${parts.join("\n")}${qa}</body></html>`;
  fs.writeFileSync(outFile, html, "utf8");
  console.log("html:", outFile);
}

function writeNotes() {
  const notes = slides.map((s, i) => ({
    n: i + 1,
    titulo: s.title,
    secao: s.section,
    apresentador: s.presenter ? NOMES[s.presenter - 1] : "",
    bloco: s.presenter || 0,
    tempo: s.time,
    notas: s.notes,
  }));
  const f = path.join(HERE, "notas.json");
  fs.writeFileSync(f, JSON.stringify({ nomes: NOMES, tempos: TEMPOS, slides: notes }, null, 1), "utf8");
  console.log("notas:", f, notes.length, "slides");
}

(async () => {
  if (OUT_HTML) buildHtml(OUT_HTML);
  writeNotes();
  await buildPptx();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
