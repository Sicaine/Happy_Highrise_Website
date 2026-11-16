#!/usr/bin/env python3
"""Build happy-highrise.com into a folder of static files.

    python3 website/build.py                 # -> .tmp/website
    python3 website/build.py --out _site     # what the deploy workflow does
    python3 -m http.server -d .tmp/website   # look at it on :8000

Standard library only. Every page is plain HTML, one stylesheet, one small
script that the page works without, and media served from the site itself:
no CDN, no fonts from elsewhere, no cookies, no tracking.

Words live in website/i18n/<lang>.json, one file per language. English is the
default and lives at /, every other language at /<lang>/. The build refuses
to run if a language file is missing a key the English one has (or has one
it does not), so a German page can never quietly fall back to English.

Facts that are the same in every language (the Steam app id, the release, a
contact address, the imprint) are in website/site.json.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STEAM = ROOT / "steam" / "assets"
YEAR = date.today().year


def esc(s):
    return html.escape(str(s), quote=True)


def fill(s, **kw):
    """Replace {{name}} in a translated string."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(kw.get(m.group(1), m.group(0))), s)


# ---------------------------------------------------------------- checks

# Keys that only one language has. The test-phase imprint is a German legal
# page and exists only in German; every language's footer links to it.
ONE_LANGUAGE = {"imprint_preview"}


def same_shape(a, b, where="", errors=None):
    """Two language files must have the same keys, list lengths and the same
    non-text values (screenshot ids, floor ids)."""
    errors = [] if errors is None else errors
    if isinstance(a, dict):
        if not isinstance(b, dict):
            errors.append(f"{where}: not an object")
            return errors
        for k in a.keys() - b.keys() - ONE_LANGUAGE:
            errors.append(f"{where}.{k}: missing")
        for k in b.keys() - a.keys() - ONE_LANGUAGE:
            errors.append(f"{where}.{k}: not in the English file")
        for k in a.keys() & b.keys():
            same_shape(a[k], b[k], f"{where}.{k}", errors)
    elif isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            errors.append(f"{where}: list length differs")
            return errors
        for i, (x, y) in enumerate(zip(a, b)):
            same_shape(x, y, f"{where}[{i}]", errors)
    elif where.endswith((".id", ".shots[0]", ".shots[1]", ".shots[2]", ".shots[3]")) and a != b:
        errors.append(f"{where}: {b!r} should be {a!r} (not translated)")
    return errors


# ---------------------------------------------------------------- pieces

class Site:
    def __init__(self, out):
        self.out = out
        self.cfg = json.loads((HERE / "site.json").read_text())
        self.langs = {code: json.loads((HERE / "i18n" / f"{code}.json").read_text())
                      for code in self.cfg["langs"]}
        self.default = self.cfg["default_lang"]
        self.base = f"https://{self.cfg['domain']}/"
        self.warnings = []
        self.pages = []  # (lang, key, path) for the sitemap and hreflang

    # paths -------------------------------------------------------------

    def path(self, code, key):
        """The site-relative directory of a page, '' for the English home."""
        t = self.langs[code]
        prefix = t["path"]
        if key == "home":
            return prefix
        if key == "imprint" and code not in self.imprint_langs():
            return self.path(self.imprint_langs()[0], key)
        return f"{prefix}{t[key]['slug']}/"

    @staticmethod
    def rel(from_dir, to):
        """A relative link from a page in directory from_dir to a site path,
        so the site works at the domain root and at a project-pages URL alike."""
        up = "../" * from_dir.count("/")
        return (up + to) or "./"

    def has(self, key):
        return key != "imprint" or bool(self.imprint_langs())

    @property
    def preview(self):
        return bool(self.cfg.get("preview"))

    def imprint_langs(self):
        """Languages with their own imprint page. A real imprint is in every
        language; the test-phase one only in German."""
        if self.cfg.get("imprint"):
            return list(self.langs)
        if self.preview and "imprint_preview" in self.langs.get("de", {}):
            return ["de"]
        return []

    def banner(self, code, here):
        """The test-phase strip at the top of every page."""
        if not self.preview:
            return ""
        t = self.langs[code]["preview"]
        link = ""
        if self.has("imprint"):
            link = (f' <a href="{self.rel(here, self.path(code, "imprint"))}" hreflang="de">'
                    f'{esc(t["link"])}</a>')
        return (f'<div class="preview" role="note"><span class="badge">{esc(t["badge"])}</span> '
                f'<span>{esc(t["text"])}{link}</span></div>\n')

    # chrome ------------------------------------------------------------

    def asset(self, here, name):
        return f"{self.rel(here, 'static/' + name)}?v={self.hashes.get(name, '')}"

    def head(self, code, key, here, title, description):
        t = self.langs[code]
        alts = ""
        if not (key == "imprint" and len(self.imprint_langs()) < len(self.langs)):
            alts = "".join(
                f'<link rel="alternate" hreflang="{c}" href="{self.base}{self.path(c, key)}">\n'
                for c in self.langs)
            alts += f'<link rel="alternate" hreflang="x-default" href="{self.base}{self.path(self.default, key)}">\n'
        url = self.base + self.path(code, key)
        og = self.base + "static/media/og.jpg"
        return f"""<!doctype html>
<html lang="{code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{'<meta name="robots" content="noindex, nofollow">' + chr(10) if self.preview else ''}<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{url}">
{alts}<meta property="og:type" content="website">
<meta property="og:site_name" content="Happy Highrise">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og}">
<meta property="og:image:width" content="920">
<meta property="og:image:height" content="430">
<meta property="og:locale" content="{t['locale']}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#97bdda">
<link rel="icon" href="{self.rel(here, 'static/favicon.ico')}" sizes="any">
<link rel="icon" type="image/png" href="{self.rel(here, 'static/media/favicon.png')}">
<link rel="apple-touch-icon" href="{self.rel(here, 'static/media/apple-touch-icon.png')}">
<link rel="preload" href="{self.rel(here, 'static/fonts/Silkscreen-Bold.ttf')}" as="font" type="font/ttf" crossorigin>
<link rel="stylesheet" href="{self.asset(here, 'site.css')}">
</head>
"""

    def langs_switch(self, code, key, here):
        items = []
        for c, t in self.langs.items():
            label = f'<abbr title="{esc(t["lang_name"])}">{t["lang_short"]}</abbr>'
            if c == code:
                items.append(f'<span aria-current="true" lang="{c}">{label}</span>')
            else:
                target = self.path(c, key)
                if target == here:  # a page only one language has: go home
                    target = self.path(c, "home")
                href = self.rel(here, target)
                items.append(f'<a href="{href}" hreflang="{c}" lang="{c}">{label}</a>')
        return (f'<nav class="langs" aria-label="{esc(self.langs[code]["ui"]["language"])}">'
                + "".join(items) + "</nav>")

    def footer(self, code, key, here):
        t = self.langs[code]
        links = [f'<a href="{self.rel(here, self.path(code, "privacy"))}">{esc(t["footer"]["privacy"])}</a>']
        if self.has("imprint"):
            hl = "" if code in self.imprint_langs() else ' hreflang="de"'
            links.append(f'<a href="{self.rel(here, self.path(code, "imprint"))}"{hl}>{esc(t["footer"]["imprint"])}</a>')
        email = self.cfg.get("contact_email")
        if email:
            links.append(f'<a href="mailto:{esc(email)}">{esc(email)}</a>')
        if key == "home":
            links.append(f'<a href="#roof">{esc(t["footer"]["top"])} ↑</a>')
        return f"""<footer class="bedrock">
<div class="wrap row">
<nav>{''.join(links)}</nav>
{self.langs_switch(code, key, here)}
<span>© {YEAR} Happy Highrise</span>
</div>
</footer>
"""

    def steam_button(self, code):
        t = self.langs[code]["hero"]
        app = self.cfg.get("steam_app_id")
        icon = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 3h6v2H5v4H3zm12 0h6v6h-2V5h-4zM3 15h2v4h4v2H3zm16 0h2v6h-6v-2h4z"/></svg>')
        if app:
            lang_q = "?l=german" if code == "de" else ""
            return (f'<a class="btn btn-primary" href="https://store.steampowered.com/app/{esc(app)}/{lang_q}" '
                    f'rel="noopener">{icon}{esc(t["cta_wishlist"])}</a>')
        return f'<span class="btn btn-soon"><span class="dot" aria-hidden="true"></span>{esc(t["cta_soon"])}</span>'

    # pages -------------------------------------------------------------

    def shot(self, code, sid, big):
        alt = self.langs[code]["shots"][sid]
        here = self.path(code, "home")
        full = self.rel(here, f"static/media/{sid}.webp")
        thumb = self.rel(here, f"static/media/{sid}-960.webp")
        sizes = "(max-width: 900px) 100vw, 640px" if big else "(max-width: 900px) 33vw, 210px"
        return (f'<a class="shot" href="{full}">'
                f'<img src="{thumb}" srcset="{thumb} 960w, {full} 1920w" sizes="{sizes}" '
                f'width="960" height="540" loading="lazy" decoding="async" alt="{esc(alt)}"></a>')

    def home(self, code):
        t = self.langs[code]
        here = self.path(code, "home")
        ui = t["ui"]
        floors = t["floors"]
        n = len(floors)
        rooms = {"build": "build", "lifts": "lifts", "run": "run", "life": "life", "stars": "stars"}

        # The lift: roof, the trailer on the top floor, a floor per feature
        # counting down, the lobby, then underground.
        stops = [("roof", "R", "Happy Highrise"), ("trailer", str(n + 1), t["trailer"]["label"])]
        stops += [(f["id"], str(n - i), f["label"]) for i, f in enumerate(floors)]
        stops += [("lobby", "G", t["lobby"]["label"]), ("dig", "B1", t["dig"]["label"])]
        shaft = "".join(
            f'<li><a href="#{sid}"><span class="sr">{esc(ui["floor"])} </span>{num}'
            f'<span class="name">{esc(name)}</span></a></li>'
            for sid, num, name in stops)

        def tag(num, label):
            return (f'<div class="tag"><span class="num" aria-hidden="true">{num}</span>'
                    f'<span>{esc(ui["floor"])} {num} · {esc(label)}</span></div>')

        feature_html = []
        for i, f in enumerate(floors):
            shots = f["shots"]
            more = ""
            if len(shots) > 1:
                more = f'<div class="shots-more" style="grid-template-columns: repeat({max(2, len(shots) - 1)}, minmax(0, 1fr))">' + "".join(self.shot(code, s, False) for s in shots[1:]) + "</div>"
            room = rooms.get(f["id"], "build")
            feature_html.append(f"""
<section class="floor" id="{f['id']}" style="--room: var(--room-{room})">
<div class="wrap feature">
<div>
{tag(n - i, f['label'])}
<h2>{esc(f['title'])}</h2>
<p style="margin-top:18px">{esc(f['text'])}</p>
</div>
<div>{self.shot(code, shots[0], True)}{more}</div>
</div>
</section>""")

        release = self.cfg.get("release") or t["lobby"]["release_soon"]
        facts = "".join(f"<dt>{esc(k)}</dt><dd>{esc(fill(v, release=release))}</dd>"
                        for k, v in t["lobby"]["facts"])
        email = self.cfg.get("contact_email")
        contact = ""
        if email:
            contact = (f'<p class="small">{esc(t["lobby"]["contact"])}: '
                       f'<a href="mailto:{esc(email)}">{esc(email)}</a></p>')
        kit = self.rel(here, "static/press/happy-highrise-presskit.zip")

        page = self.head(code, "home", here, t["meta"]["title"], t["meta"]["description"])
        page += f"""<body>
<a class="skip" href="#main">{esc(ui['skip'])}</a>
{self.banner(code, here)}
<nav class="shaft" aria-label="{esc(ui['floors'])}">
<ol>{shaft}<li class="car" aria-hidden="true"></li></ol>
</nav>

<section class="hero" id="roof">
<header class="topbar">{self.langs_switch(code, 'home', here)}</header>
<div class="hero-copy">
<img class="logo" src="{self.rel(here, 'static/media/logo.webp')}" width="584" height="172" alt="Happy Highrise">
<h1>{t['hero']['tagline']}</h1>
<p class="lede">{esc(t['hero']['lede'])}</p>
<div class="ctas">
{self.steam_button(code)}
<a class="btn btn-ghost" href="#trailer"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 4h2v2h2v2h2v2h2v4h-2v2h-2v2H9v2H7z"/></svg>{esc(t['hero']['cta_trailer'])}</a>
</div>
<p class="platforms">{esc(t['hero']['platforms'])}</p>
</div>
<div class="hero-art-box"><img class="hero-art" src="{self.rel(here, 'static/media/hero.png')}" width="1920" height="620" alt="" fetchpriority="high"></div>
</section>

<main id="main">
<section class="floor floor-trailer" id="trailer">
<div class="wrap">
<div class="floor-head">
{tag(n + 1, t['trailer']['label'])}
<h2>{esc(t['trailer']['title'])}</h2>
<p>{esc(t['trailer']['text'])}</p>
</div>
<div class="video">
<video controls preload="none" playsinline width="1280" height="720" poster="{self.rel(here, 'static/media/trailer-poster.jpg')}">
<source src="{self.rel(here, 'static/media/trailer.mp4')}" type="video/mp4">
{esc(t['trailer']['fallback'])}
</video>
</div>
</div>
</section>
{''.join(feature_html)}

<section class="floor" id="lobby" style="--room: var(--room-lobby)">
<div class="wrap">
<div class="floor-head">
{tag('G', t['lobby']['label'])}
<h2>{esc(t['lobby']['title'])}</h2>
<p style="margin-top:18px">{esc(t['lobby']['text'])}</p>
</div>
<div class="press">
<div class="card">
<h3>{esc(t['lobby']['facts_title'])}</h3>
<dl class="facts">{facts}</dl>
</div>
<div class="card">
<h3>{esc(t['lobby']['kit_title'])}</h3>
<p>{esc(t['lobby']['kit_text'])}</p>
<a class="btn btn-primary" href="{kit}" download><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 3h2v10h2v-2h2v2h-2v2h-2v2h-2v-2H9v-2H7v-2h2v2h2zM4 19h16v2H4z"/></svg>{esc(t['lobby']['kit_button'])}</a>
<p class="small">{self.kit_size} MB · ZIP</p>
{contact}
<div style="margin-top:18px">{self.steam_button(code)}</div>
</div>
</div>
</div>
</section>
</main>

<div class="street" aria-hidden="true"></div>
<section class="underground" id="dig">
<div class="wrap">
{tag('B1', t['dig']['label'])}
<h2>{esc(t['dig']['title'])}</h2>
<p>{esc(t['dig']['text'])}</p>
<p class="tease">{esc(t['dig']['tease'])}</p>
</div>
</section>
<div class="strata" aria-hidden="true"></div>
{self.footer(code, 'home', here)}
<dialog class="lightbox" aria-label="{esc(ui['enlarge'])}">
<figure><img alt=""><figcaption></figcaption></figure>
<button class="close" type="button" aria-label="{esc(ui['close'])}">×</button>
<button class="prev" type="button" aria-label="{esc(ui['previous'])}">‹</button>
<button class="next" type="button" aria-label="{esc(ui['next'])}">›</button>
</dialog>
<script src="{self.asset(here, 'site.js')}" defer></script>
</body>
</html>
"""
        self.write(here, page)
        self.pages.append(("home", here))

    def plain(self, code, key, title, body):
        here = self.path(code, key)
        t = self.langs[code]
        page = self.head(code, key, here, f"{title} · Happy Highrise", t["meta"]["description"])
        page += f"""<body>
{self.banner(code, here)}<header class="page-top"><div class="wrap row">
<a href="{self.rel(here, self.path(code, 'home'))}"><img class="logo" src="{self.rel(here, 'static/media/logo.webp')}" width="584" height="172" alt="Happy Highrise"></a>
{self.langs_switch(code, key, here)}
</div></header>
<main class="prose">
<h1>{esc(title)}</h1>
{body}
</main>
<div class="strata" aria-hidden="true"></div>
{self.footer(code, key, here)}</body>
</html>
"""
        self.write(here, page)
        self.pages.append((key, here))

    def privacy(self, code):
        t = self.langs[code]
        p = t["privacy"]
        email = self.cfg.get("contact_email")
        if email:
            contact = fill(p["contact_line"], email=esc(email))
        elif self.has("imprint"):
            contact = fill(p["contact_imprint"], imprint_href=self.rel(self.path(code, "privacy"), self.path(code, "imprint")))
        else:
            contact = ""
        body = "\n".join(fill(line, privacy_contact=contact) for line in p["body"])
        self.plain(code, "privacy", p["title"], body)

    def imprint(self, code):
        if code not in self.imprint_langs():
            return
        if not self.cfg.get("imprint"):
            t = self.langs[code]["imprint_preview"]
            body = "\n".join(t["body"])
            return self.plain(code, "imprint", t["title"], body)
        im = self.cfg["imprint"]
        t = self.langs[code]["imprint"]
        lines = "<br>".join(esc(x) for x in [im["name"], *im.get("address", [])])
        body = f"<p>{esc(t['intro'])}</p>\n<address>{lines}</address>\n"
        if im.get("email"):
            body += f"<h2>{esc(t['contact'])}</h2>\n<p><a href=\"mailto:{esc(im['email'])}\">{esc(im['email'])}</a></p>\n"
        body += f"<h2>{esc(t['responsible'])}</h2>\n<p>{lines}</p>\n"
        self.plain(code, "imprint", t["title"], body)

    def not_found(self):
        # Served for any missing path at any depth, so links are absolute.
        en, de = self.langs["en"]["notfound"], self.langs["de"]["notfound"]
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>404 · Happy Highrise</title>
<meta name="robots" content="noindex">
<link rel="icon" href="/static/favicon.ico" sizes="any">
<link rel="stylesheet" href="/static/site.css?v={self.hashes['site.css']}">
</head>
<body>
<header class="page-top"><div class="wrap row"><a href="/"><img class="logo" src="/static/media/logo.webp" width="584" height="172" alt="Happy Highrise"></a></div></header>
<main class="notfound">
<h1>{esc(en['title'])}</h1>
<p>{esc(en['text'])}</p>
<p><a class="btn btn-primary" href="/">{esc(en['home'])}</a></p>
<div lang="de" style="margin-top:56px">
<h2 class="pixel" style="font-size:20px">{esc(de['title'])}</h2>
<p><a href="/de/">{esc(de['home'])}</a></p>
</div>
</main>
<div class="strata" aria-hidden="true"></div>
</body>
</html>
"""
        (self.out / "404.html").write_text(page)

    # output ------------------------------------------------------------

    def write(self, here, text):
        d = self.out / here
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(text)

    def press_kit(self):
        """One zip of everything a journalist asks for, from the Steam kit."""
        d = self.out / "static" / "press"
        d.mkdir(parents=True, exist_ok=True)
        z = d / "happy-highrise-presskit.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as kit:  # PNG/JPG don't shrink
            kit.write(STEAM / "capsules" / "library_logo.png", "logo/happy-highrise-logo.png")
            kit.write(HERE / "static" / "media" / "logo.png", "logo/happy-highrise-logo-small.png")
            for name in ("header_capsule", "main_capsule", "vertical_capsule", "library_capsule", "library_hero"):
                kit.write(STEAM / "capsules" / f"{name}.png", f"key-art/{name}.png")
            kit.write(STEAM / "icons" / "client_icon_512.png", "icon/happy-highrise-icon-512.png")
            for s in sorted((STEAM / "screenshots").glob("*.jpg")):
                kit.write(s, f"screenshots/{s.name}")
            for code, t in self.langs.items():
                release = self.cfg.get("release") or t["lobby"]["release_soon"]
                lines = [f"Happy Highrise - {t['lobby']['facts_title']}", ""]
                lines += [f"{k}: {fill(v, release=release)}" for k, v in t["lobby"]["facts"]]
                lines += ["", t["meta"]["description"], "", self.base + t["path"]]
                if self.cfg.get("contact_email"):
                    lines += ["", f"{t['lobby']['contact']}: {self.cfg['contact_email']}"]
                kit.writestr(f"factsheet-{code}.txt", "\n".join(lines) + "\n")
        self.kit_size = max(1, round(z.stat().st_size / 1_000_000))

    def sitemap(self):
        rows = []
        keys = ["home", "privacy"] + (["imprint"] if self.has("imprint") else [])
        for key in keys:
            for c in (self.imprint_langs() if key == "imprint" else self.langs):
                alts = "".join(
                    f'<xhtml:link rel="alternate" hreflang="{a}" href="{self.base}{self.path(a, key)}"/>'
                    for a in self.langs)
                rows.append(f"<url><loc>{self.base}{self.path(c, key)}</loc>{alts}</url>")
        (self.out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(rows) + "\n</urlset>\n")
        if self.preview:
            # A test site stays out of search results until it goes public.
            (self.out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        else:
            (self.out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {self.base}sitemap.xml\n")

    def build(self):
        en = self.langs[self.default]
        errors = []
        for code, t in self.langs.items():
            if code != self.default:
                errors += [f"{code}.json{e}" for e in same_shape(en, t)]
            for f in t["floors"]:
                for s in f["shots"]:
                    if not (HERE / "static" / "media" / f"{s}.webp").exists():
                        errors.append(f"{code}.json: screenshot {s} has no picture (python3 website/make_media.py)")
        if errors:
            sys.exit("the language files disagree:\n  " + "\n  ".join(errors))
        im = self.cfg.get("imprint")
        if im is not None and not im.get("name"):
            sys.exit("site.json: imprint needs at least a name and an address")
        if self.preview:
            self.warnings.append("preview: the site is marked as a test version (banner, noindex, test-phase imprint).")
        elif not im:
            self.warnings.append("no imprint: a German site needs one (DDG §5). Fill in site.json's \"imprint\".")
        if not self.cfg.get("steam_app_id"):
            self.warnings.append("no steam_app_id yet: the page says 'Coming soon on Steam'.")

        if self.out.exists():
            shutil.rmtree(self.out)
        shutil.copytree(HERE / "static", self.out / "static")
        self.hashes = {n: hashlib.sha256((HERE / "static" / n).read_bytes()).hexdigest()[:10]
                       for n in ("site.css", "site.js")}
        self.press_kit()
        for code in self.langs:
            self.home(code)
            self.privacy(code)
            if self.has("imprint"):
                self.imprint(code)
        self.not_found()
        self.sitemap()
        (self.out / "CNAME").write_text(self.cfg["domain"] + "\n")
        (self.out / ".nojekyll").write_text("")
        return self.warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "website"), help="output folder (default .tmp/website)")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    if out == ROOT or out == HERE or HERE.is_relative_to(out):
        sys.exit(f"refusing to build into {out}: it would delete the sources")
    warnings = Site(out).build()
    for w in warnings:
        # GitHub Actions shows these on the run's summary page.
        print(f"::warning::{w}")
    files = sum(1 for p in out.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"built {files} files, {size / 1e6:.1f} MB, into {out}")


if __name__ == "__main__":
    main()
