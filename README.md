# Happy Highrise - website

The source of https://happy-highrise.com, published by GitHub Pages
(`.github/workflows/website.yml`).

**Do not edit this repository by hand.** It is a copy, made by
`scripts/sync-website.py` in the game's own repository, which is where the
site is written; every sync overwrites what is here. How the site is built
and changed is in [website/README.md](website/README.md).

```sh
python3 website/build.py --out _site      # build it
python3 -m http.server -d _site 8000      # look at it on :8000
```
