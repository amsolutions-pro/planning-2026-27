# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, emploi du
temps au collège, activités et inscriptions, calendrier de garde de septembre,
budget annuel.

L'onglet « Activités & créneaux » réunit le coût des inscriptions et le choix
des créneaux : pour le ping-pong, la flûte et le piano, on coche les créneaux
retenus — plusieurs sont possibles pour une même activité — et les autres
disparaissent de la semaine type et des journées superposées. Les choix sont
conservés dans le `localStorage` du navigateur, donc propres à chaque appareil.

L'onglet « Collège » propose deux vues : la grille des cours, et « Journées
superposées », où les jours sont en colonnes et le temps en vertical. L'échelle
ne couvre que la fin de journée (elle démarre une heure avant la première sortie
de cours) et affiche, pour chaque enfant, la fin des cours, les activités et le
battement entre les deux.

Les âges sont calculés à partir des dates de naissance inscrites dans la
constante `ENFANTS`, afin de rester justes au fil de l'année.

Sous 720 px, les deux grilles horaires abandonnent la lecture en colonnes, qui
imposait un long défilement latéral : l'emploi du temps devient une liste jour
par jour (rendue par le même `drawTimetable`, en plus du tableau, le CSS
choisissant laquelle afficher) et les journées superposées s'empilent, chacune
avec son propre rail d'heures.

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

### Favicon

Les icônes (`favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`,
`apple-touch-icon.png`, `android-chrome-192x192.png`,
`android-chrome-512x512.png`) et `site.webmanifest` sont à la racine ; les
balises `<link>` sont ajoutées par `build.py`. Tous les chemins sont **relatifs**
(`./favicon.ico`) : le site étant servi sous `/planning-2026-27/`, un chemin
absolu pointerait hors du projet.

L'artifact Claude garde son icône emoji : sa politique de sécurité n'autorise
pas d'image externe, et son onglet est celui de claude.ai.

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
