"""Tests de fetch.py sur le faux client : python3 -m unittest discover pronote"""

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import fetch  # noqa: E402
from exemple import FauxClient  # noqa: E402

MAINTENANT = dt.datetime(2026, 9, 16, 10, 0, tzinfo=fetch.PARIS)  # un mercredi


def collecte():
    return fetch.Collecte(FauxClient(MAINTENANT), MAINTENANT).tout()


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

    def test_devoir_pour_demain_important(self):
        a = self.par_id["devoir:d1"]
        self.assertEqual(a["niveau"], "important")
        self.assertEqual(a["horizon"], "avenir")
        self.assertEqual(a["date"], "2026-09-17")

    def test_devoir_fait_ou_lointain_info(self):
        self.assertEqual(self.par_id["devoir:d3"]["niveau"], "info")
        self.assertTrue(self.par_id["devoir:d3"]["fait"])
        self.assertEqual(self.par_id["devoir:d4"]["niveau"], "info")

    def test_controle_dans_devoir(self):
        a = self.par_id["devoir:d2"]
        self.assertEqual((a["type"], a["niveau"]), ("controle", "important"))
        self.assertEqual(a["pieces_jointes"], 1)

    def test_cours(self):
        self.assertEqual(self.par_id["cours:c1"]["raison"], "Cours annulé")
        self.assertEqual(self.par_id["cours:c4"]["raison"], "Prof. absent")
        self.assertEqual(self.par_id["controle:c2"]["type"], "controle")
        self.assertNotIn("cours:c3", self.par_id)

    def test_notes(self):
        self.assertEqual(self.par_id["note:n1"]["niveau"], "important")
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
        self.assertEqual(self.par_id["message:m1"]["enfants"], ["narek", "annie"])
        self.assertEqual(self.par_id["message:m1"]["niveau"], "important")
        self.assertEqual(self.par_id["message:m2"]["niveau"], "info")

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
