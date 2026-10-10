"""Link-preview image for the predictor (og:image, 1200 × 630): our own graphic, no numbers, so it
never goes stale (the live chances are in the page and its description). Fonts: DejaVu Sans (free
licence), passed with --fonts because the NAS has none installed.

    python3 cricstat/tools/gen_og_card.py --fonts DIR     # → staging/web/og/predictor.png
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "staging", "web", "og", "predictor.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True, help="folder with DejaVuSans.ttf and DejaVuSans-Bold.ttf")
    a = ap.parse_args()
    B = lambda n: ImageFont.truetype(os.path.join(a.fonts, "DejaVuSans-Bold.ttf"), n)  # noqa: E731
    R = lambda n: ImageFont.truetype(os.path.join(a.fonts, "DejaVuSans.ttf"), n)       # noqa: E731
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), "#0d0f14")
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([-250, -300, 650, 380], fill=(19, 71, 163))
    g.ellipse([700, 300, 1450, 900], fill=(120, 60, 10))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(160)), 0.35)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([24, 24, W - 24, H - 24], 22, outline="#2a2f3d", width=2)
    SAFF, GOLD, DIM = "#FF9933", "#F5B82E", "#94a3b8"
    d.text((70, 70), "CRICKET WORLD CUP 2027  ·  PREDICTION", font=B(22), fill=SAFF)
    d.text((70, 112), "Who will win?", font=B(76), fill="#ffffff")
    d.text((70, 206), "Every team's chances, updated daily.", font=B(40), fill="#e2e8f0")
    # simple trophy in gold
    tx, ty = 1010, 120
    d.pieslice([tx - 70, ty - 40, tx + 70, ty + 120], 0, 180, fill=GOLD)
    d.rectangle([tx - 70, ty - 40, tx + 70, ty + 40], fill=GOLD)
    d.arc([tx - 115, ty - 30, tx - 45, ty + 60], 90, 270, fill=GOLD, width=10)
    d.arc([tx + 45, ty - 30, tx + 115, ty + 60], 270, 90, fill=GOLD, width=10)
    d.rectangle([tx - 10, ty + 118, tx + 10, ty + 160], fill=GOLD)
    d.rounded_rectangle([tx - 55, ty + 158, tx + 55, ty + 182], 6, fill=GOLD)
    for i, (big, small) in enumerate([("cricstat Elo", "our own team rating, every men's ODI since 2002"),
                                      ("50,000", "simulated tournaments in the published format"),
                                      ("900 ODIs", "backtested before they were played")]):
        y = 312 + i * 72
        d.text((70, y), big, font=B(34), fill=GOLD)
        d.text((70 + d.textlength(big, font=B(34)) + 18, y + 10), small, font=R(22), fill=DIM)
    d.text((70, 548), "cric", font=B(34), fill="#ffffff")
    cw = d.textlength("cric", font=B(34))
    d.text((70 + cw, 548), "stat", font=B(34), fill=SAFF)
    sw = d.textlength("stat", font=B(34))
    d.text((70 + cw + sw + 20, 558), "pandyahomelab.com/cricket/predictor  ·  not betting advice", font=R(22), fill=DIM)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)
    print(OUT, os.path.getsize(OUT))


if __name__ == "__main__":
    main()
