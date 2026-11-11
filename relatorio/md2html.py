"""RELATORIO.md -> HTML autocontido (figuras em base64) com estilo de documento A4, para imprimir em PDF com o Edge headless.

Uso: python -I md2html.py <RELATORIO.md> <saida.html>
"""
import base64
import html
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

src, out = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(encoding="utf-8")

md = MarkdownIt("commonmark", {"html": False, "typographer": False}).enable("table")
body = md.render(text)


def embed(m: re.Match) -> str:
    rel = html.unescape(m.group(1))
    p = (src.parent / rel).resolve()
    if not p.is_file():
        raise SystemExit(f"figura nao encontrada: {p}")
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return f'src="data:image/png;base64,{data}"'


body = re.sub(r'src="([^"]+\.png)"', embed, body)
# figura: imagem e legenda (o paragrafo em negrito "Figura N." logo antes) ficam juntas na mesma pagina
body = re.sub(r"<p><strong>(Figura \d+\.)</strong>(.*?)\n<img ([^>]*)></p>",
              r'<figure><figcaption><strong>\1</strong>\2</figcaption><img \3></figure>', body, flags=re.S)

title = "Verificação adversarial com 3 agentes para reduzir falsos positivos — relatório TAES"
css = """
@page {
  size: A4;
  margin: 18mm 15mm 18mm 15mm;
  @bottom-center { content: "Página " counter(page) " de " counter(pages); font: 8pt "Segoe UI", sans-serif; color: #666; }
  @top-right { content: "Projeto TAES — Belozerov et al. (2026), verificação adversarial"; font: 7.5pt "Segoe UI", sans-serif; color: #888; }
}
@page :first { @top-right { content: none; } }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Cambria, Georgia, "Times New Roman", serif; font-size: 10.5pt; line-height: 1.42; color: #1a1a1a; margin: 0; }
h1 { font-family: "Segoe UI", Calibri, sans-serif; font-size: 17pt; line-height: 1.25; margin: 0 0 8pt 0; color: #111; }
h2 { font-family: "Segoe UI", Calibri, sans-serif; font-size: 13pt; margin: 16pt 0 6pt 0; padding-bottom: 2pt; border-bottom: 1px solid #bbb;
     break-after: avoid; page-break-after: avoid; }
h3 { font-family: "Segoe UI", Calibri, sans-serif; font-size: 11pt; margin: 12pt 0 4pt 0; break-after: avoid; }
p { margin: 0 0 6pt 0; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 6pt 0; padding-left: 16pt; }
li { margin: 0 0 3pt 0; text-align: justify; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.8pt; background: #f2f2f2; padding: 0 2px; border-radius: 2px; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 9pt 0; font-family: "Segoe UI", Calibri, sans-serif; font-size: 8pt; line-height: 1.3; }
th, td { border: 0.6pt solid #b5b5b5; padding: 2.5pt 4pt; vertical-align: top; text-align: left; }
th { background: #e9edf2; font-weight: 600; }
tr { break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }
tbody tr:nth-child(even) td { background: #fafafa; }
td code, th code { font-size: 7.6pt; }
figure { margin: 6pt 0 10pt 0; break-inside: avoid; page-break-inside: avoid; }
figcaption { font-size: 9.5pt; margin-bottom: 4pt; text-align: left; }
img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
strong { font-weight: 700; }
/* primeira linha apos o titulo (referencia do artigo e estado) */
h1 + p { font-size: 9.5pt; color: #333; text-align: left; border-left: 3px solid #9fb3c8; padding-left: 7pt; }
"""
doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""
out.write_text(doc, encoding="utf-8")
print(f"html: {out} ({out.stat().st_size / 1e6:.2f} MB)")
