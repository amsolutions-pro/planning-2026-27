#!/usr/bin/env python3
"""Enveloppe la source de la page (format Artifact) dans un document HTML autonome.

La source `planning-hebdomadaire.html` ne contient que le contenu de la page
(<title>, styles, markup, scripts) : c'est ce qu'attend la publication en
Artifact, qui ajoute l'enveloppe elle-meme. Ce script produit la meme enveloppe
pour le site GitHub Pages, afin qu'il n'y ait qu'une seule source a maintenir.
"""

import pathlib
import shutil

ROOT = pathlib.Path(__file__).parent
SOURCE = ROOT / "planning-hebdomadaire.html"
DIST = ROOT / "dist"

SHELL = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Planning hebdomadaire des activites de Narek et Annie, garde de septembre et budget de l'annee scolaire 2026-2027.">
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
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(SHELL.format(content=content), encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    print(f"dist/index.html ecrit ({len(content)} octets de contenu)")


if __name__ == "__main__":
    main()
