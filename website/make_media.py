#!/usr/bin/env python3
"""Make the website's pictures and trailer from the Steam kit.

    python3 website/make_media.py            # everything
    python3 website/make_media.py images     # pictures only
    python3 website/make_media.py trailer    # the web trailer only

Run it by hand when the Steam kit changes; the results in website/static/media
are committed, so the deploy itself needs neither Pillow nor ffmpeg.

Sources (all made by the game, see steam/):
  steam/assets/capsules/library_hero.png   the hero: the showcase tower at 2x
  steam/assets/capsules/library_logo.png   the title logo, transparent
  steam/assets/screenshots/*.jpg           1920x1080, interface on
  steam/trailer/*-express-small.mp4        the "Express to the Top" cut (git-ignored,
                                           made by steam/trailer/make3.py express)
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
STEAM = ROOT / "steam"
OUT = ROOT / "website" / "static" / "media"

# The trailer's end card says OUT NOW ON STEAM. Until that is true the web cut
# stops on the crown, just before it (the card starts at 65.7 s).
TRAILER = STEAM / "trailer" / "happy-highrise-launch-trailer-express-small.mp4"
TRAILER_END = 65.5
TRAILER_FADE = 0.8


def save_webp(im, path, quality=84):
    im.save(path, "WEBP", quality=quality, method=6)
    print(f"  {path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  {path.stat().st_size // 1024} KB")


def images():
    OUT.mkdir(parents=True, exist_ok=True)
    caps = STEAM / "assets" / "capsules"

    # The hero is drawn at 2x game pixels. Halving it with NEAREST gives the
    # exact 1x picture, a quarter of the bytes, and the browser scales it back
    # up with image-rendering: pixelated, so it stays crisp at any size.
    hero = Image.open(caps / "library_hero.png").convert("RGB")
    hero = hero.resize((hero.width // 2, hero.height // 2), Image.NEAREST)
    hero.save(OUT / "hero.png", optimize=True)
    print(f"  hero.png {hero.size}  {(OUT / 'hero.png').stat().st_size // 1024} KB")

    # The logo is painted, not on a pixel grid: scale it smoothly.
    logo = Image.open(caps / "library_logo.png").convert("RGBA")
    logo = logo.crop(logo.getbbox())
    save_webp(logo.resize((logo.width // 2, logo.height // 2), Image.LANCZOS), OUT / "logo.webp", 90)
    logo.resize((logo.width // 2, logo.height // 2), Image.LANCZOS).save(OUT / "logo.png", optimize=True)

    # Social preview (og:image): the header capsule is exactly what Steam shows.
    Image.open(caps / "header_capsule.png").convert("RGB").save(OUT / "og.jpg", quality=88)

    icons = STEAM / "assets" / "icons"
    icon = Image.open(icons / "client_icon_256.png").convert("RGBA")
    icon.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png", optimize=True)
    icon.resize((64, 64), Image.LANCZOS).save(OUT / "favicon.png", optimize=True)
    icon.save(OUT.parent / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    for src in sorted((STEAM / "assets" / "screenshots").glob("*.jpg")):
        im = Image.open(src).convert("RGB")
        save_webp(im, OUT / f"{src.stem}.webp", 82)
        save_webp(im.resize((960, 540), Image.LANCZOS), OUT / f"{src.stem}-960.webp", 82)


def trailer():
    if not TRAILER.exists():
        sys.exit(f"{TRAILER.relative_to(ROOT)} is missing: python3 steam/trailer/make3.py express")
    OUT.mkdir(parents=True, exist_ok=True)
    fade_at = TRAILER_END - TRAILER_FADE
    out = OUT / "trailer.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(TRAILER), "-t", str(TRAILER_END),
        "-vf", f"scale=1280:720:flags=lanczos,fade=t=out:st={fade_at}:d={TRAILER_FADE}",
        "-af", f"afade=t=out:st={fade_at}:d={TRAILER_FADE}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", str(out),
    ], check=True)
    print(f"  {out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB")
    # Poster: a gameplay frame, not the logo card.
    poster = OUT / "trailer-poster.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "13.5", "-i", str(TRAILER),
                    "-frames:v", "1", "-vf", "scale=1280:720:flags=lanczos", "-q:v", "3",
                    str(poster)], check=True)
    print(f"  {poster.relative_to(ROOT)}  {poster.stat().st_size // 1024} KB")


if __name__ == "__main__":
    what = sys.argv[1:] or ["images", "trailer"]
    if "images" in what:
        images()
    if "trailer" in what:
        trailer()
