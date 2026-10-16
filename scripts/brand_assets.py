"""Временные ассеты FoxScanner из композитов бренда (design-src/*.jpg): маскот героя, логотип, иконки.
Когда будут отдельные экспорты (PNG/SVG) — положить их в static/img/ с теми же именами, скрипт больше не нужен.

    python scripts/brand_assets.py
"""
import base64, io, os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, IMG, STATIC = (os.path.join(ROOT, *p) for p in (("design-src",), ("static", "img"), ("static",)))
BG = (11, 11, 11)


def fade(im, edge):
    """Альфа-маска: края уходят в прозрачность (герой ложится на фон страницы без рамки)."""
    w, h = im.size
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((edge, edge, w - edge, h - edge), radius=edge * 2, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(edge * 0.6))
    out = im.convert("RGBA")
    out.putalpha(ImageChops.multiply(m, out.getchannel("A")))
    return out


def rounded(im, size, radius, bg=None):
    im = im.convert("RGBA").resize((size, size), Image.LANCZOS)
    if bg:
        tile = Image.new("RGBA", (size, size), bg)
        tile.alpha_composite(im)
        im = tile
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    im.putalpha(ImageChops.multiply(m, im.getchannel("A")))
    return im


def main():
    os.makedirs(IMG, exist_ok=True)
    landing = Image.open(os.path.join(SRC, "landing.jpg")).convert("RGB")
    sheet = Image.open(os.path.join(SRC, "brand-sheet.jpg")).convert("RGB")

    hero = landing.crop((495, 0, 775, 290)).resize((560, 580), Image.LANCZOS)
    fade(hero, 40).save(os.path.join(IMG, "mascot-hero.png"), optimize=True)

    mascot = sheet.crop((10, 10, 300, 236)).resize((580, 452), Image.LANCZOS)
    fade(mascot, 24).save(os.path.join(IMG, "mascot-banner.png"), optimize=True)

    logo = sheet.crop((525, 20, 690, 170))
    side = max(logo.size)
    sq = Image.new("RGB", (side, side), BG)
    sq.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
    rounded(sq, 160, 36).save(os.path.join(IMG, "logo.png"), optimize=True)

    fav = rounded(sq, 180, 40)
    fav.save(os.path.join(STATIC, "favicon.png"), optimize=True)
    buf = io.BytesIO()
    rounded(sq, 64, 14).save(buf, "PNG", optimize=True)
    with open(os.path.join(STATIC, "favicon.svg"), "w", encoding="utf-8") as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                'viewBox="0 0 64 64"><image width="64" height="64" xlink:href="data:image/png;base64,'
                + base64.b64encode(buf.getvalue()).decode() + '"/></svg>\n')

    sheet.crop((735, 300, 1020, 435)).save(os.path.join(SRC, "icons.png"))   # набор иконок — для справки
    print("ok:", sorted(os.listdir(IMG)))


if __name__ == "__main__":
    main()
