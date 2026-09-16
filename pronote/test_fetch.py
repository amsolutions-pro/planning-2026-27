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


def collecte_indexee(client=None, maintenant=MAINTENANT):
    """Les données, et par quel numéro PRONOTE on a atteint chaque nouvelle.

    Les nouvelles n'exposent plus ces numéros : ils ne valent que le temps d'une
    session. Les tests désignent quand même « devoir:d1 », c'est plus lisible.
    """
    c = fetch.Collecte(client or FauxClient(maintenant), maintenant)
    return c.tout(), dict(c.connus)


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
        cls.donnees, cls.par_id = collecte_indexee()

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
        donnees, par_id = collecte_indexee(client)
        messages = [a for a in donnees["actualites"] if a["type"] == "message"]
        self.assertEqual(len(messages), 3)
        self.assertIs(par_id[id_message("m1")], par_id[id_message("m1-bis")])
        self.assertEqual(par_id[id_message("m1")]["enfants"], ["narek", "annie"])

    def test_identite_survit_a_une_renumerotation(self):
        """PRONOTE renumérote tout à chaque session : les identités doivent tenir."""
        def renumerote(client):
            for cle, enfant in client._donnees.items():
                for liste in ("devoirs", "cours", "infos"):
                    for i, o in enumerate(enfant.get(liste, [])):
                        if hasattr(o, "id"):
                            # Numéros neufs, mais toujours distincts d'un enfant à l'autre.
                            o.id = f"session2-{cle}-{liste}-{i}"
                for d in enfant.get("discussions", []):
                    d._participants_message_id = "session2-" + str(d._participants_message_id)
                for periode in enfant["periodes"]:
                    for liste in (periode.grades, periode.absences, periode.delays, periode.punishments):
                        for o in liste:
                            o.id = "session2-" + o.id
            return client

        avant = {a["id"] for a in collecte()["actualites"]}
        apres = {a["id"] for a in fetch.Collecte(renumerote(FauxClient(MAINTENANT)), MAINTENANT).tout()["actualites"]}
        self.assertEqual(avant, apres)

    def test_identite_independante_de_l_enfant(self):
        """Le « Vu » du navigateur tient à l'identifiant de la nouvelle.

        Le message est le même, mais chaque enfant le porte sous son propre
        numéro. Tant que l'identité venait du premier enfant lu, la disparition
        de sa copie — liste bornée, réordonnée — rebaptisait la nouvelle, qui
        revenait « non vue » après une actualisation.
        """
        def donnees(avec_narek):
            client = FauxClient(MAINTENANT)
            client._donnees["E2"]["discussions"][0]._participants_message_id = "m1-bis"
            if not avec_narek:
                client._donnees["E1"]["discussions"] = []
            return collecte_indexee(client)

        a_deux = donnees(True)[1][id_message("m1-bis")]
        seul = donnees(False)[1][id_message("m1-bis")]
        self.assertEqual(a_deux["enfants"], ["narek", "annie"])
        self.assertEqual(seul["enfants"], ["annie"])
        self.assertEqual(seul["id"], a_deux["id"])
        self.assertNotIn(":", seul["id"])  # jamais confondu avec un identifiant PRONOTE

    def test_devoirs_jamais_fusionnes(self):
        """Le travail scolaire ne se regroupe jamais entre enfants."""
        for a in self.donnees["actualites"]:
            if a["type"] not in fetch.ACTU_COMMUNES:
                self.assertEqual(len(a["enfants"]), 1, a["id"])

    def test_communication_lue_nest_plus_importante(self):
        """L'important, c'est ce qui attend encore : une lue en sort.

        Une discussion lue parlant d'autorisation y restait indéfiniment. Il
        fallait la masquer d'un « Vu » que rien ne reprenait jamais, et le
        « Remettre les vues » gonflait sans fin.
        """
        m3 = self.par_id[id_message("m3")]
        self.assertTrue(m3["lu"])
        self.assertEqual((m3["niveau"], m3["raison"]), ("info", "Discussion lue"))

    def test_mention_dit_pourquoi_un_non_lu_est_important(self):
        m1 = self.par_id[id_message("m1")]
        self.assertEqual((m1["niveau"], m1["raison"]), ("important", "Mention « sortie »"))

    def test_ordre(self):
        horizons = [a["horizon"] for a in self.donnees["actualites"]]
        self.assertEqual(horizons, sorted(horizons, key=lambda h: h != "avenir"))
        recents = [a["date"] for a in self.donnees["actualites"] if a["horizon"] == "recent"]
        self.assertEqual(recents, sorted(recents, reverse=True))


class Marquage(unittest.TestCase):
    """Le clic « Vu » doit vraiment atteindre PRONOTE, une session plus tard."""

    def test_identite_retrouvee_dans_une_session_neuve(self):
        publie = collecte()
        cible = [a for a in publie["actualites"]
                 if a["type"] == "message" and a["niveau"] == "important"][0]
        # Nouvelle session : PRONOTE renumérote, la page ne sait que l'identité.
        client = FauxClient(MAINTENANT)
        for enfant in client._donnees.values():
            for d in enfant.get("discussions", []):
                d._participants_message_id = "session2-" + str(d._participants_message_id)
        faits, introuvables = fetch.marquer_lu(client, [cible["id"]])
        self.assertEqual((faits, introuvables), ([cible["id"]], []))
        lues = [d for e in client._donnees.values() for d in e.get("discussions", []) if not d.unread]
        self.assertTrue(lues)

    def test_les_deux_copies_sont_marquees(self):
        """Le collège écrit aux deux : un exemplaire de chaque côté à marquer.

        S'arrêter à la première copie laissait l'autre non lue, et le compte des
        non-lus de PRONOTE ne descendait pas.
        """
        publie = collecte()
        cible = [a for a in publie["actualites"]
                 if a["type"] == "message" and a["enfants"] == ["narek", "annie"]][0]
        client = FauxClient(MAINTENANT)
        # Chaque enfant porte sa propre copie, sous son propre numéro.
        client._donnees["E2"]["discussions"][0]._participants_message_id = "m1-bis"
        faits, introuvables = fetch.marquer_lu(client, [cible["id"]])
        self.assertEqual((faits, introuvables), ([cible["id"]], []))
        copies = [d for e in client._donnees.values() for d in e.get("discussions", [])
                  if str(d._participants_message_id).endswith(("m1", "m1-bis"))]
        self.assertEqual(len(copies), 2)
        self.assertTrue(all(d.unread == 0 for d in copies), [d.unread for d in copies])

    def test_information_marquee_au_nom_de_l_enfant(self):
        """pronotepy adresse le marquage au parent ; PRONOTE n'en fait rien."""
        publie = collecte()
        sondage = [a for a in publie["actualites"] if a["type"] == "sondage"][0]
        client = FauxClient(MAINTENANT)
        faits, introuvables = fetch.marquer_lu(client, [sondage["id"]])
        self.assertEqual((faits, introuvables), ([sondage["id"]], []))
        # L'information est vraiment lue côté serveur, pas seulement dans l'objet.
        restant = [i for e in client._donnees.values() for i in e["infos"] if not i.read]
        self.assertFalse([i.id for i in restant if i.id == "i3"], "le sondage est resté non lu")
        publics = [a["public"]["N"] for p in client._postes if p["fonction"] == "SaisieActualites"
                   for a in p["data"]["listeActualites"]]
        self.assertIn("E2", publics, "le marquage doit être adressé à l'enfant")

    def test_seules_les_identites_passent(self):
        """Un numéro PRONOTE, ou n'importe quoi d'autre, est écarté."""
        bon = "message~0123456789abcdef"
        self.assertEqual(fetch.ids_a_marquer(f"{bon}, message:d1, devoir~0123456789abcdef, "
                                             "message~PAS_HEXA, ../../etc"), [bon])


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

    def test_contenu_stable_entre_deux_passages(self):
        """Sans nouveauté, deux passages doivent donner le même fichier."""
        premier = collecte()
        memoire = {a["id"]: a["signale_le"] for a in premier["actualites"]}
        plus_tard = MAINTENANT + dt.timedelta(minutes=37)
        second = fetch.Collecte(FauxClient(MAINTENANT), plus_tard, memoire=memoire).tout()
        self.assertEqual(fetch.empreinte(premier), fetch.empreinte(second))

    def test_fichier_stable_malgre_une_renumerotation(self):
        """Le cas réel : PRONOTE renumérote, et le fichier ne doit pas bouger."""
        premier = collecte()
        memoire = {a["id"]: a["signale_le"] for a in premier["actualites"]}
        client = FauxClient(MAINTENANT)
        for cle, enfant in client._donnees.items():
            for liste in ("devoirs", "cours", "infos"):
                for i, o in enumerate(enfant.get(liste, [])):
                    if hasattr(o, "id"):
                        o.id = f"session2-{cle}-{liste}-{i}"
        plus_tard = MAINTENANT + dt.timedelta(minutes=37)
        second = fetch.Collecte(client, plus_tard, memoire=memoire).tout()
        self.assertEqual(fetch.empreinte(premier), fetch.empreinte(second))

    def test_sans_memoire_le_contenu_derive(self):
        """Le défaut que la mémoire corrige : l'heure du passage entrait dans le contenu."""
        premier = collecte()
        plus_tard = MAINTENANT + dt.timedelta(minutes=37)
        second = fetch.Collecte(FauxClient(MAINTENANT), plus_tard).tout()
        self.assertNotEqual(fetch.empreinte(premier), fetch.empreinte(second))

    def test_memoire_relue_du_fichier(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = pathlib.Path(d) / "a.json"
            donnees = collecte()
            fetch.ecrire(donnees, chemin, "secret")
            memoire = fetch.memoire_precedente(chemin, "secret")
            self.assertEqual(memoire[donnees["actualites"][0]["id"]],
                             donnees["actualites"][0]["signale_le"])
            self.assertEqual(fetch.memoire_precedente(chemin, "faux"), {})
            self.assertEqual(fetch.memoire_precedente(pathlib.Path(d) / "rien.json", "secret"), {})

    def test_identites_comptees(self):
        donnees = collecte()
        ids = [a["id"] for a in donnees["actualites"]]
        self.assertIn("pas de passage précédent", fetch.identites({}, donnees))
        memoire = {i: "2026-09-16T09:00:00+02:00" for i in ids[1:]} | {"parti:1": "x"}
        self.assertEqual(fetch.identites(memoire, donnees),
                         f"  identités : {len(ids) - 1} gardée(s), 1 nouvelle(s), 1 disparue(s)")

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
