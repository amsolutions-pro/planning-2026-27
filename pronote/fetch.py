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
import os
import pathlib
import re
import sys
import unicodedata
import uuid as uuidlib
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
ICI = pathlib.Path(__file__).resolve().parent
SORTIE = ICI / "actualites.json"
URL_DEFAUT = "https://0940575p.index-education.net/pronote/parent.html"

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


def prochain_jour_de_classe(jour: dt.date) -> dt.date:
    suivant = jour + dt.timedelta(days=1)
    while suivant.weekday() >= 5:  # samedi, dimanche
        suivant += dt.timedelta(days=1)
    return suivant


# ---------------------------------------------------------------- connexion

def connexion(env: dict = os.environ):
    import pronotepy

    jeton = env.get("PRONOTE_TOKEN_JSON", "").strip()
    pin = env.get("PRONOTE_PIN", "").strip() or None
    appareil = env.get("PRONOTE_DEVICE_NAME", "").strip() or "Planning famille"

    if jeton:
        creds = json.loads(jeton)
        client = pronotepy.ParentClient.token_login(
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
    client = pronotepy.ParentClient(
        url,
        username=utilisateur,
        password=mot_de_passe,
        account_pin=pin,
        client_identifier=env.get("PRONOTE_CLIENT_ID", "").strip() or None,
        device_name=appareil,
    )
    return client, "mot de passe"


# ---------------------------------------------------------------- collecte

class Collecte:
    def __init__(self, client, maintenant: dt.datetime) -> None:
        self.client = client
        self.maintenant = maintenant
        self.aujourdhui = maintenant.date()
        self.erreurs: list[str] = []
        self.enfants: list[dict] = []
        self.actualites: dict[str, dict] = {}  # id → actualité (dédoublonnée)

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
            self.client.set_child(info)
            for nom, collecteur in (
                ("devoirs", self.devoirs), ("cours", self.cours), ("notes", self.notes),
                ("vie scolaire", self.vie_scolaire), ("informations", self.informations),
                ("messages", self.messages),
            ):
                try:
                    collecteur(enfant)
                except Exception as e:  # une source en panne ne doit pas tout bloquer
                    self.erreurs.append(f"{enfant['nom']} · {nom} : {type(e).__name__} : {court(str(e), 160)}")

        cle = lambda a: (a["date"] or "", a.get("heure") or "")
        avenir = sorted((a for a in self.actualites.values() if a["horizon"] == "avenir"), key=cle)
        recent = sorted((a for a in self.actualites.values() if a["horizon"] != "avenir"), key=cle, reverse=True)
        liste = avenir + recent
        return {
            "version": 1,
            "mis_a_jour_le": self.maintenant.isoformat(timespec="minutes"),
            "etablissement": etablissement,
            "regles": {
                "important": [
                    "absence ou retard non justifié", "punition", "cours annulé ou modifié",
                    "contrôle annoncé", "devoir pour le prochain jour de classe non fait",
                    "note en dessous de 10/20", "sondage sans réponse", "message non lu",
                    "information sur une réunion, sortie, autorisation, orientation…",
                ],
            },
            "enfants": self.enfants,
            "actualites": liste,
            "erreurs": self.erreurs,
        }

    def ajoute(self, enfant: dict, item: dict) -> None:
        existant = self.actualites.get(item["id"])
        if existant:
            if enfant["id"] not in existant["enfants"]:
                existant["enfants"].append(enfant["id"])
            return
        item["enfants"] = [enfant["id"]]
        item.setdefault("heure", None)
        item.setdefault("matiere", None)
        item.setdefault("detail", "")
        item.setdefault("signale_le", iso_instant(self.maintenant))
        self.actualites[item["id"]] = item

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
                niveau, raison, type_ = "important", f"Mention « {mot} »", "controle"
            elif not hw.done and hw.date <= prochain:
                niveau, raison, type_ = "important", "Pour le prochain jour de classe, non fait", "devoir"
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
                    "niveau": "important",
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
                    niveau, raison = "important", "Note en dessous de 10/20"
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
            if ident in self.actualites:
                self.ajoute(enfant, {"id": ident})
                continue
            contenu = ""
            if details < MAX_DETAILS:
                details += 1
                try:
                    contenu = i.content() or ""
                except Exception:
                    contenu = ""
            texte = f"{i.title or ''} {i.category or ''} {contenu}"
            mot = contient(texte, MOTS_INFO_IMPORTANTE)
            if i.survey and not i.read:
                niveau, raison = "important", "Sondage sans réponse"
            elif mot:
                niveau, raison = "important", f"Mention « {mot} »"
            else:
                niveau, raison = "info", "Information" + (" non lue" if not i.read else "")
            self.ajoute(enfant, {
                "id": ident,
                "type": "sondage" if i.survey else "info",
                "niveau": niveau,
                "raison": raison,
                "titre": i.title or (i.category or "Information"),
                "detail": court(contenu),
                "auteur": i.author or "",
                "categorie": i.category or "",
                "date": iso_date(quand),
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
            ident = f"message:{d.id}"
            if ident in self.actualites:
                self.ajoute(enfant, {"id": ident})
                continue
            if details >= MAX_DETAILS:
                break
            details += 1
            msgs = list(d.messages)
            if not msgs:
                continue
            dernier = msgs[-1]
            if d.unread == 0 and dernier.created < depuis:
                continue
            non_lus = d.unread or 0
            auteur = dernier.author or "Vous"
            self.ajoute(enfant, {
                "id": ident,
                "type": "message",
                "niveau": "important" if non_lus and not d.closed else "info",
                "raison": f"{non_lus} message{'s' if non_lus > 1 else ''} non lu{'s' if non_lus > 1 else ''}"
                          if non_lus else "Discussion lue",
                "titre": d.subject or f"Discussion avec {d.creator or auteur}",
                "detail": court(f"{auteur} : {dernier.content}", 300),
                "auteur": d.creator or auteur,
                "date": iso_date(dernier.created),
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
    base = {"version": 1, "empreinte": empreinte(donnees), "mis_a_jour_le": donnees["mis_a_jour_le"]}
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


def resume(donnees: dict) -> str:
    lignes = []
    for e in donnees["enfants"]:
        miens = [a for a in donnees["actualites"] if e["id"] in a["enfants"]]
        imp = sum(1 for a in miens if a["niveau"] == "important")
        lignes.append(f"  {e['nom']} ({e['classe'] or '?'}) : {imp} important(s), {len(miens) - imp} autre(s)")
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
    args = p.parse_args(argv)

    passphrase = None if args.clair else (args.passphrase or os.environ.get("PRONOTE_SITE_PASSPHRASE") or None)
    maintenant = dt.datetime.now(PARIS)

    if args.exemple:
        from exemple import FauxClient
        client, mode = FauxClient(maintenant), "exemple"
    else:
        client, mode = connexion()
        if not getattr(client, "logged_in", True):
            print("Connexion refusée par PRONOTE (identifiants ?).", file=sys.stderr)
            return 2
    print(f"Connexion : {mode} · {len(client.children)} enfant(s)")

    # Le jeton a déjà tourné à la connexion : on le sauve avant tout le reste.
    if mode == "jeton" and os.environ.get("PRONOTE_TOKEN_SORTIE"):
        pathlib.Path(os.environ["PRONOTE_TOKEN_SORTIE"]).write_text(
            json.dumps(client.export_credentials()), encoding="utf-8")
        print("Nouveau jeton écrit (à remettre dans le secret PRONOTE_TOKEN_JSON).")

    donnees = Collecte(client, maintenant).tout()

    change = ecrire(donnees, args.sortie, passphrase, args.forcer)
    print(("Écrit" if change else "Inchangé") + f" : {args.sortie}" + (" (chiffré)" if passphrase else " (en clair)"))
    print(resume(donnees))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"change={'true' if change else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
