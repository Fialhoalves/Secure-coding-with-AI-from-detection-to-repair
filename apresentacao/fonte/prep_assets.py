"""Gera os fundos e logos dos slides a partir das imagens do modelo "Apresentação Padrão CIn-UFPE.pdf".

Uso (na raiz do projeto): pipeline\\.venv\\Scripts\\python.exe -I apresentacao\\fonte\\prep_assets.py <pasta_imagens_do_modelo>
A pasta de entrada tem as imagens extraídas do PDF do modelo (p1_Image2.png, p4_Image10.png, p6_Image13.png,
p13_Image15.png, p14_Image22.png). Saída: apresentacao/fonte/assets/*.png (1920 x 1080 = 10 x 5,625 pol a 192 dpi).
Também recorta o painel da regra estrita da Figura 1 do relatório.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SRC = Path(sys.argv[1])
HERE = Path(__file__).resolve().parent
OUT = HERE / "assets"
ROOT = HERE.parents[1]
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080
PX_IN = W / 10  # 192 px por polegada

RED = (0xDB, 0x1E, 0x2F)
GRAY = (0xEE, 0xEE, 0xEE)
WHITE = (255, 255, 255)


def load(name):
    im = Image.open(SRC / f"{name}.png").convert("RGBA")
    return im.crop(im.getchannel("A").getbbox())


def components_bbox(im):
    """Separa a gota (componente de cima) da onda; devolve a bbox da gota."""
    a = im.getchannel("A").point(lambda v: 255 if v > 0 else 0)
    w, h = a.size
    # a gota termina na primeira faixa horizontal vazia depois do topo
    rows = [a.crop((0, y, w, y + 1)).getbbox() is not None for y in range(h)]
    y_end = next(y for y in range(1, h) if rows[y - 1] and not rows[y])
    return a.crop((0, 0, w, y_end)).getbbox()


def place_swoosh(canvas, sw, drop_left, drop_bottom, drop_width, clip=None):
    gx0, gy0, gx1, gy1 = components_bbox(sw)
    s = drop_width / (gx1 - gx0)
    sw2 = sw.resize((round(sw.width * s), round(sw.height * s)), Image.LANCZOS)
    ox = round(drop_left - gx0 * s)
    oy = round(drop_bottom - gy1 * s)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.alpha_composite(sw2, (max(ox, 0), max(oy, 0)), (max(-ox, 0), max(-oy, 0)))
    if clip:
        mask = Image.new("L", canvas.size, 0)
        ImageDraw.Draw(mask).rectangle(clip, fill=255)
        layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", canvas.size, 0), mask))
    canvas.alpha_composite(layer)


def save(im, name):
    im.convert("RGB").save(OUT / name, optimize=True)
    print(name, im.size)


sw35 = load("p4_Image10")      # "i" branco a ~35% (capa)
sw_faint = load("p6_Image13")  # "i" branco quase transparente (divisores)
i_white = load("p13_Image15")  # "i" branco sólido
logo_white = load("p1_Image2")
logo_red = load("p14_Image22")

# capa: vermelho + "i" saindo pela esquerda e por baixo (modelo, página 4); opacidade reduzida à metade
# para o texto branco por cima continuar legível
c = Image.new("RGBA", (W, H), RED + (255,))
sw_capa = sw35.copy()
sw_capa.putalpha(sw35.getchannel("A").point(lambda v: v // 2))
place_swoosh(c, sw_capa, drop_left=206, drop_bottom=314, drop_width=337)
save(c, "bg_capa.png")

# divisor de bloco: painel vermelho à esquerda com "i" bem suave e área cinza à direita (modelo, página 6)
c = Image.new("RGBA", (W, H), GRAY + (255,))
panel_w = round(W * 598 / 1008)
ImageDraw.Draw(c).rectangle((0, 0, panel_w - 1, H), fill=RED)
place_swoosh(c, sw_faint, drop_left=476, drop_bottom=352, drop_width=295, clip=(0, 0, panel_w - 1, H))
save(c, "bg_divisor.png")

# frase-resumo: vermelho com arco branco fino (modelo, página 7)
S = 2
c = Image.new("RGBA", (W * S, H * S), RED + (255,))
cx, cy, r = 0.4456 * PX_IN * S, 2.81 * PX_IN * S, 3.784 * PX_IN * S
ImageDraw.Draw(c).ellipse((cx - r, cy - r, cx + r, cy + r), outline=WHITE, width=3 * S)
c = c.resize((W, H), Image.LANCZOS)
save(c, "bg_circulo.png")

# encerramento: painel vermelho à esquerda com o "i" branco (modelo, página 13)
c = Image.new("RGBA", (W, H), WHITE + (255,))
panel_w = round(W * 411 / 1008)
ImageDraw.Draw(c).rectangle((0, 0, panel_w - 1, H), fill=RED)
iw = round(W * 75 / 1008)
ii = i_white.resize((iw, round(i_white.height * iw / i_white.width)), Image.LANCZOS)
c.alpha_composite(ii, (round(panel_w / 2 - iw / 2), round(H * 140 / 567)))
save(c, "bg_fim.png")

# última página: fundo branco com a marca do CIn (modelo, página 14)
c = Image.new("RGBA", (W, H), WHITE + (255,))
lw = round(W * 0.62)
lr = logo_red.resize((lw, round(logo_red.height * lw / logo_red.width)), Image.LANCZOS)
c.alpha_composite(lr, (round((W - lw) / 2), round((H - lr.height) / 2)))
save(c, "bg_logo.png")

# marca branca para a capa (imagem separada, com transparência)
lw = 700
logo_white.resize((lw, round(logo_white.height * lw / logo_white.width)), Image.LANCZOS).save(OUT / "logo_branco.png", optimize=True)
print("logo_branco.png")

# Figura 1 do relatório: só o painel da regra estrita (metade esquerda, sem a legenda de baixo)
f1 = Image.open(ROOT / "pipeline" / "results" / "figs" / "fig1_recall_vs_falsos_alarmes.png").convert("RGB")
fw, fh = f1.size
crop = f1.crop((0, 0, round(fw * 0.50), round(fh * 0.925)))
crop.save(OUT / "fig_h4.png", optimize=True)
print("fig_h4.png", crop.size)
