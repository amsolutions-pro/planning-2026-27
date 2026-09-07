# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, emploi du
temps au collège, activités et inscriptions, calendrier de garde de septembre,
budget annuel.

L'onglet « Collège » reprend les emplois du temps du semestre 1 de Narek (5C) et
Annie (3F). La quinzaine y est notée `R` pour la semaine rouge (colonne Q1 des
emplois du temps papier) et `V` pour la semaine verte (colonne Q2) ; un cours
marqué `V + R` a lieu toutes les semaines. La semaine affichée par défaut est
déduite de l'alternance, la semaine du lundi 7 septembre 2026 étant verte
(constante `ANCRAGE` dans le script de la page).

## Fichier

- `planning-hebdomadaire.html` — source de la page, au format attendu par les
  Artifacts Claude : le fichier contient directement le `<title>`, les styles,
  le contenu et les scripts (l'enveloppe `<!doctype html><html><head><body>`
  est ajoutée à la publication).

## Déploiement GitHub Pages

Site : https://amsolutions-pro.github.io/planning-2026-27/

Pages est activé sur le dépôt et chaque push sur la branche par défaut
redéploie le site. Les deux modes de publication sont couverts :

- **Source « GitHub Actions »** — le workflow `.github/workflows/pages.yml`
  construit et publie le site ;
- **Source « Deploy from a branch »** — branche `claude/deploy-html-page-sdarke`,
  dossier `/ (root)` : `index.html` et `.nojekyll` sont versionnés à la racine.

L'activation initiale de Pages reste un geste manuel dans **Settings → Pages** :
le jeton des GitHub Actions n'a pas le droit de créer le site (`Resource not
accessible by integration`). Le workflow ne tente donc pas de l'activer.

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
