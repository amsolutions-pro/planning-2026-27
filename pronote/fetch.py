#!/usr/bin/env python3
"""Récupère sur PRONOTE ce qui concerne les enfants et le classe : important / le reste.

Le résultat est écrit dans `pronote/actualites.json`, lu par l'onglet « Actualités »
du site. Si PRONOTE_SITE_PASSPHRASE est défini, le fichier est chiffré (AES-GCM) :
le dépôt étant public, rien de lisible n'est publié sans le mot de passe.

Connexion, au choix (variables d'environnement) :
  - PRONOTE_TOKEN_JSON : identifiants exportés par `configurer.py --qr` (jeton
    d'application mobile, tourne à chaque connexion : les nouveaux identifiants
    sont écrits dans PRONOTE_TOKEN_SORTIE pour être remis dans le secret) ;
  - PRONOTE_USERNAME + PRONOTE_PASSWORD (PRONOTE_URL si l'espace Parents n'est
    pas URL_DEFAUT), avec PRONOTE_PIN et PRONOTE_CLIENT_ID si le compte a la
    double authentification.

`python3 pronote/fetch.py --exemple` produit un fichier fictif pour voir l'onglet.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
import unicodedata
import uuid as uuidlib
from zoneinfo import ZoneInfo

log = logging.getLogger("pronote.fetch")
PARIS = ZoneInfo("Europe/Paris")
ICI = pathlib.Path(__file__).resolve().parent
SORTIE = ICI / "actualites.json"
URL_DEFAUT = "https://0940575p.index-education.net/pronote/parent.html"

# Marquage « lu » demandé depuis la page. Les identifiants viennent du dehors
# (ils traversent l'API GitHub) : on n'accepte que la forme exacte que le script
# produit lui-même, et jamais plus d'une poignée à la fois.
# Ce que la page a le droit de demander de marquer lu : une identité de
# communication, telle que `identite` la fabrique. Rien d'autre ne passe.
ID_MARQUABLE = re.compile(r"^(message|info|sondage)~[0-9a-f]{16}$")
MAX_MARQUAGES = 60
# Ce que le collège adresse à la famille, et qui ne vaut qu'une fois même
# lorsqu'il arrive sous chacun des enfants.
ACTU_COMMUNES = ("message", "info", "sondage")

# Plage horaire des passages automatiques, à Paris : personne ne lit l'onglet à
# 6 h du matin, et le soir les nouvelles du jour sont déjà tombées.
HEURE_MIN, HEURE_MAX = 7, 18

# Fenêtres de collecte, en jours.
DEVOIRS_JOURS = 14
COURS_JOURS = 7
NOTES_JOURS = 30
VIE_SCOLAIRE_JOURS = 30
INFOS_JOURS = 30
MESSAGES_JOURS = 21
# Requêtes supplémentaires (contenu d'une information, messages d'une discussion).
MAX_DETAILS = 15

ITERATIONS_KDF = 200_000
# Numéro du format publié, lisible sans le mot de passe : une page restée
# ouverte s'en sert pour voir qu'elle est plus vieille que le fichier, et
# proposer de se recharger plutôt que de le lire de travers.
#   1 : premier format
#   2 : l'identité d'une communication vient de son contenu, plus de son
#       numéro chez PRONOTE, qui diffère d'un enfant à l'autre
#   3 : de même pour tout le reste — PRONOTE renumérote à chaque session
VERSION_FICHIER = 3

MOTS_CONTROLE = (
    "contrôle", "controle", "évaluation", "evaluation", "interro", "devoir surveillé",
    "devoir maison", "brevet", "oral", "exposé", "expose", "dictée", "dictee",
    "test", " ds ", " dm ",
)
MOTS_INFO_IMPORTANTE = (
    "réunion", "reunion", "sortie", "voyage", "autorisation", "conseil de classe",
    "orientation", "stage", "brevet", "bourse", "inscription", "urgent", "rappel",
    "annul", "grève", "greve", "fermeture", "modification", "changement", "santé",
    "sante", "vaccin", "pai ", "photo de classe", "paiement", "facture",
    "carnet", "signature", "signer", "rendez-vous", "convocation", "absence du prof",
    "professeur absent", "remplacement", "portes ouvertes", "bulletin", "examen",
)

JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
        "sept.", "oct.", "nov.", "déc."]


# ---------------------------------------------------------------- utilitaires

def slug(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sans_accent.lower()).strip("-") or "enfant"


def prenom(nom_complet: str) -> str:
    """PRONOTE écrit « NOM Prénom » : le prénom est ce qui n'est pas en capitales."""
    mots = nom_complet.split()
    minuscules = [m for m in mots if not m.isupper()]
    return " ".join(minuscules) if minuscules else (mots[-1] if mots else "")


def jour_fr(d: dt.date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def heure_fr(t: dt.datetime | dt.time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def iso_date(d: dt.date | dt.datetime | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, dt.datetime):
        d = d.date()
    return d.isoformat()


def iso_instant(d: dt.datetime | dt.date | None) -> str | None:
    if d is None:
        return None
    if not isinstance(d, dt.datetime):
        d = dt.datetime.combine(d, dt.time())
    if d.tzinfo is None:
        d = d.replace(tzinfo=PARIS)
    return d.isoformat(timespec="minutes")


def court(texte: str | None, n: int = 400) -> str:
    texte = re.sub(r"\s+", " ", (texte or "")).strip()
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


def contient(texte: str, mots: tuple[str, ...]) -> str | None:
    bas = " " + (texte or "").lower() + " "
    for mot in mots:
        if mot in bas:
            return mot.strip()
    return None


def note_sur_20(note: str, bareme: str) -> float | None:
    try:
        n = float(str(note).replace(",", "."))
        b = float(str(bareme).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if b <= 0:
        return None
    return round(n / b * 20, 2)


def id_discussion(d) -> str:
    """Fabrique un identifiant pour une discussion, qui n'en expose pas.

    `Discussion` n'a pas d'attribut `id` — à la différence des messages et des
    informations. On s'appuie sur le message qui ancre la discussion, stable
    d'un passage à l'autre, avec deux replis si pronotepy change de structure.
    """
    ancre = getattr(d, "_participants_message_id", None)
    if not ancre:
        possessions = getattr(d, "_possessions", None) or []
        ancre = "-".join(str(p.get("N", "")) for p in possessions if isinstance(p, dict))
    if not ancre:
        ancre = f"{getattr(d, 'subject', '')}|{getattr(d, 'creator', '')}"
    return hashlib.sha1(str(ancre).encode()).hexdigest()[:16]


# Ce qui fait l'identité d'une nouvelle. Une communication se reconnaît à peu de
# chose : ce qu'on peut relire sans frais au moment de la marquer lue, et qui ne
# dépend pas de l'enfant sous lequel on la lit. Le travail scolaire y ajoute son
# descriptif, seul à distinguer deux devoirs de même matière et même échéance.
# Le classement, l'état lu ou fait, la date de signalement n'en sont pas : ils
# bougent sans que la nouvelle change.
CHAMPS_IDENTITE = ("type", "titre", "auteur", "date")
CHAMPS_IDENTITE_SCOLAIRE = CHAMPS_IDENTITE + ("categorie", "heure", "matiere", "sur20", "detail")


def identite(item: dict, enfant: str | None) -> str:
    """Identifiant d'une nouvelle, tiré de ce qu'elle dit.

    PRONOTE renumérote tout à chaque session : les identifiants d'un devoir,
    d'un cours ou d'une note ne survivent pas d'un passage à l'autre — un relevé
    en a vu 29 sur 39 changer en vingt minutes. Les reprendre tels quels
    réécrivait le fichier à chaque passage, faisait revenir le bouton « Vu » des
    nouvelles déjà vues, et envoyait au robot des numéros périmés qu'il ne
    retrouvait plus pour les marquer lues.

    `enfant` vaut None pour une communication : le même message adressé aux deux
    n'en fait qu'une, et un seul clic. Le tilde la distingue d'un identifiant
    PRONOTE, avec lequel elle ne doit jamais être confondue.
    """
    champs = CHAMPS_IDENTITE if enfant is None else CHAMPS_IDENTITE_SCOLAIRE
    brut = "|".join(str(item.get(c) or "") for c in champs)
    if enfant:
        brut = f"{enfant}|{brut}"
    return f"{item['type']}~{hashlib.sha1(brut.encode()).hexdigest()[:16]}"


def contenu_discussion(d) -> dict:
    """Ce qui identifie une discussion — la même chose au marquage et à la collecte."""
    msgs = list(d.messages)
    dernier = msgs[-1] if msgs else None
    auteur = (dernier.author if dernier else None) or "Vous"
    return {
        "type": "message",
        "titre": d.subject or f"Discussion avec {d.creator or auteur}",
        "auteur": d.creator or auteur,
        "date": iso_date(dernier.created) if dernier else "",
        "_dernier": dernier,
    }


def contenu_information(i) -> dict:
    """De même pour une information ou un sondage."""
    quand = i.start_date or i.creation_date
    return {
        "type": "sondage" if i.survey else "info",
        "titre": i.title or (i.category or "Information"),
        "auteur": i.author or "",
        "date": iso_date(quand) if quand else "",
        "_quand": quand,
    }


def prochain_jour_de_classe(jour: dt.date) -> dt.date:
    suivant = jour + dt.timedelta(days=1)
    while suivant.weekday() >= 5:  # samedi, dimanche
        suivant += dt.timedelta(days=1)
    return suivant


# ---------------------------------------------------------------- connexion

def classe_client():
    import pronotepy

    class ClientParent(pronotepy.ParentClient):
        """Quand pronotepy rouvre la session après une erreur, il revient au profil
        parent : on remet l'enfant en cours, sinon toutes les lectures suivantes
        portent sur le mauvais profil."""

        def refresh(self) -> None:
            nom = self._selected_child.name if getattr(self, "_selected_child", None) else None
            super().refresh()
            self.children = [
                pronotepy.dataClasses.ClientInfo(self, c)
                for c in self.parametres_utilisateur["dataSec"]["data"]["ressource"]["listeRessources"]
            ]
            if nom:
                self.set_child(nom)

    return ClientParent


def connexion(env: dict = os.environ):
    ClientParent = classe_client()
    jeton = env.get("PRONOTE_TOKEN_JSON", "").strip()
    pin = env.get("PRONOTE_PIN", "").strip() or None
    appareil = env.get("PRONOTE_DEVICE_NAME", "").strip() or "Planning famille"

    if jeton:
        creds = json.loads(jeton)
        client = ClientParent.token_login(
            pronote_url=creds["pronote_url"],
            username=creds["username"],
            password=creds["password"],
            uuid=creds["uuid"],
            client_identifier=creds.get("client_identifier"),
            account_pin=pin,
            device_name=appareil,
        )
        return client, "jeton"

    url = env.get("PRONOTE_URL", "").strip() or URL_DEFAUT
    utilisateur = env.get("PRONOTE_USERNAME", "").strip()
    mot_de_passe = env.get("PRONOTE_PASSWORD", "")
    if not (utilisateur and mot_de_passe):
        raise SystemExit(
            "Identifiants manquants : définir PRONOTE_TOKEN_JSON, ou "
            "PRONOTE_USERNAME et PRONOTE_PASSWORD (voir README)."
        )
    client = ClientParent(
        url,
        username=utilisateur,
        password=mot_de_passe,
        account_pin=pin,
        client_identifier=env.get("PRONOTE_CLIENT_ID", "").strip() or None,
        device_name=appareil,
    )
    return client, "mot de passe"


# ---------------------------------------------------------------- collecte

def ids_a_marquer(brut: str) -> list[str]:
    """Trie les identifiants reçus : seuls ceux de la forme attendue passent."""
    vus, propres = set(), []
    for morceau in re.split(r"[,\s]+", brut or ""):
        if morceau and ID_MARQUABLE.match(morceau) and morceau not in vus:
            vus.add(morceau)
            propres.append(morceau)
    if len(propres) > MAX_MARQUAGES:
        log.warning("%d identifiants reçus, on s'arrête à %d", len(propres), MAX_MARQUAGES)
        propres = propres[:MAX_MARQUAGES]
    return propres


def marquer_information(client, i) -> None:
    """Marque une information lue, au nom de l'enfant.

    pronotepy adresse le marquage à `client.info`, la ressource fixée à la
    connexion — sur un compte parent, c'est le parent, jamais l'enfant que
    `set_child` a choisi. PRONOTE accepte la requête et n'en fait rien : le
    robot croyait avoir marqué, et la pastille du collège ne bougeait pas.

    Quelle ressource PRONOTE attend ici pour un parent, je ne peux pas le
    vérifier d'ici : on pose les deux, l'enfant d'abord — celui que porte la
    signature de la requête — puis celle de pronotepy. Marquer deux fois est
    sans effet de bord, et les compteurs de non-lus encadrant le passage
    diront laquelle a porté.
    """
    publics = []
    enfant = getattr(client, "_selected_child", None)
    if enfant is not None:
        publics.append(enfant.id)
    if getattr(client, "info", None) is not None and client.info.id not in publics:
        publics.append(client.info.id)
    for public in publics:
        client.post("SaisieActualites", 8, {
            "listeActualites": [{
                "N": i.id,
                "validationDirecte": True,
                "genrePublic": 4,
                "public": {"N": public, "G": 4},
                "lue": True,
            }],
            "saisieActualite": False,
        })
    i.read = True


def non_lus(client) -> str:
    """Ce que PRONOTE compte encore de non-lus, enfant par enfant.

    Des nombres, rien du contenu : le journal de l'action est public. Encadrant
    le marquage, ils disent si PRONOTE l'a vraiment pris — le robot, lui, ne
    sait que s'il a posté sans erreur.
    """
    bouts = []
    for info in client.children:
        try:
            client.set_child(info.name)
            d = len(list(client.discussions(only_unread=True)))
            i = len(list(client.information_and_surveys(only_unread=True)))
            bouts.append(f"{prenom(info.name)} {d} msg / {i} info")
        except Exception as e:
            bouts.append(f"{prenom(info.name)} ? ({type(e).__name__})")
    return " · ".join(bouts)


def marquer_lu(client, ids: list[str]) -> tuple[list[str], list[str]]:
    """Passe en « lu » sur PRONOTE les discussions et informations demandées.

    La page envoie des identités, pas des numéros PRONOTE : ceux du fichier
    viennent d'une session passée et ne désignent plus rien. On recalcule donc
    l'identité de chaque communication encore non lue, et on marque celles qui
    répondent à l'appel.

    On parcourt les deux enfants jusqu'au bout, sans s'arrêter à la première
    copie : le collège qui écrit aux deux laisse un exemplaire de chaque côté,
    et n'en marquer qu'un ne fait pas descendre le compte des non-lus.

    Renvoie ce qui a été marqué, et ce qui n'a pas été retrouvé.
    """
    demandes = set(ids)
    faits: set[str] = set()
    for info in client.children:
        client.set_child(info.name)
        for source, contenu, marque in (
            (lambda: client.discussions(only_unread=True), contenu_discussion, lambda o: o.mark_as(True)),
            (lambda: client.information_and_surveys(only_unread=True), contenu_information,
             lambda o: marquer_information(client, o)),
        ):
            try:
                for objet in source():
                    ident = identite(contenu(objet), None)
                    if ident in demandes:
                        marque(objet)
                        faits.add(ident)
            except Exception as e:
                log.warning("marquage %s : %s", info.name, court(str(e), 160))
    return sorted(faits), sorted(demandes - faits)


def memoire_precedente(chemin: pathlib.Path, passphrase: str | None) -> dict[str, str]:
    """Quand chaque nouvelle a été vue pour la première fois.

    Un devoir ou un cours n'a pas de date d'apparition propre : sans mémoire on
    leur donnait l'heure du passage, si bien que le fichier changeait à chaque
    fois — commit inutile, site republié pour rien, et tout marqué « Nouveau ».
    """
    try:
        env = json.loads(chemin.read_text(encoding="utf-8"))
        donnees = dechiffrer(env, passphrase or "") if env.get("chiffre") else env.get("donnees")
    except Exception as e:
        log.info("pas de mémoire du passage précédent (%s)", type(e).__name__)
        return {}
    return {a["id"]: a["signale_le"]
            for a in (donnees or {}).get("actualites", []) if a.get("signale_le")}


class Collecte:
    def __init__(self, client, maintenant: dt.datetime, reconnecter=None,
                 memoire: dict[str, str] | None = None) -> None:
        self.client = client
        self.reconnecter = reconnecter
        self.memoire = memoire or {}
        self.maintenant = maintenant
        self.aujourdhui = maintenant.date()
        self.erreurs: list[str] = []
        self.enfants: list[dict] = []
        self.actualites: dict[str, dict] = {}  # identité → actualité (dédoublonnée)
        self.connus: dict[str, dict] = {}      # identifiant PRONOTE → son actualité

    # -- squelette

    def tout(self) -> dict:
        etablissement = ""
        for info in self.client.children:
            ident = slug(prenom(info.name))
            enfant = {
                "id": ident,
                "nom": prenom(info.name) or info.name,
                "nom_complet": info.name,
                "classe": getattr(info, "class_name", "") or "",
                "moyennes": [],
                "moyenne_generale": None,
                "moyenne_classe": None,
            }
            if not etablissement:
                try:
                    etablissement = info.establishment or ""
                except Exception:  # propriété absente selon les versions
                    etablissement = ""
            self.enfants.append(enfant)
            self.client.set_child(info.name)
            for nom, collecteur in (
                ("devoirs", self.devoirs), ("cours", self.cours), ("notes", self.notes),
                ("vie scolaire", self.vie_scolaire), ("informations", self.informations),
                ("messages", self.messages),
            ):
                self.lire(enfant, nom, collecteur)

        cle = lambda a: (a["date"] or "", a.get("heure") or "")
        avenir = sorted((a for a in self.actualites.values() if a["horizon"] == "avenir"), key=cle)
        recent = sorted((a for a in self.actualites.values() if a["horizon"] != "avenir"), key=cle, reverse=True)
        liste = avenir + recent
        return {
            "version": VERSION_FICHIER,
            # À la seconde : la page s'en sert pour reconnaître un passage
            # qu'elle a elle-même demandé, même s'il n'a rien trouvé de neuf.
            "mis_a_jour_le": self.maintenant.isoformat(timespec="seconds"),
            "etablissement": etablissement,
            # Où la page renvoie les « Vu » ; chiffré avec le reste du fichier.
            "depot": os.environ.get("GITHUB_REPOSITORY", ""),
            "regles": {
                "important": [
                    "absence ou retard non justifié", "punition", "cours annulé ou modifié",
                    "message non lu", "sondage sans réponse",
                    "message ou information non lus parlant de réunion, sortie, autorisation…",
                ],
                "scolaire": [
                    "contrôle annoncé", "devoir pour le prochain jour de classe non fait",
                    "note en dessous de 10/20",
                ],
            },
            "enfants": self.enfants,
            "actualites": liste,
            "erreurs": self.erreurs,
        }

    def lire(self, enfant: dict, nom: str, collecteur) -> None:
        """Une source en panne ne bloque pas les autres ; PRONOTE ferme parfois la
        session en cours de route (« La page a expiré ») : on en rouvre une
        neuve et on réessaie une fois."""
        try:
            collecteur(enfant)
            return
        except Exception as e:
            premiere = f"{type(e).__name__} : {court(str(e), 160)}"
            log.warning("%s · %s : %s", enfant["nom"], nom, premiere)
        if not self.reconnecter:
            self.erreurs.append(f"{enfant['nom']} · {nom} : {premiere}")
            return
        try:
            log.info("nouvelle session pour réessayer %s · %s", enfant["nom"], nom)
            self.client = self.reconnecter()
            self.client.set_child(enfant["nom_complet"])
            collecteur(enfant)
        except Exception as e:
            self.erreurs.append(
                f"{enfant['nom']} · {nom} : {premiere} ; après reconnexion : {type(e).__name__} : {court(str(e), 160)}")

    def rattache(self, enfant: dict, connu: dict, chez_pronote: str) -> None:
        if enfant["id"] not in connu["enfants"]:
            connu["enfants"].append(enfant["id"])
        self.connus[chez_pronote] = connu

    def ajoute(self, enfant: dict, item: dict) -> None:
        # Le numéro que PRONOTE donne à l'objet ne sert qu'ici, le temps du
        # passage : il dédouble les lectures des deux enfants sans relire. Il ne
        # va pas dans le fichier, il ne vaudra plus rien à la prochaine session.
        chez_pronote = item.pop("id")
        # Une communication est la même pour les deux enfants ; un devoir, non.
        ident = identite(item, None if item["type"] in ACTU_COMMUNES else enfant["id"])
        connu = self.connus.get(chez_pronote) or self.actualites.get(ident)
        if connu:
            self.rattache(enfant, connu, chez_pronote)
            return
        item["id"] = ident
        item["enfants"] = [enfant["id"]]
        item.setdefault("heure", None)
        item.setdefault("matiere", None)
        item.setdefault("detail", "")
        item.setdefault("signale_le", self.memoire.get(ident) or iso_instant(self.maintenant))
        self.actualites[ident] = item
        self.connus[chez_pronote] = item

    def periodes_en_cours(self):
        periodes = []
        for p in self.client.periods:
            try:
                if p.start.date() <= self.aujourdhui <= p.end.date():
                    periodes.append(p)
            except AttributeError:
                continue
        if not periodes:
            periodes = [self.client.current_period]
        return periodes

    # -- devoirs

    def devoirs(self, enfant: dict) -> None:
        limite = self.aujourdhui + dt.timedelta(days=DEVOIRS_JOURS)
        prochain = prochain_jour_de_classe(self.aujourdhui)
        for hw in self.client.homework(self.aujourdhui, limite):
            texte = hw.description or ""
            mot = contient(texte, MOTS_CONTROLE)
            pieces = 0
            try:
                pieces = len(hw.files)
            except Exception:
                pass
            if mot and not hw.done:
                niveau, raison, type_ = "scolaire", f"Mention « {mot} »", "controle"
            elif not hw.done and hw.date <= prochain:
                niveau, raison, type_ = "scolaire", "Pour le prochain jour de classe, non fait", "devoir"
            else:
                niveau, raison, type_ = "info", "Devoir fait" if hw.done else "Devoir à venir", "devoir"
            self.ajoute(enfant, {
                "id": f"devoir:{hw.id}",
                "type": type_,
                "niveau": niveau,
                "raison": raison,
                "titre": f"{hw.subject.name} — pour {jour_fr(hw.date)}",
                "detail": court(texte),
                "matiere": hw.subject.name,
                "date": iso_date(hw.date),
                "horizon": "avenir",
                "fait": bool(hw.done),
                "pieces_jointes": pieces,
            })

    # -- cours annulés, modifiés, contrôles prévus

    def cours(self, enfant: dict) -> None:
        limite = self.aujourdhui + dt.timedelta(days=COURS_JOURS)
        vus = set()
        for lecon in self.client.lessons(self.aujourdhui, limite):
            if not (lecon.canceled or lecon.status or lecon.test):
                continue
            matiere = lecon.subject.name if lecon.subject else "Cours"
            cle = (lecon.start, matiere, bool(lecon.canceled), lecon.status or "")
            if cle in vus:
                continue
            vus.add(cle)
            plage = f"{heure_fr(lecon.start)} → {heure_fr(lecon.end)}" if lecon.end else heure_fr(lecon.start)
            if lecon.canceled or lecon.status:
                statut = lecon.status or "Cours annulé"
                self.ajoute(enfant, {
                    "id": f"cours:{lecon.id}",
                    "type": "cours",
                    "niveau": "important",
                    "raison": statut,
                    "titre": f"{statut} — {matiere}, {jour_fr(lecon.start.date())} {plage}",
                    "detail": " · ".join(x for x in (lecon.teacher_name, lecon.classroom, lecon.memo) if x),
                    "matiere": matiere,
                    "date": iso_date(lecon.start),
                    "heure": heure_fr(lecon.start),
                    "horizon": "avenir",
                })
            if lecon.test:
                self.ajoute(enfant, {
                    "id": f"controle:{lecon.id}",
                    "type": "controle",
                    "niveau": "scolaire",
                    "raison": "Contrôle prévu",
                    "titre": f"Contrôle — {matiere}, {jour_fr(lecon.start.date())} {plage}",
                    "detail": lecon.teacher_name or "",
                    "matiere": matiere,
                    "date": iso_date(lecon.start),
                    "heure": heure_fr(lecon.start),
                    "horizon": "avenir",
                })

    # -- notes et moyennes

    def notes(self, enfant: dict) -> None:
        periode = self.client.current_period
        depuis = self.aujourdhui - dt.timedelta(days=NOTES_JOURS)
        for g in periode.grades:
            if g.date < depuis:
                continue
            sur20 = note_sur_20(g.grade, g.out_of)
            if sur20 is None:
                titre = f"{g.subject.name} — {g.grade}"
                niveau, raison = "info", "Note non chiffrée"
            else:
                titre = f"{g.subject.name} — {g.grade}/{g.out_of}"
                if abs(float(str(g.out_of).replace(",", ".")) - 20) > 0.01:
                    titre += f" ({sur20:g}/20)"
                if sur20 < 10:
                    niveau, raison = "scolaire", "Note en dessous de 10/20"
                else:
                    niveau, raison = "info", "Note au-dessus de 10/20"
            morceaux = []
            if g.comment:
                morceaux.append(g.comment)
            if g.average:
                morceaux.append(f"moyenne de la classe {g.average}")
            if g.coefficient and str(g.coefficient) not in ("1", "1.0", "1,00"):
                morceaux.append(f"coef. {g.coefficient}")
            self.ajoute(enfant, {
                "id": f"note:{g.id}",
                "type": "note",
                "niveau": niveau,
                "raison": raison,
                "titre": titre,
                "detail": court(" · ".join(morceaux)),
                "matiere": g.subject.name,
                "date": iso_date(g.date),
                "horizon": "recent",
                "signale_le": iso_instant(g.date),
                "sur20": sur20,
            })
        try:
            enfant["moyennes"] = [
                {"matiere": m.subject.name, "eleve": m.student, "classe": m.class_average, "sur": m.out_of}
                for m in periode.averages
            ]
            enfant["moyenne_generale"] = periode.overall_average or None
            enfant["moyenne_classe"] = periode.class_overall_average or None
            enfant["periode"] = periode.name
        except Exception as e:
            self.erreurs.append(f"{enfant['nom']} · moyennes : {type(e).__name__} : {court(str(e), 160)}")

    # -- absences, retards, punitions

    def vie_scolaire(self, enfant: dict) -> None:
        depuis = self.maintenant - dt.timedelta(days=VIE_SCOLAIRE_JOURS)
        depuis = depuis.replace(tzinfo=None)
        for p in self.periodes_en_cours():
            for a in p.absences:
                if a.from_date < depuis:
                    continue
                motif = ", ".join(a.reasons) if a.reasons else ""
                plage = f"{jour_fr(a.from_date.date())} {heure_fr(a.from_date)} → "
                plage += (heure_fr(a.to_date) if a.to_date.date() == a.from_date.date()
                          else f"{jour_fr(a.to_date.date())} {heure_fr(a.to_date)}")
                self.ajoute(enfant, {
                    "id": f"absence:{a.id}",
                    "type": "absence",
                    "niveau": "info" if a.justified else "important",
                    "raison": "Absence justifiée" if a.justified else "Absence non justifiée",
                    "titre": f"Absence — {plage}",
                    "detail": " · ".join(x for x in (motif, f"{a.hours} h" if a.hours else "") if x),
                    "date": iso_date(a.from_date),
                    "heure": heure_fr(a.from_date),
                    "horizon": "recent",
                    "signale_le": iso_instant(a.from_date),
                    "justifie": bool(a.justified),
                })
            for r in p.delays:
                if r.date < depuis:
                    continue
                motif = ", ".join(r.reasons) if r.reasons else ""
                self.ajoute(enfant, {
                    "id": f"retard:{r.id}",
                    "type": "retard",
                    "niveau": "info" if r.justified else "important",
                    "raison": "Retard justifié" if r.justified else "Retard non justifié",
                    "titre": f"Retard de {r.minutes} min — {jour_fr(r.date.date())} {heure_fr(r.date)}",
                    "detail": " · ".join(x for x in (motif, r.justification or "") if x),
                    "date": iso_date(r.date),
                    "heure": heure_fr(r.date),
                    "horizon": "recent",
                    "signale_le": iso_instant(r.date),
                    "justifie": bool(r.justified),
                })
            for s in p.punishments:
                donnee = s.given
                date = donnee.date() if isinstance(donnee, dt.datetime) else donnee
                if dt.datetime.combine(date, dt.time()) < depuis:
                    continue
                quand = jour_fr(date) + (f" {heure_fr(donnee)}" if isinstance(donnee, dt.datetime) else "")
                programme = ""
                if s.schedule:
                    debut = s.schedule[0].start
                    programme = "prévue " + jour_fr(debut.date() if isinstance(debut, dt.datetime) else debut)
                    if isinstance(debut, dt.datetime):
                        programme += f" {heure_fr(debut)}"
                detail = " · ".join(x for x in (
                    ", ".join(s.reasons) if s.reasons else "", s.circumstances, programme,
                    f"par {s.giver}" if s.giver else "",
                ) if x)
                self.ajoute(enfant, {
                    "id": f"punition:{s.id}",
                    "type": "punition",
                    "niveau": "important",
                    "raison": s.nature or "Punition",
                    "titre": f"{s.nature or 'Punition'} — {quand}",
                    "detail": court(detail),
                    "date": iso_date(date),
                    "horizon": "recent",
                    "signale_le": iso_instant(donnee),
                })

    # -- informations et sondages

    def informations(self, enfant: dict) -> None:
        depuis = (self.maintenant - dt.timedelta(days=INFOS_JOURS)).replace(tzinfo=None)
        details = 0
        for i in self.client.information_and_surveys():
            if getattr(i, "template", False):
                continue
            quand = i.start_date or i.creation_date
            if quand is None or (i.read and quand < depuis):
                continue
            ident = f"info:{i.id}"
            if ident in self.connus:
                self.rattache(enfant, self.connus[ident], ident)
                continue
            base = contenu_information(i)
            contenu = ""
            if details < MAX_DETAILS:
                details += 1
                try:
                    contenu = i.content() or ""
                except Exception:
                    contenu = ""
            texte = f"{i.title or ''} {i.category or ''} {contenu}"
            mot = contient(texte, MOTS_INFO_IMPORTANTE)
            # Lue, une communication n'est plus « importante » : l'important est
            # ce qui attend encore votre attention. Sans quoi une information
            # parlant de réunion y restait pour toujours, et il fallait la
            # masquer à la main — un « Vu » de plus à chaque fois, que rien ne
            # venait jamais reprendre.
            if i.survey and not i.read:
                niveau, raison = "important", "Sondage sans réponse"
            elif mot and not i.read:
                niveau, raison = "important", f"Mention « {mot} »"
            else:
                niveau, raison = "info", "Information" + (" non lue" if not i.read else "")
            self.ajoute(enfant, {
                "id": ident,
                "type": base["type"],
                "niveau": niveau,
                "raison": raison,
                "titre": base["titre"],
                # Le descriptif n'est lu que pour les premières informations : il
                # ne peut pas entrer dans l'identité, il changerait avec l'ordre.
                "detail": court(contenu),
                "auteur": base["auteur"],
                "categorie": i.category or "",
                "date": base["date"],
                "horizon": "recent",
                "signale_le": iso_instant(quand),
                "lu": bool(i.read),
            })

    # -- messagerie

    def messages(self, enfant: dict) -> None:
        depuis = (self.maintenant - dt.timedelta(days=MESSAGES_JOURS)).replace(tzinfo=None)
        details = 0
        for d in self.client.discussions():
            if "Trash" in (d.labels or []) or "Drafts" in (d.labels or []):
                continue
            ident = f"message:{id_discussion(d)}"
            if ident in self.connus:
                self.rattache(enfant, self.connus[ident], ident)
                continue
            if details >= MAX_DETAILS:
                break
            details += 1
            base = contenu_discussion(d)
            dernier = base["_dernier"]
            if dernier is None:
                continue
            if d.unread == 0 and dernier.created < depuis:
                continue
            non_lus = d.unread or 0
            auteur = dernier.author or "Vous"
            # Un message déjà lu peut rester à traiter : on relit son objet et son
            # dernier texte à la recherche de ce qui demande une réponse.
            mot = contient(f"{d.subject or ''} {dernier.content or ''}", MOTS_INFO_IMPORTANTE)
            if non_lus and not d.closed:
                niveau = "important"
                raison = (f"Mention « {mot} »" if mot else
                          f"{non_lus} message{'s' if non_lus > 1 else ''} non lu{'s' if non_lus > 1 else ''}")
            else:
                niveau, raison = "info", "Discussion lue"
            self.ajoute(enfant, {
                "id": ident,
                "type": base["type"],
                "niveau": niveau,
                "raison": raison,
                "titre": base["titre"],
                "detail": court(f"{auteur} : {dernier.content}", 300),
                "auteur": base["auteur"],
                "date": base["date"],
                "heure": heure_fr(dernier.created),
                "horizon": "recent",
                "signale_le": iso_instant(dernier.created),
                "lu": non_lus == 0,
                "non_lus": non_lus,
            })


# ---------------------------------------------------------------- sortie

def empreinte(donnees: dict) -> str:
    sans_date = {k: v for k, v in donnees.items() if k != "mis_a_jour_le"}
    brut = json.dumps(sans_date, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(brut.encode()).hexdigest()


def enveloppe(donnees: dict, passphrase: str | None) -> dict:
    texte = json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))
    base = {"version": VERSION_FICHIER, "empreinte": empreinte(donnees),
            "mis_a_jour_le": donnees["mis_a_jour_le"]}
    if not passphrase:
        return {**base, "chiffre": False, "donnees": donnees}

    from Crypto.Cipher import AES
    from Crypto.Hash import SHA256
    from Crypto.Protocol.KDF import PBKDF2

    sel = os.urandom(16)
    iv = os.urandom(12)
    cle = PBKDF2(passphrase.encode(), sel, dkLen=32, count=ITERATIONS_KDF, hmac_hash_module=SHA256)
    chiffreur = AES.new(cle, AES.MODE_GCM, nonce=iv)
    ct, tag = chiffreur.encrypt_and_digest(texte.encode())
    b64 = lambda b: base64.b64encode(b).decode()
    return {
        **base,
        "chiffre": True,
        "kdf": {"nom": "PBKDF2-SHA256", "iterations": ITERATIONS_KDF, "sel": b64(sel)},
        "iv": b64(iv),
        "donnees": b64(ct + tag),
    }


def dechiffrer(env: dict, passphrase: str) -> dict:
    """Inverse d'`enveloppe`, pour les tests et la vérification locale."""
    from Crypto.Cipher import AES
    from Crypto.Hash import SHA256
    from Crypto.Protocol.KDF import PBKDF2

    if not env.get("chiffre"):
        return env["donnees"]
    sel = base64.b64decode(env["kdf"]["sel"])
    cle = PBKDF2(passphrase.encode(), sel, dkLen=32, count=env["kdf"]["iterations"], hmac_hash_module=SHA256)
    brut = base64.b64decode(env["donnees"])
    dechiffreur = AES.new(cle, AES.MODE_GCM, nonce=base64.b64decode(env["iv"]))
    texte = dechiffreur.decrypt_and_verify(brut[:-16], brut[-16:])
    return json.loads(texte.decode())


def ecrire(donnees: dict, chemin: pathlib.Path, passphrase: str | None, forcer: bool = False) -> bool:
    """Écrit le fichier ; renvoie False s'il était déjà à jour (rien n'est réécrit)."""
    nouvelle = empreinte(donnees)
    if chemin.exists() and not forcer:
        try:
            ancienne = json.loads(chemin.read_text(encoding="utf-8")).get("empreinte")
        except (ValueError, OSError):
            ancienne = None
        if ancienne == nouvelle:
            return False
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(enveloppe(donnees, passphrase), ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    return True


def identites(memoire: dict[str, str], donnees: dict) -> str:
    """Combien de nouvelles ont gardé leur identité d'un passage à l'autre.

    Le « Vu » du navigateur est rangé sous cet identifiant : s'il bouge sans
    raison, la marque se perd et la nouvelle « revient ». Des comptes, rien du
    contenu — le journal de l'action est public.
    """
    if not memoire:
        return "  identités : pas de passage précédent à comparer"
    avant, apres = set(memoire), {a["id"] for a in donnees["actualites"]}
    return (f"  identités : {len(avant & apres)} gardée(s), {len(apres - avant)} nouvelle(s), "
            f"{len(avant - apres)} disparue(s)")


def resume(donnees: dict) -> str:
    lignes = []
    for e in donnees["enfants"]:
        miens = [a for a in donnees["actualites"] if e["id"] in a["enfants"]]
        compte = lambda n: sum(1 for a in miens if a["niveau"] == n)
        lignes.append(f"  {e['nom']} ({e['classe'] or '?'}) : {compte('important')} important(s), "
                      f"{compte('scolaire')} scolaire(s), {compte('info')} autre(s)")
    for err in donnees["erreurs"]:
        lignes.append(f"  ! {err}")
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--exemple", action="store_true", help="données fictives, sans connexion")
    p.add_argument("--sortie", type=pathlib.Path, default=SORTIE)
    p.add_argument("--passphrase", default=None, help="sinon PRONOTE_SITE_PASSPHRASE")
    p.add_argument("--clair", action="store_true", help="ne pas chiffrer, même si un mot de passe est défini")
    p.add_argument("--forcer", action="store_true", help="réécrire même si rien n'a changé")
    p.add_argument("--heures-ouvrees", action="store_true",
                   help=f"ne rien faire hors de {HEURE_MIN} h – {HEURE_MAX} h (heure de Paris)")
    p.add_argument("--marquer-lu", default="", metavar="IDS",
                   help="passer ces nouvelles en « lu » sur PRONOTE (message:N, info:N)")
    args = p.parse_args(argv)

    heure = dt.datetime.now(PARIS).hour
    if args.heures_ouvrees and not (HEURE_MIN <= heure <= HEURE_MAX):
        print(f"{heure} h à Paris : hors de la plage {HEURE_MIN} h – {HEURE_MAX} h, rien à faire.")
        return 0

    passphrase = None if args.clair else (args.passphrase or os.environ.get("PRONOTE_SITE_PASSPHRASE") or None)
    maintenant = dt.datetime.now(PARIS)
    # Le journal de pronotepy dit ce que PRONOTE répond ; GitHub masque les secrets.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s", stream=sys.stderr)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    reconnecter = None
    if args.exemple:
        from exemple import FauxClient
        client, mode = FauxClient(maintenant), "exemple"
    else:
        client, mode = connexion()
        if not getattr(client, "logged_in", True):
            print("Connexion refusée par PRONOTE (identifiants ?).", file=sys.stderr)
            return 2
        if mode == "mot de passe":
            reconnecter = lambda: connexion()[0]
    print(f"Connexion : {mode} · {len(client.children)} enfant(s)")

    ids = ids_a_marquer(args.marquer_lu)
    if ids:
        print(f"Non lus avant : {non_lus(client)}")
        faits, introuvables = marquer_lu(client, ids)
        detail = " · ".join(f"{n} {nom}" for nom, n in (
            ("message(s)", sum(1 for f in faits if f.startswith("message~"))),
            ("information(s)", sum(1 for f in faits if f.startswith(("info~", "sondage~")))),
        ) if n)
        print(f"Marqué lu sur PRONOTE : {len(faits)}/{len(ids)}"
              + (f" ({detail})" if detail else "")
              + (f" · introuvables : {len(introuvables)}" if introuvables else ""))
        print(f"Non lus après : {non_lus(client)}")

    # Le jeton a déjà tourné à la connexion : on le sauve avant tout le reste.
    if mode == "jeton" and os.environ.get("PRONOTE_TOKEN_SORTIE"):
        pathlib.Path(os.environ["PRONOTE_TOKEN_SORTIE"]).write_text(
            json.dumps(client.export_credentials()), encoding="utf-8")
        print("Nouveau jeton écrit (à remettre dans le secret PRONOTE_TOKEN_JSON).")

    memoire = memoire_precedente(args.sortie, passphrase)
    donnees = Collecte(client, maintenant, reconnecter, memoire).tout()

    change = ecrire(donnees, args.sortie, passphrase, args.forcer)
    print(("Écrit" if change else "Inchangé") + f" : {args.sortie}" + (" (chiffré)" if passphrase else " (en clair)"))
    print(identites(memoire, donnees))
    print(resume(donnees))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"change={'true' if change else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
