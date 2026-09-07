# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, activités
et inscriptions, calendrier de garde de septembre, budget annuel.

## Fichier

- `planning-hebdomadaire.html` — source de la page, au format attendu par les
  Artifacts Claude : le fichier contient directement le `<title>`, les styles,
  le contenu et les scripts (l'enveloppe `<!doctype html><html><head><body>`
  est ajoutée à la publication).

## Contraintes respectées

- Icônes en SVG inline (sprite `<symbol>`) : les feuilles de style externes
  autres que Google Fonts sont bloquées à la publication.
- Aucune dépendance JavaScript externe.
- Thèmes clair et sombre pilotés par variables CSS.
- Feuille de style d'impression : toutes les sections sont imprimées.
