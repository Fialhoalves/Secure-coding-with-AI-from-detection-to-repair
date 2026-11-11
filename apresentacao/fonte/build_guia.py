"""Monta o guia de apresentação e estudo (HTML autocontido para imprimir em PDF com o Edge).

Junta três fontes:
  - guia.md: texto do guia; o marcador <!-- ROTEIRO --> recebe o roteiro slide a slide, e os blocos
    "::: slide N ... :::" trazem o material extra de cada slide;
  - notas.json: roteiro de fala de cada slide (o mesmo das notas do .pptx), gerado por build_slides.js;
  - o PDF dos slides: miniaturas de cada slide.

Uso: python -I build_guia.py <guia.md> <notas.json> <slides.pdf> <saida.html> [pasta_do_pypdfium2]
(o ultimo argumento so e preciso se o pypdfium2 estiver instalado fora do ambiente, numa pasta avulsa)
"""
import base64
import html
import io
import json
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

md_path, notes_path, slides_pdf, out_path = (Path(a) for a in sys.argv[1:5])
if len(sys.argv) > 5:
    sys.path.insert(0, sys.argv[5])
import pypdfium2 as pdfium  # noqa: E402

md = MarkdownIt("commonmark", {"html": False, "typographer": False}).enable("table")
text = md_path.read_text(encoding="utf-8")
notes = json.loads(notes_path.read_text(encoding="utf-8"))

# blocos extras por slide
extras = {}


def grab(m):
    extras[int(m.group(1))] = m.group(2).strip()
    return ""


text = re.sub(r"^::: slide (\d+)\n(.*?)\n:::\s*$", grab, text, flags=re.S | re.M)
text = text.replace("- [ ] ", "- ☐ ")

# miniaturas
doc = pdfium.PdfDocument(str(slides_pdf))
thumbs = []
for i in range(len(doc)):
    im = doc[i].render(scale=0.75).to_pil().convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True)
    thumbs.append(base64.b64encode(buf.getvalue()).decode("ascii"))
assert len(thumbs) == len(notes["slides"]), (len(thumbs), len(notes["slides"]))

BLOCOS = {
    1: "Bloco 1 · Contexto e auditoria",
    2: "Bloco 2 · Proposta e método",
    3: "Bloco 3 · Resultados",
    4: "Bloco 4 · Análises e conclusão",
    0: "Apêndice (para as perguntas)",
}


def roteiro():
    out = []
    last = None
    for s in notes["slides"]:
        b = s["bloco"]
        if b != last:
            who = f" · {notes['nomes'][b - 1]} · {notes['tempos'][b - 1]}" if b else ""
            out.append(f'<h3 class="bloco">{html.escape(BLOCOS[b] + who)}</h3>')
            last = b
        title = s["titulo"] or "Encerramento (marca do CIn)"
        if s["titulo"] == "RESULTADO":
            title = "Resultado em uma frase"
        meta = f"{s['apresentador']} · {s['tempo']}" if s["apresentador"] else "Usar só se houver pergunta"
        say = f'<p class="say"><strong>O que dizer.</strong> {html.escape(s["notas"])}</p>' if s["notas"] else ""
        extra = f'<div class="extra">{md.render(extras[s["n"]])}</div>' if s["n"] in extras else ""
        out.append(
            f'<section class="entry"><div class="row"><img class="thumb" src="data:image/jpeg;base64,{thumbs[s["n"] - 1]}">'
            f'<div class="body"><h4>Slide {s["n"]} · {html.escape(title)}</h4><p class="meta">{html.escape(meta)}</p>{say}</div></div>{extra}</section>'
        )
    return "\n".join(out)


before, after = text.split("<!-- ROTEIRO -->")
body = md.render(before) + roteiro() + md.render(after)

# capa: título e primeiro parágrafo
body = re.sub(r"^<h1>(.*?)</h1>\n<p>(.*?)</p>", r'<header class="capa"><h1>\1</h1><p>\2</p></header>', body, count=1, flags=re.S)

css = """
@page {
  size: A4;
  margin: 17mm 16mm 18mm 16mm;
  @bottom-center { content: "Página " counter(page) " de " counter(pages); font: 8pt "Segoe UI", sans-serif; color: #595959; }
  @top-right { content: "Guia de apresentação e estudo · Projeto TAES"; font: 7.5pt "Segoe UI", sans-serif; color: #8C8C8C; }
}
@page :first { @top-right { content: none; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Segoe UI", sans-serif; font-size: 10pt; line-height: 1.45; color: #231F20; margin: 0; }
.capa { background: #DB1E2F; color: #fff; padding: 14mm 12mm 11mm 12mm; margin: 0 0 8mm 0; }
.capa h1 { font-size: 26pt; line-height: 1.15; margin: 0 0 5mm 0; color: #fff; }
.capa p { font-size: 11pt; margin: 0; color: #fff; }
.capa strong { color: #fff; }
h2 { font-size: 17pt; color: #DB1E2F; margin: 0 0 4mm 0; padding-top: 1mm; break-before: page; break-after: avoid; }
.capa + h2 { break-before: auto; }
h3 { font-size: 12.5pt; color: #231F20; margin: 6mm 0 2mm 0; break-after: avoid; }
h3.bloco { background: #231F20; color: #fff; padding: 2.2mm 3mm; margin: 6mm 0 3mm 0; font-size: 11.5pt; }
h4 { font-size: 11pt; color: #DB1E2F; margin: 0 0 0.6mm 0; }
p { margin: 0 0 2.4mm 0; }
ul, ol { margin: 0 0 2.4mm 0; padding-left: 6mm; }
li { margin: 0 0 1mm 0; }
blockquote { margin: 2mm 0 4mm 0; padding: 3mm 5mm; background: #FBE3E5; border: none; font-size: 11.5pt; }
blockquote p { margin: 0; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.8pt; background: #F2F2F2; padding: 0 2px; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm 0; font-size: 8.8pt; line-height: 1.35; }
th, td { border: 0.6pt solid #D0D0D0; padding: 1.6mm 2mm; vertical-align: top; text-align: left; }
th { background: #231F20; color: #fff; font-weight: 600; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
tbody tr:nth-child(even) td { background: #F6F6F6; }
.entry { border-top: 0.8pt solid #D0D0D0; padding: 3mm 0 1mm 0; }
.entry .row { display: flex; gap: 5mm; align-items: flex-start; break-inside: avoid; }
.entry .extra p, .entry .extra li, .entry .extra table { break-inside: avoid; }
.entry .thumb { width: 64mm; flex: none; border: 0.6pt solid #BFBFBF; }
.entry .body { flex: 1; }
.entry .meta { color: #595959; font-size: 9pt; margin: 0 0 1.5mm 0; }
.entry .say { font-size: 9.6pt; }
.entry .extra { margin: 2mm 0 0 0; font-size: 9.4pt; }
.entry .extra table { font-size: 8.4pt; }
strong { font-weight: 700; }
"""
doc_html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Guia de apresentação e estudo · Projeto TAES</title>
<style>{css}</style></head><body>
{body}
</body></html>
"""
out_path.write_text(doc_html, encoding="utf-8")
print(f"html: {out_path} ({out_path.stat().st_size / 1e6:.2f} MB); extras para {len(extras)} slides")
