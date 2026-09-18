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
période y va du premier au dernier jour sans classe. Une carte les montre toutes
d'un coup (`renderVacances`) avec, pour chacune, ses dates, la reprise et les
semaines de garde qu'elle recouvre — celle en cours et la suivante y sont
signalées. Les semaines concernées portent aussi une pastille dans la liste, un
pont précise les jours qu'il couvre (`joursDeVacances`) et la recherche par date
nomme la période.

Pendant les vacances, l'onglet Collège ouvre sur un encadré qui l'annonce et
donne la date de reprise (`renderVacancesCollege`) ; la page ne défile alors pas
jusqu'au jour, pour ne pas passer par-dessus.

Le relais se faisant le vendredi soir, un bloc va **du vendredi soir au vendredi
soir** : il commence par le week-end, puis couvre la semaine de classe. Un jour
du samedi ou du dimanche est donc rattaché au lundi suivant (`lundiDuBloc`).

Les semaines qui sortent de l'alternance sont listées dans `GARDE_EXCEPTIONS` —
une seule à ce jour : celle du 14 septembre 2026, deuxième semaine d'affilée chez
Papa pendant le déplacement de la mère. La ligne rappelle alors que l'emploi du
temps du collège, lui, suit toujours la quinzaine.

## Actualités PRONOTE

L'onglet « Actualités » montre, enfant par enfant, ce que PRONOTE a de nouveau
et sépare **l'important** du reste. PRONOTE n'a pas d'API publique : la page
est statique et ne se connecte à rien. C'est l'action GitHub `pronote.yml` qui,
toutes les deux heures entre 7 h et 18 h du lundi au samedi, lance
`pronote/fetch.py` ;
le script se connecte à l'espace Parents avec la bibliothèque non officielle
[pronotepy](https://github.com/bain3/pronotepy), lit pour chaque enfant les
devoirs (14 jours), l'emploi du temps (7 jours : cours annulés, professeur
absent, contrôles annoncés), les notes et moyennes (30 jours), absences,
retards et punitions (30 jours), les informations et sondages, la messagerie,
puis écrit `pronote/actualites.json` — seulement s'il y a du nouveau — et
redéploie le site.

### Trois niveaux

Les nouvelles sont rangées en trois niveaux, et chaque vue ajoute le niveau
suivant à la précédente : **L'important**, **+ Le travail**, **Tout**.

- **Important** (filet et étiquette ambre) — ce qui demande une décision de
  votre part : absence ou retard **non justifié**, punition, cours annulé ou
  modifié, message non lu, sondage sans réponse, et toute communication **non
  lue** dont l'objet ou le texte parle de réunion, sortie, voyage, autorisation,
  orientation, stage, conseil de classe, grève, rendez-vous… (liste
  `MOTS_INFO_IMPORTANTE` dans `fetch.py`) — ces mots disent alors *pourquoi* elle
  est importante, au lieu du sec « 1 message non lu ».

  Une communication **lue** en sort. La règle a d'abord été l'inverse : une
  autorisation à signer ne cesse pas d'exister parce qu'on a ouvert le message.
  Mais rien ne l'en faisait jamais ressortir — il fallait la masquer d'un « Vu »
  que rien ne reprenait, et le « Remettre les vues » gonflait sans fin.
  L'important est ce qui attend encore votre attention ; une fois lue, la
  communication descend d'elle-même dans « Tout ».
- **Travail scolaire** (filet et étiquette violets) — ce qui regarde l'enfant :
  contrôle annoncé (emploi du temps, ou devoir mentionnant « contrôle »,
  « évaluation », « interro »…), devoir non fait pour le prochain jour de
  classe, note en dessous de 10/20.
- **Le reste** — devoirs courants, bonnes notes, absences justifiées,
  informations déjà lues.

La raison du classement est écrite en italique sous chaque nouvelle, et la
pastille de l'onglet ne compte que l'important.

Ce qui concerne les deux enfants (informations du collège, messagerie du compte
parent) apparaît dans une carte « Pour les deux » : une seule fois, donc un seul
clic. Le regroupement se fait sur le contenu lui-même — type, titre, date,
auteur —, car le collège donne un numéro différent au même message selon l'enfant
sous lequel on le lit. Le marquage « lu » repart de là et retrouve les deux
copies en direct. Deux devoirs de même intitulé, eux, restent deux devoirs : le
travail scolaire garde l'enfant dans son identité.

Les nouvelles apparues depuis la dernière ouverture de l'onglet, sur cet
appareil, portent « Nouveau ».

### Les cours annulés se posent sur la semaine

Un cours qui saute ne change pas seulement l'onglet Actualités : il change la
journée. Les perturbations que PRONOTE annonce — cours annulé, professeur
absent, cours déplacé — s'affichent donc **sur le jour concerné de la Semaine
type**, en ambre, la matière barrée quand le cours est annulé, avec l'heure, le
professeur et la salle.

Deux bornes, voulues :

- **la semaine en cours seulement**, du lundi au samedi. Une annulation de la
  semaine prochaine reste dans l'onglet Actualités : l'annoncer sur le mardi
  d'aujourd'hui tromperait ;
- **le filtre par enfant s'applique**, comme au reste de la semaine.

La mention du jour le dit aussi (« 1 au collège · 3 créneaux »), et une journée
sans activité cesse d'être grisée quand elle porte une perturbation. La semaine
est dessinée avant que le fichier chiffré ne soit lu : elle est redessinée quand
il arrive.

### Le bouton « Vu », et le « lu » sur PRONOTE

Chaque nouvelle importante ou scolaire porte un bouton **Vu** : elle sort alors
des deux premières vues et de la pastille, reste visible dans « Tout » avec une
étiquette verte, et « Remettre » la rétablit. La marque est gardée dans le
`localStorage` de l'appareil, et disparaît d'elle-même quand la nouvelle sort de
PRONOTE — au bout de quelques semaines, pas au premier passage : les listes de
PRONOTE sont bornées et se réordonnent, si bien qu'une nouvelle peut manquer à
l'appel puis revenir.

La marque tient à l'identifiant de la nouvelle, qui doit donc être le même d'un
passage à l'autre. Or **PRONOTE renumérote tout à chaque session** : un relevé a
vu 29 nouvelles sur 39 changer de numéro en vingt minutes. Reprendre ces numéros
tels quels réécrivait le fichier à chaque passage — commit et republication pour
rien —, faisait revenir le bouton « Vu » des nouvelles déjà vues à chaque
actualisation, et envoyait au robot des numéros périmés qu'il ne retrouvait plus
pour les marquer lues.

L'identité d'une nouvelle vient donc de ce qu'elle dit (`identite`) : son type,
son titre, son auteur, sa date — et pour le travail scolaire, son descriptif et
l'enfant, seuls à distinguer deux devoirs de même matière et même échéance. Une
communication n'emporte pas l'enfant : le même message adressé aux deux n'en
fait qu'une, et un seul clic. Le classement, l'état lu ou fait, la date de
signalement n'en sont pas : ils bougent sans que la nouvelle change. Les numéros
PRONOTE ne sont plus publiés du tout — ils ne servent que le temps du passage, à
ne pas relire deux fois la même chose pour les deux enfants. Le clic « Vu » envoie
l'identité, et le robot retrouve la discussion en direct pour la marquer lue.

Le journal de l'action affiche à chaque passage `identités : N gardée(s), N
nouvelle(s), N disparue(s)` — des comptes, rien du contenu. C'est ce relevé qui a
mis le défaut en évidence, et c'est lui qui dirait qu'il revient.

Changer cette identité change le format publié, d'où le numéro `version` que le
fichier annonce **en clair**, hors du chiffrement (`VERSION_FICHIER`). Un onglet
laissé ouvert plusieurs jours tourne sur le JavaScript que le navigateur a mis en
cache : s'il est plus vieux que le fichier, il lirait de travers ce que le robot
publie et perdrait les « Vu » sans dire pourquoi. Il l'annonce donc, et propose
de se recharger — sur une adresse neuve, sinon le navigateur resservirait la même
page périmée.

Par défaut, elle s'arrête là. Une fois la page **reliée à GitHub**, le même clic
passe aussi la discussion ou l'information en **lu sur PRONOTE** — de quoi ne
plus accumuler dans la messagerie du collège ce qu'on a déjà lu ici. Le robot
marque **les deux exemplaires** quand le collège a écrit aux deux enfants :
s'arrêter au premier laissait l'autre non lu, et le compte de PRONOTE ne
descendait pas. Une fois PRONOTE au courant, la marque locale est retirée : la
vérité est passée de l'autre côté, et « Remettre les vues » cesse d'accumuler
sans fin ce qui a déjà été transmis.

#### Ce que PRONOTE accepte, et ce qu'il refuse

Éprouvé en direct contre le vrai serveur, neuf tours, par le workflow
`diagnostic.yml` (réversible, et muet : il n'imprime que des nombres et des
empreintes). Deux résultats, mesurés dans des sessions neuves :

- **La messagerie s'écrit.** Une discussion lue est repassée non lue, puis
  relue : le compte des non-lus fait `0 → 1 → 0`. Le « Vu » d'un message tient
  donc sa promesse.
- **Le « lu » d'une information ne s'écrit pas.** Toutes les formes ont été
  essayées — destinataire enfant, parent, groupe, le descripteur exact que
  PRONOTE annonce lui-même (`genrePublic 2`, `public G=5`), aucun destinataire du
  tout, les quatre genres, l'ouverture du détail comme le fait un clic, et
  jusqu'au sens inverse (repasser une information lue en non lue). PRONOTE
  répond à chaque fois `RapportSaisie: {_erreurSaisie_: true}` : **la saisie est
  écartée**, sans la moindre erreur HTTP.

Le code livré a été éprouvé tel quel contre le vrai serveur, en dernier tour :
`marquer_lu` rend `1 fait · 1 écarté · 0 introuvable`, le message passe de non lu
à lu (`1 → 0`) et l'information ne bouge pas (`8 → 8`) — dite écartée, jamais
donnée pour marquée.

Ce silence est ce qui a fait tourner en rond : pronotepy ne regarde pas ce
rapport, et le robot croyait donc avoir marqué à chaque fois. `saisie_refusee`
le lit maintenant, et seul ce que PRONOTE a réellement pris est compté comme
fait — le journal dit `écartés par PRONOTE : N` le cas échéant.

Conséquence assumée : la page n'envoie plus que les **messages**. Pour une
information ou un sondage, le « Vu » reste sur l'appareil, et le bandeau le dit
au lieu de le promettre.

Le marquage des **informations et sondages** demande un détour. pronotepy
adresse la requête à `client.info`, la ressource fixée à la connexion : sur un
compte parent, c'est le parent, jamais l'enfant que `set_child` vient de
choisir. PRONOTE accepte la requête et n'en fait rien — le robot croyait avoir
marqué, et la pastille du collège ne bougeait pas. `marquer_information` poste
donc au nom de l'enfant. Quelle ressource PRONOTE attend exactement pour un
parent n'est pas vérifiable hors ligne : les deux sont postées, l'enfant
d'abord, et les compteurs de non-lus disent laquelle a porté.

Les passages qui marquent affichent dans le journal le nombre de non-lus que
PRONOTE compte **avant et après**, enfant par enfant. Des nombres, rien du
contenu : c'est la seule façon de savoir si PRONOTE a vraiment pris le marquage,
le robot ne sachant, lui, que s'il a posté sans erreur.

**« Actualiser » ne marque rien** : il relance le robot, pour aller chercher les
nouveautés sans attendre l'heure suivante. Et il ne le relance que depuis un
appareil **relié** : le jeton vit dans le `localStorage` de ce navigateur-là, à
recoller sur le téléphone comme sur chaque ordinateur. Sans jeton, le bouton
relit le fichier publié — il le dit, et ouvre la marche à suivre, au lieu de ne
rien faire sans un mot comme il le faisait. Seul le clic sur **Vu** demande un
marquage. Un passage dont le journal ne montre aucune ligne « Marqué lu » est un
passage à qui on n'a rien demandé.

Un envoi accepté par GitHub n'est pas un marquage réussi : GitHub dit seulement
qu'il a pris la demande. La page vérifie donc sur pièces — si le robot republie
après l'envoi et que la communication est toujours non lue chez PRONOTE, elle
affiche « Vu · pas pris par PRONOTE » et rend la main au bouton **Réessayer
l'envoi**, au lieu d'un « lu sur PRONOTE » qui n'est pas vrai.

Le chemin est indirect, faute de mieux : la page est un fichier statique, elle
n'a ni les identifiants PRONOTE ni le droit de l'appeler depuis un autre site.
Elle demande donc à GitHub de réveiller le robot (`repository_dispatch`, type
`pronote-lu`), qui se connecte et marque. Le clic est groupé avec les suivants
pendant quatre secondes, pour ne pas lancer un passage par pression. L'étiquette
suit l'affaire : « à transmettre », « transmission… », « lu sur PRONOTE », ou
« envoi échoué » avec un bouton pour réessayer. Seuls les messages,
informations et sondages partent : un devoir n'a pas de « lu » sur PRONOTE.

La même liaison sert au bouton **Actualiser** : il lance un passage du robot sans
attendre l'heure suivante, puis guette la republication du site. Comptez une
minute ou deux. Un passage demandé depuis la page réécrit le fichier **même sans
nouvelle** (`--forcer`), pour que le bouton reçoive une réponse au lieu
d'attendre un changement qui ne viendrait pas ; les passages à l'heure, eux,
restent silencieux quand il n'y a rien. Sans liaison, le bouton relit simplement
le fichier publié.

Le fichier ne doit changer que lorsque PRONOTE a du neuf — sinon chaque passage
produirait un commit et une republication pour rien, et l'onglet marquerait tout
comme « Nouveau ». Or un devoir ou un cours n'a pas de date d'apparition propre.
Le robot relit donc le fichier précédent pour retrouver quand il a vu chaque
nouvelle la première fois (`memoire_precedente`), au lieu de leur donner l'heure
du passage.

#### Un jeton pour tous les appareils, ou un par appareil

Deux façons de relier la page, au choix.

**Porté par le fichier (recommandé).** Mettez le jeton dans un secret de dépôt
nommé `PRONOTE_PAGE_PAT`. Le robot le glisse dans le fichier **chiffré** qu'il
publie (`jeton_page`), et la page s'en sert : tout appareil qui a le mot de passe
peut lancer le robot, sans rien coller nulle part. C'est la réponse à « je ne sais
plus sur quel navigateur j'ai mis le jeton ».

Le prix, dit franchement : le mot de passe de la famille protège alors **aussi**
un jeton capable d'écrire sur le dépôt. Il doit être à la hauteur, et si vous le
partagez un jour, révoquez le jeton et changez le secret. Deux garde-fous dans le
code : le jeton n'est **jamais** écrit dans un fichier non chiffré (`--clair` ou
mot de passe absent : il est retiré, avec un avertissement dans le journal), et la
page ne l'affiche nulle part — il ne sert que dans l'en-tête de la requête.

**Collé sur l'appareil.** Le champ en bas de l'onglet garde le jeton dans le
`localStorage` de ce navigateur-là. Il l'emporte sur celui du fichier : c'est le
recours si celui du fichier a été révoqué. Sans secret de dépôt ni jeton collé,
« Actualiser » relit simplement le fichier publié et le dit.

Pour relier à la main : dépliez la ligne en bas de l'onglet, puis créez un jeton sur
[github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens/new)
limité à **ce seul dépôt**, avec la permission **Contents : Read and write** (la
permission que demande `repository_dispatch`), et collez-le. Le jeton reste dans
le `localStorage` de cet appareil — il n'est jamais publié, ni écrit dans le
dépôt — et il est à refaire sur chaque appareil. À garder en tête : qui met la
main sur l'appareil déverrouillé peut s'en servir pour écrire dans ce dépôt ;
un jeton se révoque en un clic depuis la même page GitHub. « Retirer le jeton »
l'efface de l'appareil.

Ce que le robot ne fait **pas** de lui-même : marquer lu ce que vous n'avez pas
cliqué. Un marquage automatique à chaque passage ferait croire au professeur que
vous avez lu son message alors que personne ne l'a ouvert — ce qui compte pour
une autorisation à signer — et l'onglet y perdrait son principal signal, puisque
c'est justement « non lu » qui fait entrer un message dans l'important.

### Horaires

Le cron de GitHub est en UTC et ignore l'heure d'été : à heures fixes, les
passages glisseraient d'une heure entre juin et décembre. Le cron couvre donc
large et c'est `fetch.py --heures-ouvrees` qui décide, en heure de Paris : rien
avant `HEURE_MIN` (7 h) ni après `HEURE_MAX` (18 h). Résultat, six passages par
jour en toute saison — 7 h à 17 h l'été, 8 h à 18 h l'hiver — et aucun le
dimanche. Un lancement à la main (**Run workflow**) passe outre et s'exécute
toujours.

### Confidentialité

Le dépôt est **public**. Le fichier est donc chiffré (AES-256-GCM, clé dérivée
par PBKDF2 du secret `PRONOTE_SITE_PASSPHRASE`) ; la page demande ce mot de
passe une fois et le garde dans le `localStorage` de l'appareil (bouton
« Oublier le mot de passe » pour l'effacer). Le déchiffrement se fait dans le
navigateur avec WebCrypto, donc en https (GitHub Pages l'est). Sans mot de
passe, seuls l'horodatage et une empreinte du contenu sont lisibles.

Les identifiants PRONOTE ne sont jamais dans le dépôt : ils vivent dans les
secrets du dépôt (Settings → Secrets and variables → Actions), lus par l'action.
Les journaux de l'action n'affichent aucun identifiant.

### Mise en place (une fois)

1. Sur votre ordinateur : `pip install -r pronote/requirements.txt`.
2. Choisir la voie de connexion, en lançant `pronote/configurer.py` :
   - **`--qr` (recommandé)** — sur PRONOTE, Mon compte → générer un QR code
     pour l'application mobile, avec un code à 4 chiffres ; coller le contenu
     du QR code dans le script. Il imprime le secret `PRONOTE_TOKEN_JSON`. Le
     mot de passe du compte ne quitte pas votre ordinateur, et ce jeton se
     révoque depuis PRONOTE (liste des appareils). Le jeton change à chaque
     connexion : l'action le remet dans le secret elle-même, ce qui demande un
     jeton GitHub à granularité fine (Settings → Developer settings →
     Fine-grained tokens, ce dépôt, permission *Secrets : read and write*)
     dans le secret `PRONOTE_SECRETS_PAT`.
   - **`--mdp`** — identifiant et mot de passe de l'espace Parents, plus le code
     PIN si la double authentification est activée. Les secrets `PRONOTE_USERNAME`
     et `PRONOTE_PASSWORD` suffisent ; s'ajoutent `PRONOTE_PIN` et
     `PRONOTE_CLIENT_ID` (l'identifiant qui fait reconnaître l'« appareil » aux
     connexions suivantes) quand la double authentification est activée, et
     `PRONOTE_URL` seulement si l'espace Parents n'est pas celui inscrit dans
     `fetch.py` (`URL_DEFAUT`).
3. Créer le secret `PRONOTE_SITE_PASSPHRASE` : le mot de passe que la page
   demandera (à partager avec qui doit lire l'onglet).
4. Lancer une fois l'action « PRONOTE — actualités » (onglet Actions → Run
   workflow) : le fichier est créé, committé et le site redéployé.

Sans configuration, l'onglet affiche simplement « Pas encore de nouvelles ».
`python3 pronote/fetch.py --exemple --passphrase test` fabrique un fichier
fictif pour voir l'onglet en local (servir le dossier en http, par exemple
`python3 -m http.server`).

### Limites

pronotepy reproduit le protocole de l'application mobile ; un changement chez
Index Éducation peut casser la collecte jusqu'à une mise à jour de la
bibliothèque. Chaque source est lue indépendamment : si l'une échoue, les
autres s'affichent et l'erreur est notée au bas de l'onglet (`erreurs` du JSON).
L'action échoue — et GitHub prévient par courriel — si la connexion est refusée.
Tests : `python3 -m unittest discover pronote`.

## Fichier

- `planning-hebdomadaire.html` — source de la page, au format attendu par les
  Artifacts Claude : le fichier contient directement le `<title>`, les styles,
  le contenu et les scripts (l'enveloppe `<!doctype html><html><head><body>`
  est ajoutée à la publication).
- `pronote/` — collecte PRONOTE : `fetch.py` (script), `configurer.py`
  (préparation des secrets, en local), `exemple.py` (données fictives),
  `test_fetch.py`, et `actualites.json` produit par l'action.

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
- Feuille de style d'impression : toutes les sections sont imprimées (par la
  commande d'impression du navigateur — la page n'a pas de bouton dédié).
