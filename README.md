# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, activités
et inscriptions, calendrier de garde de septembre, budget annuel.

## Fichier

- `planning-hebdomadaire.html` — source de la page, au format attendu par les
  Artifacts Claude : le fichier contient directement le `<title>`, les styles,
  le contenu et les scripts (l'enveloppe `<!doctype html><html><head><body>`
  est ajoutée à la publication).

## Déploiement GitHub Pages

Le workflow `.github/workflows/pages.yml` construit et publie le site à chaque
push sur la branche par défaut :

1. `build.py` enveloppe `planning-hebdomadaire.html` dans un document HTML
   autonome et écrit `dist/index.html` ;
2. `actions/configure-pages` active GitHub Pages sur le dépôt si besoin ;
3. `actions/deploy-pages` publie `dist/`.

Site : https://amsolutions-pro.github.io/planning-2026-27/

`dist/` est généré, donc non versionné (`.gitignore`).

## Contraintes respectées

- Icônes en SVG inline (sprite `<symbol>`) : les feuilles de style externes
  autres que Google Fonts sont bloquées à la publication.
- Aucune dépendance JavaScript externe.
- Thèmes clair et sombre pilotés par variables CSS.
- Feuille de style d'impression : toutes les sections sont imprimées.
