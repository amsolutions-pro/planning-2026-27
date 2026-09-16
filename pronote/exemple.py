"""Faux client PRONOTE : données fictives pour les tests et l'aperçu de l'onglet.

Reproduit les seuls attributs de pronotepy que `fetch.py` utilise, avec des
situations variées (devoir pour demain, contrôle, note basse, absence, sondage…).
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace as NS


def _o(**kw) -> NS:
    return NS(**kw)


class FauxPeriode:
    def __init__(self, nom, debut, fin, notes, moyennes, absences, retards, punitions,
                 generale=None, classe=None):
        self.name = nom
        self.start = dt.datetime.combine(debut, dt.time())
        self.end = dt.datetime.combine(fin, dt.time(23, 59))
        self.grades = notes
        self.averages = moyennes
        self.absences = absences
        self.delays = retards
        self.punishments = punitions
        self.overall_average = generale
        self.class_overall_average = classe


class FauxClient:
    """Deux enfants, chacun avec son lot de nouvelles."""

    def __init__(self, maintenant: dt.datetime) -> None:
        self.maintenant = maintenant
        j = maintenant.date()
        self.children = [
            _o(id="E1", name="MELIKSETYAN Narek", class_name="5F", establishment="Collège de démonstration"),
            _o(id="E2", name="MELIKSETYAN Annie", class_name="3F", establishment="Collège de démonstration"),
        ]
        self.logged_in = True
        self._courant = self.children[0]
        self._donnees = {"E1": self._narek(j, maintenant), "E2": self._annie(j, maintenant)}

    # -- interface pronotepy

    def set_child(self, enfant) -> None:
        if isinstance(enfant, str):
            enfant = next(c for c in self.children if c.name == enfant)
        self._courant = enfant

    @property
    def _d(self) -> dict:
        return self._donnees[self._courant.id]

    def homework(self, d1, d2):
        return [h for h in self._d["devoirs"] if d1 <= h.date <= d2]

    def lessons(self, d1, d2):
        return self._d["cours"]

    @property
    def periods(self):
        return self._d["periodes"]

    @property
    def current_period(self):
        return self._d["periodes"][0]

    def discussions(self):
        return self._d["discussions"]

    def information_and_surveys(self):
        return self._d["infos"]

    def export_credentials(self) -> dict:
        return {"pronote_url": "exemple", "username": "exemple", "password": "exemple", "uuid": "exemple",
                "client_identifier": "exemple"}

    # -- jeux de données

    @staticmethod
    def _matiere(nom):
        return _o(id=nom.lower(), name=nom)

    def _narek(self, j: dt.date, m: dt.datetime) -> dict:
        M = self._matiere
        demain = j + dt.timedelta(days=1)
        while demain.weekday() >= 5:
            demain += dt.timedelta(days=1)
        return {
            "devoirs": [
                _o(id="d1", subject=M("Mathématiques"), date=demain, done=False, files=[],
                   description="Exercices 12 à 15 p. 34 : fractions et nombres décimaux."),
                _o(id="d2", subject=M("Histoire-géo"), date=j + dt.timedelta(days=4), done=False, files=[_o()],
                   description="Contrôle sur le chapitre 1 : l'Empire byzantin. Réviser la fiche distribuée."),
                _o(id="d3", subject=M("Anglais LV1"), date=j + dt.timedelta(days=6), done=True, files=[],
                   description="Apprendre le vocabulaire de la leçon 2 (workbook p. 8)."),
                _o(id="d4", subject=M("Français"), date=j + dt.timedelta(days=9), done=False, files=[],
                   description="Lire le chapitre 3 du roman et répondre aux questions 1 à 5."),
            ],
            "cours": [
                _o(id="c1", canceled=True, status="Cours annulé", test=False, memo=None,
                   start=dt.datetime.combine(j + dt.timedelta(days=2), dt.time(8, 10)),
                   end=dt.datetime.combine(j + dt.timedelta(days=2), dt.time(9, 5)),
                   subject=M("SVT"), teacher_name="Mme DURAND", classroom="B12"),
                _o(id="c2", canceled=False, status=None, test=True, memo=None,
                   start=dt.datetime.combine(j + dt.timedelta(days=4), dt.time(10, 20)),
                   end=dt.datetime.combine(j + dt.timedelta(days=4), dt.time(11, 15)),
                   subject=M("Histoire-géo"), teacher_name="M. MARTIN", classroom="A03"),
                _o(id="c3", canceled=False, status=None, test=False, memo=None,
                   start=dt.datetime.combine(j + dt.timedelta(days=1), dt.time(13, 45)),
                   end=dt.datetime.combine(j + dt.timedelta(days=1), dt.time(14, 40)),
                   subject=M("EPS"), teacher_name="M. LOPEZ", classroom="Gymnase"),
            ],
            "periodes": [FauxPeriode(
                "Trimestre 1", j - dt.timedelta(days=15), j + dt.timedelta(days=90),
                notes=[
                    _o(id="n1", subject=M("Mathématiques"), grade="7,5", out_of="20", date=j - dt.timedelta(days=2),
                       average="11,2", coefficient="1", comment="Fractions"),
                    _o(id="n2", subject=M("Anglais LV1"), grade="16", out_of="20", date=j - dt.timedelta(days=5),
                       average="13,4", coefficient="1", comment="Vocabulaire"),
                    _o(id="n3", subject=M("Technologie"), grade="8", out_of="10", date=j - dt.timedelta(days=8),
                       average="7,1", coefficient="0,5", comment=""),
                ],
                moyennes=[
                    _o(subject=M("Mathématiques"), student="9,8", class_average="11,5", out_of="20"),
                    _o(subject=M("Anglais LV1"), student="15,2", class_average="13,1", out_of="20"),
                    _o(subject=M("Technologie"), student="16", class_average="14,2", out_of="20"),
                ],
                absences=[
                    _o(id="a1", from_date=dt.datetime.combine(j - dt.timedelta(days=3), dt.time(8, 10)),
                       to_date=dt.datetime.combine(j - dt.timedelta(days=3), dt.time(12, 10)),
                       justified=False, hours="4", reasons=[]),
                ],
                retards=[
                    _o(id="r1", date=dt.datetime.combine(j - dt.timedelta(days=6), dt.time(8, 10)), minutes=10,
                       justified=True, justification="Bus", reasons=["Transport"]),
                ],
                punitions=[],
                generale="12,4", classe="12,9",
            )],
            "discussions": [
                _o(id="m1", subject="Sortie au musée — autorisation", creator="M. MARTIN", unread=1, closed=False,
                   labels=[], messages=[
                       _o(author="M. MARTIN", created=m.replace(tzinfo=None) - dt.timedelta(hours=5),
                          content="Bonjour, merci de retourner l'autorisation signée avant vendredi."),
                   ]),
            ],
            "infos": [
                _o(id="i1", title="Réunion parents-professeurs 5e", author="Direction", read=False,
                   creation_date=m.replace(tzinfo=None) - dt.timedelta(days=1), start_date=None,
                   category="Information", survey=False, template=False,
                   content=lambda: "La réunion aura lieu le jeudi 8 octobre à 18h00 dans la salle polyvalente."),
                _o(id="i2", title="Menus de la cantine", author="Intendance", read=True,
                   creation_date=m.replace(tzinfo=None) - dt.timedelta(days=4), start_date=None,
                   category="Information", survey=False, template=False,
                   content=lambda: "Les menus du mois sont disponibles."),
            ],
        }

    def _annie(self, j: dt.date, m: dt.datetime) -> dict:
        M = self._matiere
        return {
            "devoirs": [
                _o(id="d5", subject=M("LCA latin"), date=j + dt.timedelta(days=3), done=False, files=[],
                   description="Traduire les phrases 1 à 6."),
                _o(id="d6", subject=M("Physique-chimie"), date=j + dt.timedelta(days=7), done=False, files=[],
                   description="Évaluation sur les états de la matière."),
            ],
            "cours": [
                _o(id="c4", canceled=False, status="Prof. absent", test=False, memo=None,
                   start=dt.datetime.combine(j + dt.timedelta(days=1), dt.time(16, 50)),
                   end=dt.datetime.combine(j + dt.timedelta(days=1), dt.time(17, 45)),
                   subject=M("LCA latin"), teacher_name="Mme BERNARD", classroom="C21"),
            ],
            "periodes": [FauxPeriode(
                "Trimestre 1", j - dt.timedelta(days=15), j + dt.timedelta(days=90),
                notes=[
                    _o(id="n4", subject=M("Français"), grade="14", out_of="20", date=j - dt.timedelta(days=1),
                       average="12", coefficient="2", comment="Rédaction"),
                    _o(id="n5", subject=M("Espagnol LV2"), grade="Absent", out_of="20", date=j - dt.timedelta(days=9),
                       average="13", coefficient="1", comment=""),
                ],
                moyennes=[
                    _o(subject=M("Français"), student="14,5", class_average="12,2", out_of="20"),
                    _o(subject=M("Espagnol LV2"), student="13", class_average="12,8", out_of="20"),
                ],
                absences=[],
                retards=[
                    _o(id="r2", date=dt.datetime.combine(j - dt.timedelta(days=1), dt.time(8, 10)), minutes=15,
                       justified=False, justification=None, reasons=[]),
                ],
                punitions=[
                    _o(id="p1", given=dt.datetime.combine(j - dt.timedelta(days=2), dt.time(14, 40)),
                       nature="Retenue", reasons=["Bavardages répétés"], circumstances="",
                       giver="M. PETIT", schedule=[_o(start=dt.datetime.combine(j + dt.timedelta(days=5), dt.time(16, 50)))]),
                ],
                generale="13,7", classe="12,5",
            )],
            "discussions": [
                _o(id="m1", subject="Sortie au musée — autorisation", creator="M. MARTIN", unread=1, closed=False,
                   labels=[], messages=[
                       _o(author="M. MARTIN", created=m.replace(tzinfo=None) - dt.timedelta(hours=5),
                          content="Bonjour, merci de retourner l'autorisation signée avant vendredi."),
                   ]),
                _o(id="m3", subject="Voyage en Espagne — autorisation de sortie", creator="Direction",
                   unread=0, closed=False, labels=[], messages=[
                       _o(author="Direction", created=m.replace(tzinfo=None) - dt.timedelta(days=3),
                          content="Le dossier est à rapporter signé avant la fin du mois."),
                   ]),
                _o(id="m2", subject="Absence en espagnol", creator=None, unread=0, closed=False,
                   labels=[], messages=[
                       _o(author=None, created=m.replace(tzinfo=None) - dt.timedelta(days=8),
                          content="Bonjour, Annie était chez le médecin."),
                       _o(author="Mme GARCIA", created=m.replace(tzinfo=None) - dt.timedelta(days=7),
                          content="Merci, c'est noté."),
                   ]),
            ],
            "infos": [
                _o(id="i3", title="Stage d'observation de 3e", author="Direction", read=False,
                   creation_date=m.replace(tzinfo=None) - dt.timedelta(days=2), start_date=None,
                   category="Information", survey=True, template=False,
                   content=lambda: "Merci d'indiquer si votre enfant a déjà trouvé un lieu de stage."),
                _o(id="i2", title="Menus de la cantine", author="Intendance", read=True,
                   creation_date=m.replace(tzinfo=None) - dt.timedelta(days=4), start_date=None,
                   category="Information", survey=False, template=False,
                   content=lambda: "Les menus du mois sont disponibles."),
            ],
        }
