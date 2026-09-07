# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, activités
et inscriptions, calendrier de garde de septembre, budget annuel.

## Fichier

- `planning-hebdomadaire.html` — source de la page, au format attendu par les
  Artifacts Claude : le fichier contient directement le `<title>`, les styles,
  le contenu et les scripts (l'enveloppe `<!doctype html><html><head><body>`
  est ajoutée à la publication).

## Déploiement GitHub Pages

Site : https://amsolutions-pro.github.io/planning-2026-27/

### Activation (une seule fois)

GitHub Pages doit être activé à la main dans **Settings → Pages** : le jeton des
GitHub Actions n'a pas le droit de créer le site (`Resource not accessible by
integration`). Les deux modes fonctionnent :

- **Source « GitHub Actions »** — le workflow `.github/workflows/pages.yml`
  publie à chaque push sur la branche par défaut ;
- **Source « Deploy from a branch »** — branche `claude/deploy-html-page-sdarke`,
  dossier `/ (root)` : `index.html` et `.nojekyll` sont versionnés à la racine.

### Génération de `index.html`

`index.html` est produit par `build.py`, qui enveloppe
`planning-hebdomadaire.html` dans un document HTML complet. Après toute
modification de la page :

```
python3 build.py
```

Le workflow échoue si `index.html` n'a pas été régénéré après un changement de
la source.

## Contraintes respectées

- Icônes en SVG inline (sprite `<symbol>`) : les feuilles de style externes
  autres que Google Fonts sont bloquées à la publication.
- Aucune dépendance JavaScript externe.
- Thèmes clair et sombre pilotés par variables CSS.
- Feuille de style d'impression : toutes les sections sont imprimées.
