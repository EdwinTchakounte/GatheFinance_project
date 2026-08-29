#!/usr/bin/env python3
"""Captures tablettes Play Store (7 pouces + 10 pouces) pour GATHE Finance.
Reprend le cadrage brandé et met la capture téléphone en situation sur un
canevas au format tablette. Sortie : graphiques/screenshots/tablet-7 et tablet-10.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = "/home/tchakounte/Desktop/Gathe_finance"
OUT = os.path.join(ROOT, "playstore", "graphiques", "screenshots")
SORA = os.path.join(ROOT, "mobile/assets/fonts/Sora.ttf")
INTER = os.path.join(ROOT, "mobile/assets/fonts/Inter.ttf")
BLUE = (14, 77, 146); GREEN = (16, 163, 127); GREY = (240, 244, 243)

def font(p, s): return ImageFont.truetype(p, s)

def rounded(im, rad):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.size[0], im.size[1]], rad, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.paste(im, (0, 0), mask); return out

def vgrad(w, h, top, bot):
    base = Image.new("RGB", (w, h), top); ov = Image.new("RGB", (w, h), bot)
    mask = Image.new("L", (w, h)); md = mask.load()
    for y in range(h):
        v = int(255 * y / h)
        for x in range(w): md[x, y] = v
    base.paste(ov, (0, 0), mask); return base

SHOTLIST = [
    ("docs/captures/mobile-live/actif/01-accueil.png", "Tout votre patrimoine", "en un coup d'œil", ["Épargne, collectes et crédit réunis", "Solde en temps réel"]),
    ("docs/captures/mobile-live/actif/05-credit.png", "Trois voies de crédit", "un comité à votre écoute", ["Ancienneté, avaliste, garantie, campagne", "Suivi de bout en bout"]),
    ("docs/captures/mobile-live/actif/03-verser.png", "Épargnez librement", "ou placez votre argent", ["Versement sécurisé", "Retrait à tout moment"]),
]

# (dossier, largeur, hauteur) : 7" ~ 1200x1920, 10" ~ 1600x2560 (ratio 1:1.6)
FORMATS = [("tablet-7", 1200, 1920), ("tablet-10", 1600, 2560)]

for folder, CW, CH in FORMATS:
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    for i, (rel, l1, l2, bullets) in enumerate(SHOTLIST, 1):
        canvas = vgrad(CW, CH, (255, 255, 255), GREY).convert("RGBA")
        d = ImageDraw.Draw(canvas)
        m = CW / 1200.0
        # titre
        d.text((int(80*m), int(90*m)), l1, font=font(SORA, int(66*m)), fill=BLUE)
        d.text((int(80*m), int(175*m)), l2, font=font(SORA, int(66*m)), fill=BLUE)
        d.rounded_rectangle([int(82*m), int(270*m), int(240*m), int(284*m)], int(7*m), fill=GREEN)
        # bullets
        by = int(330*m)
        for b in bullets:
            d.ellipse([int(84*m), by+int(10*m), int(104*m), by+int(30*m)], fill=GREEN)
            d.text((int(122*m), by), b, font=font(INTER, int(30*m)), fill=(60, 74, 88))
            by += int(52*m)
        # capture centree
        shot = Image.open(os.path.join(ROOT, rel)).convert("RGBA")
        shot = shot.crop((0, 74, shot.width, shot.height))
        th = int(CH * 0.66); tw = int(shot.width * th / shot.height)
        shot = shot.resize((tw, th), Image.LANCZOS)
        shot = rounded(shot, int(46*m))
        px = (CW - tw) // 2; py = int(CH * 0.30)
        sh = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([px, py, px+tw, py+th], int(46*m), fill=(14, 77, 146, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(int(34*m)))
        canvas.alpha_composite(sh)
        fr = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        ImageDraw.Draw(fr).rounded_rectangle([px-int(8*m), py-int(8*m), px+tw+int(8*m), py+th+int(8*m)], int(52*m), fill=(255, 255, 255, 255))
        canvas.alpha_composite(fr)
        canvas.alpha_composite(shot, (px, py))
        canvas.convert("RGB").save(os.path.join(OUT, folder, f"{i:02d}.png"))
        print(f"{folder}/{i:02d}.png ({CW}x{CH}) OK")
print("DONE")
