# happy-highrise.com

The game's website: static HTML, one stylesheet, one small script the page
works without, and every font, picture and video served from the site itself.
There are no cookies, no analytics and no third-party requests, so the privacy
page can stay short and true.

English is the default, at `/`. German is at `/de/`.

## The idea

The page is the tower. It opens on the roof, in the game's own sky, with the
showcase tower from the Steam library hero. Each section below it is a floor:
a concrete slab on top, a lift-shaft number, and a room colour. A lift car on
the left (wide screens) follows you down and takes you to any floor. After the
lobby (press and facts) comes the street, and under it the rock: "Then dig
down". The colours are the game's own: sky and earth from the renderer, the
cream of the interface bar, the logo's navy and cream, and the lamp yellow of a
lift landing. Headings are in Silkscreen, the trailer's lettering font.

## Layout

```
website/
  build.py         makes the site (standard library only)
  make_media.py    makes static/media from the Steam kit (Pillow + ffmpeg, run by hand)
  site.json        facts that are the same in every language: Steam app id,
                   release, contact address, imprint
  i18n/en.json     every word on the site, in English
  i18n/de.json     ... and in German; must have exactly the same keys
  static/          served as /static: site.css, site.js, fonts/, media/
```

## Building and looking at it

```sh
python3 website/build.py                    # -> .tmp/website
python3 -m http.server -d .tmp/website 8000 # http://localhost:8000
```

The build fails if a language file is missing a key the English one has, so
a page can never fall back to English quietly. It warns (and the workflow
shows the warning) while there is no imprint or no Steam app id.

## Changing things

- **Words:** edit `i18n/en.json` and `i18n/de.json` together.
- **The Steam page goes live:** put its app id (the number in the store URL)
  in `site.json` as `"steam_app_id": 1234560`. Every "Coming soon on Steam"
  becomes "Wishlist on Steam" and links to the store.
- **A release date:** `"release": "March 2027"` in `site.json`.
- **Screenshots, logo or trailer changed in `steam/`:** run
  `python3 website/make_media.py` and commit `static/media`. The web trailer is
  the "Express to the Top" cut, trimmed to stop before its OUT NOW ON STEAM end
  card. When the game is out, set `TRAILER_END` in `make_media.py` to the
  full length and run it again.
- **Another language:** copy `i18n/en.json` to `i18n/<code>.json`, set its
  `path` to `<code>/`, translate, and add the code to `langs` in `site.json`.

## Test phase and imprint (Impressum)

While `"preview": true` in `site.json` (the setting today):

- every page carries a striped "Test version / Testversion" banner saying the
  site is a private preview, nothing is for sale and there is no Steam page;
- every page has `noindex`, and `robots.txt` disallows everything;
- the imprint is a German page, `/de/impressum/`, saying the site is a
  non-commercial test and that a full imprint follows before launch. Its words
  are `imprint_preview` in `i18n/de.json`; the English footer links to it as
  "Imprint (German)".

To go public: set `"preview": false` and fill in `imprint` (name, postal
address, email). A German website that promotes a product needs that imprint
(§ 5 DDG); with `preview` off and no imprint, the site has no imprint page and
every build warns.

## Deploying

This repository is private and stays the source of truth. GitHub Pages serves
the site from a second, **public** repository next to it, named after this
one with `_website` appended (`../aitower_website`). Never edit that one by
hand: it is a copy.

```sh
python3 scripts/sync-website.py --dry-run   # what would change
python3 scripts/sync-website.py             # copy and commit there
git -C ../aitower_website push              # publish
```

The sync checks this repository's name, builds the site once to make sure it
builds, then mirrors `website/`, the `steam/assets` pictures the press kit is
made from, and `website/deploy/website.yml` (installed there as
`.github/workflows/website.yml`) into the public repository, and commits
there if anything changed, naming the source commit. If the folder does not
exist it asks, then creates it with `git init`. It refuses a public copy with
uncommitted changes, and it never pushes.

In the public repository, every push to `main` builds and publishes the site.

One-time setup:

1. **GitHub:** create the public repository, then
   `git -C ../aitower_website remote add origin <its url>`. In its
   Settings → Pages → Source: **GitHub Actions**. Custom domain:
   `happy-highrise.com`. Tick **Enforce HTTPS** once GitHub has issued the
   certificate (minutes to an hour after DNS resolves).
2. **DNS** at the registrar:
   - `A` records for `happy-highrise.com`: `185.199.108.153`,
     `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `AAAA` records: `2606:50c0:8000::153`, `2606:50c0:8001::153`,
     `2606:50c0:8002::153`, `2606:50c0:8003::153`
   - `CNAME` for `www`: `sicaine.github.io`
3. Optionally verify the domain under your GitHub account (Settings → Pages →
   Add a domain), so nobody else can claim it for their own Pages site.
