#!/usr/bin/env python3
"""Genere le document HTML autonome servi par GitHub Pages.

La source `planning-hebdomadaire.html` ne contient que le contenu de la page
(<title>, styles, markup, scripts) : c'est ce qu'attend la publication en
Artifact, qui ajoute l'enveloppe elle-meme. Ce script produit la meme enveloppe
pour le site, afin qu'il n'y ait qu'une seule source de contenu a maintenir.

`index.html` est versionne : le site fonctionne donc aussi bien avec la source
Pages « GitHub Actions » qu'avec « Deploy from a branch ».
"""

import pathlib

ROOT = pathlib.Path(__file__).parent
SOURCE = ROOT / "planning-hebdomadaire.html"
OUTPUT = ROOT / "index.html"

SHELL = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Planning hebdomadaire des activites de Narek et Annie, garde de septembre et budget de l'annee scolaire 2026-2027.">
<!-- Genere par build.py a partir de planning-hebdomadaire.html - ne pas editer a la main. -->
<style>
:root{{color-scheme:light dark}}
body{{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif;background:#fff}}
img{{max-width:100%}}
[hidden]{{display:none!important}}
</style>
</head>
<body>
{content}
</body>
</html>
"""


def main() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    OUTPUT.write_text(SHELL.format(content=content), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"index.html genere ({OUTPUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
