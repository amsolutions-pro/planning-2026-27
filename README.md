# Planning 2026-2027 — Narek & Annie

Page interactive du planning hebdomadaire des enfants : semaine type, emploi du
temps au collège, activités et inscriptions, calendrier de garde jusqu'en
juillet 2027, budget annuel.

L'onglet « Activités & créneaux » réunit le coût des inscriptions et le choix
des créneaux. Seul le ping-pong reste à arbitrer : on coche les créneaux retenus
— plusieurs sont possibles — et les autres disparaissent de la semaine type et
des journées superposées. Les choix sont conservés dans le `localStorage` du
navigateur, donc propres à chaque appareil. Les créneaux de musique sont
arrêtés : solfège mercredi 16h30, flûte mercredi 18h00 → 18h20, piano jeudi
18h20 → 18h40, puis théâtre jeudi 19h15 → 21h30.

L'onglet « Collège » propose deux vues : la grille des cours, et « Journées
superposées », où les jours sont en colonnes et le temps en vertical. L'échelle
ne couvre que la fin de journée (elle démarre une heure avant la première sortie
de cours) et affiche, pour chaque enfant, la fin des cours, les activités et le
battement entre les deux.

Les âges sont calculés à partir des dates de naissance inscrites dans la
constante `ENFANTS`, afin de rester justes au fil de l'année.

Le jour en cours est signalé dans les trois vues (semaine type, grille des cours
et sa version en liste, journées superposées) et la page s'y place à l'ouverture
s'il n'est pas déjà à l'écran ; un bouton « Aujourd'hui » apparaît dès qu'on s'en
éloigne. Le dimanche, le repère se porte sur le lundi, annoncé comme « demain ».

Les deux barres de réglage — « Afficher » de la semaine type, et celle du
collège (vue, élève, semaine) — restent collées sous l'en-tête : on change
d'enfant ou de semaine depuis n'importe quel jour, sans remonter en haut de
page. Sous 720 px, l'en-tête se réduit à ses seuls onglets dès le premier
défilement (classe `is-compact`, posée par `majEntete`), et la barre perd ses
intitulés et sa légende ; à eux deux ils occupent alors environ 170 px. La
hauteur de l'en-tête est publiée dans la variable CSS `--entete`, sur laquelle
les barres s'accrochent.

Sous 720 px, les deux grilles horaires abandonnent la lecture en colonnes, qui
imposait un long défilement latéral : l'emploi du temps devient une liste jour
par jour (rendue par le même `drawTimetable`, en plus du tableau, le CSS
choisissant laquelle afficher) et les journées superposées s'empilent, chacune
avec son propre rail d'heures.

L'onglet « Collège » reprend les emplois du temps du semestre 1 de Narek (5F) et
Annie (3F). La quinzaine y est notée `R` pour la colonne Q1 des emplois du temps
papier et `V` pour la colonne Q2 ; un cours marqué `RV` a lieu chaque semaine et
porte la pastille « 2 sem. ». La semaine affichée par défaut est déduite de
l'alternance, la semaine du lundi 7 septembre 2026 étant une quinzaine Q2
(constante `ANCRAGE` dans le script de la page).

## Semaines Papa et Mama

La quinzaine est nommée par le parent qui a les enfants (table
`PARENT_DE_QUINZAINE`) : la quinzaine `V` (colonne Q2) est la semaine **Papa**,
la `R` (Q1) la semaine **Mama**. Le rattachement est calé sur un repère certain,
la reprise de Papa le vendredi 2 octobre 2026 au soir ; c'est la seule ligne à
corriger s'il change — surtout pas `ANCRAGE`, qui décide des cours affichés.
Aucune couleur ne code cette distinction —
elle tient à la forme du repère, **carré plein pour Papa, cercle évidé pour
Mama** (classe `.gm`, faite en `currentColor`), lisible à l'impression comme
pour un œil daltonien. Dans la liste des semaines, les lignes Papa portent en
plus un filet vertical à gauche.

L'onglet « Garde & semaines » ajoute, sous la frise de septembre, toutes les
semaines de la semaine en cours jusqu'à celle du lundi 26 juillet 2027
(`GARDE_DEBUT` et `GARDE_FIN`) :

- un encart « cette semaine / la semaine prochaine » ;
- un champ date qui répond pour un jour précis et met la ligne en évidence ;
- des filtres « Toutes / Papa / Mama » ;
- la liste mois par mois, avec le numéro de semaine ISO.

Les vacances scolaires de la **zone C** (Créteil, Paris, Versailles) sont
inscrites dans `VACANCES`, d'après le calendrier officiel 2026-2027 : chaque
période y va du premier au dernier jour sans classe. Les semaines concernées
portent une pastille dans la liste, un pont signale les jours qu'il couvre
(`joursDeVacances`), la recherche par date le mentionne, et un troisième encart
annonce les vacances en cours ou les prochaines.

Le relais se faisant le vendredi soir, un bloc va **du vendredi soir au vendredi
soir** : il commence par le week-end, puis couvre la semaine de classe. Un jour
du samedi ou du dimanche est donc rattaché au lundi suivant (`lundiDuBloc`).

Les semaines qui sortent de l'alternance sont listées dans `GARDE_EXCEPTIONS` —
une seule à ce jour : celle du 14 septembre 2026, deuxième semaine d'affilée chez
Papa pendant le déplacement de la mère. La ligne rappelle alors que l'emploi du
temps du collège, lui, suit toujours la quinzaine.

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
