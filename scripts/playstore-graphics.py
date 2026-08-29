#!/usr/bin/env python3
"""Génère les assets graphiques Play Store pour GATHE Finance.
- icone-512.png            (512×512, depuis app_icon 1024)
- feature-graphic-1024x500.png
- screenshots/*.png         (captures device encadrées + titre)
Palette de marque : bleu #0E4D92 / #0747FF, vert #10A37F / #33FF00, gris #F0F4F3.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = "/home/tchakounte/Desktop/Gathe_finance"
OUT = os.path.join(ROOT, "playstore", "graphiques")
SHOTS = os.path.join(OUT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)

SORA = os.path.join(ROOT, "mobile/assets/fonts/Sora.ttf")
INTER = os.path.join(ROOT, "mobile/assets/fonts/Inter.ttf")

BLUE = (14, 77, 146)       # #0E4D92
BLUE2 = (7, 71, 255)       # #0747FF
GREEN = (16, 163, 127)     # #10A37F
GREY = (240, 244, 243)     # #F0F4F3
INK = (18, 32, 47)

def font(path, size):
    return ImageFont.truetype(path, size)

def rounded(im, rad):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.size[0], im.size[1]], rad, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out

def vgrad(w, h, top, bot):
    base = Image.new("RGB", (w, h), top)
    top_im = Image.new("RGB", (w, h), bot)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        v = int(255 * y / h)
        for x in range(w):
            md[x, y] = v
    base.paste(top_im, (0, 0), mask)
    return base

def diag_grad(w, h, c1, c2):
    base = Image.new("RGB", (w, h), c1)
    ov = Image.new("RGB", (w, h), c2)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        for x in range(w):
            md[x, y] = int(255 * ((x / w) * 0.6 + (y / h) * 0.4))
    base.paste(ov, (0, 0), mask)
    return base

# ---------- 1. Icône 512 ----------
icon = Image.open(os.path.join(ROOT, "mobile/assets/images/app_icon.png")).convert("RGBA")
icon512 = icon.resize((512, 512), Image.LANCZOS)
bg = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
bg.alpha_composite(icon512)
bg.convert("RGB").save(os.path.join(OUT, "icone-512.png"))
print("icone-512.png OK")

# ---------- 2. Feature graphic 1024×500 ----------
W, H = 1024, 500
fg = diag_grad(W, H, BLUE, BLUE2).convert("RGBA")
d = ImageDraw.Draw(fg)
# halo vert décoratif
halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
hd = ImageDraw.Draw(halo)
hd.ellipse([W - 360, -160, W + 120, 320], fill=(51, 255, 0, 60))
halo = halo.filter(ImageFilter.GaussianBlur(80))
fg.alpha_composite(halo)
d = ImageDraw.Draw(fg)
# badge icône à droite
badge = rounded(icon.resize((260, 260), Image.LANCZOS), 58)
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle([W - 330, 118, W - 70, 378], 58, fill=(0, 0, 0, 90))
shadow = shadow.filter(ImageFilter.GaussianBlur(24))
fg.alpha_composite(shadow)
fg.alpha_composite(badge, (W - 330, 120))
# texte
d.text((70, 150), "GATHE Finance", font=font(SORA, 78), fill=(255, 255, 255))
d.text((72, 250), "Votre coopérative d'épargne", font=font(INTER, 34), fill=(220, 232, 245))
d.text((72, 296), "et de crédit, dans la poche.", font=font(INTER, 34), fill=(220, 232, 245))
# pastille verte
d.rounded_rectangle([74, 372, 386, 430], 29, fill=(51, 255, 0))
d.text((100, 385), "Épargne · Crédit · Collecte", font=font(SORA, 26), fill=(6, 40, 20))
fg.convert("RGB").save(os.path.join(OUT, "feature-graphic-1024x500.png"))
print("feature-graphic-1024x500.png OK")

# ---------- 3. Screenshots encadrés ----------
SHOTLIST = [
    ("docs/captures/mobile-live/actif/01-accueil.png", "Tout votre patrimoine,", "en un coup d'œil"),
    ("docs/captures/mobile-live/actif/03-verser.png", "Épargnez librement", "ou placez votre argent"),
    ("docs/captures/mobile-live/actif/05-credit.png", "Trois voies de crédit,", "un comité à votre écoute"),
    ("docs/captures/mobile-live/actif/02-transfert.png", "Remboursez votre crédit", "en un seul geste"),
    ("docs/captures/mobile-live/suspendu/05-annonces.png", "Restez informé", "des annonces de la coopérative"),
    ("docs/captures/mobile-live/actif/06-profil.png", "Votre compte,", "sécurisé par code PIN"),
]

CW, CH = 1080, 2160  # ratio exact 2:1 (max autorisé par Google Play)
for i, (rel, l1, l2) in enumerate(SHOTLIST, 1):
    canvas = vgrad(CW, CH, (255, 255, 255), GREY).convert("RGBA")
    d = ImageDraw.Draw(canvas)
    # bande titre
    d.text((70, 120), l1, font=font(SORA, 62), fill=BLUE)
    d.text((70, 200), l2, font=font(SORA, 62), fill=BLUE)
    d.rounded_rectangle([72, 300, 220, 314], 7, fill=GREEN)
    # capture (rogne 46px de barre de statut en haut)
    shot = Image.open(os.path.join(ROOT, rel)).convert("RGBA")
    shot = shot.crop((0, 74, shot.width, shot.height))
    tw = 760
    th = int(shot.height * tw / shot.width)
    shot = shot.resize((tw, th), Image.LANCZOS)
    shot = rounded(shot, 46)
    px = (CW - tw) // 2
    py = 380
    # ombre portée
    sh = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([px, py, px + tw, py + th], 46, fill=(14, 77, 146, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(34))
    canvas.alpha_composite(sh)
    # cadre blanc fin
    fr = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle([px - 8, py - 8, px + tw + 8, py + th + 8], 52, fill=(255, 255, 255, 255))
    canvas.alpha_composite(fr)
    canvas.alpha_composite(shot, (px, py))
    canvas.convert("RGB").save(os.path.join(SHOTS, f"{i:02d}.png"))
    print(f"screenshots/{i:02d}.png OK")

print("DONE")
