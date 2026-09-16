"""Tests de fetch.py sur le faux client : python3 -m unittest discover pronote"""

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fetch  # noqa: E402
from exemple import FauxClient  # noqa: E402

MAINTENANT = dt.datetime(2026, 9, 16, 10, 0, tzinfo=fetch.PARIS)  # un mercredi


def collecte():
    return fetch.Collecte(FauxClient(MAINTENANT), MAINTENANT).tout()


def id_message(ancre):
    """Les discussions n'ont pas d'identifiant : le nôtre vient du message d'ancrage."""
    return "message:" + fetch.id_discussion(SimpleNamespace(_participants_message_id=ancre))


class ConformitePronotepy(unittest.TestCase):
    """Le faux client ne doit exposer que ce que pronotepy expose vraiment.

    Sans ce garde-fou, `Discussion.id` — qui n'existe pas — est passé au travers
    des tests et n'a échoué que devant le vrai serveur.
    """

    def setUp(self):
        try:
            import pronotepy.dataClasses as dc
        except ImportError:  # pragma: no cover
            self.skipTest("pronotepy n'est pas installé")
        self.dc = dc
        self.client = FauxClient(MAINTENANT)

    def test_discussion_na_pas_d_identifiant(self):
        self.assertNotIn("id", dir(self.dc.Discussion))

    def test_attributs_connus_de_pronotepy(self):
        periode = self.client.current_period
        cas = [
            ("enfant", self.client.children, self.dc.ClientInfo),
            ("discussion", self.client.discussions(), self.dc.Discussion),
            ("information", self.client.information_and_surveys(), self.dc.Information),
            ("devoir", self.client.homework(MAINTENANT.date(), MAINTENANT.date() + dt.timedelta(days=30)),
             self.dc.Homework),
            ("cours", self.client.lessons(MAINTENANT.date(), MAINTENANT.date()), self.dc.Lesson),
            ("note", periode.grades, self.dc.Grade),
            ("moyenne", periode.averages, self.dc.Average),
            ("absence", periode.absences, self.dc.Absence),
            ("retard", periode.delays, self.dc.Delay),
            ("punition", periode.punishments, self.dc.Punishment),
            ("période", [periode], self.dc.Period),
        ]
        for nom, objets, classe in cas:
            permis = set(dir(classe))
            for objet in objets:
                inconnus = {a for a in vars(objet) if not a.startswith("_")} - permis
                self.assertFalse(inconnus, f"{nom} : {sorted(inconnus)} n'existe pas sur {classe.__name__}")


class Utilitaires(unittest.TestCase):
    def test_prenom(self):
        self.assertEqual(fetch.prenom("MELIKSETYAN Narek"), "Narek")
        self.assertEqual(fetch.prenom("Annie MELIKSETYAN"), "Annie")
        self.assertEqual(fetch.prenom("DUPONT Jean-Marie"), "Jean-Marie")
        self.assertEqual(fetch.prenom("DUPONT JEAN"), "JEAN")

    def test_slug(self):
        self.assertEqual(fetch.slug("Éléonore"), "eleonore")
        self.assertEqual(fetch.slug("Jean-Marie"), "jean-marie")

    def test_note_sur_20(self):
        self.assertEqual(fetch.note_sur_20("8", "10"), 16)
        self.assertEqual(fetch.note_sur_20("7,5", "20"), 7.5)
        self.assertIsNone(fetch.note_sur_20("Absent", "20"))

    def test_prochain_jour_de_classe(self):
        vendredi = dt.date(2026, 9, 18)
        self.assertEqual(fetch.prochain_jour_de_classe(vendredi), dt.date(2026, 9, 21))
        self.assertEqual(fetch.prochain_jour_de_classe(dt.date(2026, 9, 16)), dt.date(2026, 9, 17))


class Classement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donnees = collecte()
        cls.par_id = {a["id"]: a for a in cls.donnees["actualites"]}

    def test_enfants(self):
        ids = [e["id"] for e in self.donnees["enfants"]]
        self.assertEqual(ids, ["narek", "annie"])
        self.assertEqual(self.donnees["enfants"][0]["classe"], "5F")
        self.assertEqual(self.donnees["enfants"][0]["moyenne_generale"], "12,4")
        self.assertEqual(self.donnees["etablissement"], "Collège de démonstration")
        self.assertEqual(self.donnees["erreurs"], [])

    def test_devoir_pour_demain_scolaire(self):
        a = self.par_id["devoir:d1"]
        self.assertEqual(a["niveau"], "scolaire")
        self.assertEqual(a["horizon"], "avenir")
        self.assertEqual(a["date"], "2026-09-17")

    def test_niveaux_connus(self):
        niveaux = {a["niveau"] for a in self.donnees["actualites"]}
        self.assertTrue(niveaux <= {"important", "scolaire", "info"}, niveaux)
        self.assertIn("scolaire", self.donnees["regles"])

    def test_devoir_fait_ou_lointain_info(self):
        self.assertEqual(self.par_id["devoir:d3"]["niveau"], "info")
        self.assertTrue(self.par_id["devoir:d3"]["fait"])
        self.assertEqual(self.par_id["devoir:d4"]["niveau"], "info")

    def test_controle_dans_devoir(self):
        a = self.par_id["devoir:d2"]
        self.assertEqual((a["type"], a["niveau"]), ("controle", "scolaire"))
        self.assertEqual(a["pieces_jointes"], 1)

    def test_cours(self):
        self.assertEqual(self.par_id["cours:c1"]["raison"], "Cours annulé")
        self.assertEqual(self.par_id["cours:c4"]["raison"], "Prof. absent")
        self.assertEqual(self.par_id["controle:c2"]["type"], "controle")
        self.assertNotIn("cours:c3", self.par_id)

    def test_notes(self):
        self.assertEqual(self.par_id["note:n1"]["niveau"], "scolaire")
        self.assertEqual(self.par_id["note:n2"]["niveau"], "info")
        self.assertEqual(self.par_id["note:n3"]["titre"], "Technologie — 8/10 (16/20)")
        self.assertEqual(self.par_id["note:n5"]["raison"], "Note non chiffrée")

    def test_vie_scolaire(self):
        self.assertEqual(self.par_id["absence:a1"]["niveau"], "important")
        self.assertEqual(self.par_id["retard:r1"]["niveau"], "info")
        self.assertEqual(self.par_id["retard:r2"]["niveau"], "important")
        p = self.par_id["punition:p1"]
        self.assertEqual(p["niveau"], "important")
        self.assertIn("prévue", p["detail"])

    def test_infos_et_sondages(self):
        self.assertEqual(self.par_id["info:i1"]["niveau"], "important")
        self.assertEqual(self.par_id["info:i2"]["niveau"], "info")
        self.assertEqual(self.par_id["info:i3"]["type"], "sondage")
        self.assertEqual(self.par_id["info:i3"]["niveau"], "important")

    def test_partage_entre_enfants(self):
        self.assertEqual(self.par_id["info:i2"]["enfants"], ["narek", "annie"])
        self.assertEqual(self.par_id[id_message("m1")]["enfants"], ["narek", "annie"])
        self.assertEqual(self.par_id[id_message("m1")]["niveau"], "important")
        self.assertEqual(self.par_id[id_message("m2")]["niveau"], "info")

    def test_meme_message_sous_deux_identifiants(self):
        """Le collège écrit aux deux enfants : une seule nouvelle, un seul clic."""
        client = FauxClient(MAINTENANT)
        client._donnees["E2"]["discussions"][0]._participants_message_id = "m1-bis"
        donnees = fetch.Collecte(client, MAINTENANT).tout()
        messages = [a for a in donnees["actualites"] if a["type"] == "message"]
        fusionne = [a for a in messages if a["id"] == id_message("m1")][0]
        self.assertEqual(len(messages), 3)
        self.assertEqual(fusionne["enfants"], ["narek", "annie"])
        self.assertEqual(fusionne["ids_pronote"], [id_message("m1"), id_message("m1-bis")])

    def test_devoirs_jamais_fusionnes(self):
        """Deux devoirs de même intitulé restent deux devoirs."""
        for a in collecte()["actualites"]:
            self.assertEqual(len(a["ids_pronote"]), 1, a["id"])

    def test_message_lu_mais_a_traiter(self):
        """Une discussion lue qui parle d'autorisation reste importante."""
        self.assertEqual(self.par_id[id_message("m3")]["niveau"], "important")
        self.assertEqual(self.par_id[id_message("m3")]["raison"], "Mention « sortie »")

    def test_ordre(self):
        horizons = [a["horizon"] for a in self.donnees["actualites"]]
        self.assertEqual(horizons, sorted(horizons, key=lambda h: h != "avenir"))
        recents = [a["date"] for a in self.donnees["actualites"] if a["horizon"] == "recent"]
        self.assertEqual(recents, sorted(recents, reverse=True))


class Sortie(unittest.TestCase):
    def test_chiffrement_aller_retour(self):
        donnees = collecte()
        env = fetch.enveloppe(donnees, "secret")
        self.assertTrue(env["chiffre"])
        self.assertNotIn("Narek", json.dumps(env))
        self.assertEqual(fetch.dechiffrer(env, "secret"), donnees)
        with self.assertRaises(ValueError):
            fetch.dechiffrer(env, "faux")

    def test_en_clair(self):
        donnees = collecte()
        env = fetch.enveloppe(donnees, None)
        self.assertFalse(env["chiffre"])
        self.assertEqual(env["donnees"], donnees)

    def test_ecrire_inchange(self):
        donnees = collecte()
        with tempfile.TemporaryDirectory() as d:
            chemin = pathlib.Path(d) / "a.json"
            self.assertTrue(fetch.ecrire(donnees, chemin, "s"))
            premier = chemin.read_text()
            plus_tard = {**donnees, "mis_a_jour_le": "2030-01-01T00:00+01:00"}
            self.assertFalse(fetch.ecrire(plus_tard, chemin, "s"))
            self.assertEqual(chemin.read_text(), premier)
            plus_tard["actualites"] = plus_tard["actualites"][1:]
            self.assertTrue(fetch.ecrire(plus_tard, chemin, "s"))


if __name__ == "__main__":
    unittest.main()
