"""Épreuve en direct du marquage « lu », contre le vrai PRONOTE.

Lancée par le workflow `diagnostic.yml`. Réversible — ce qu'elle marque lu, elle
le remet non lu — et muette : elle n'imprime que des formes, des nombres et des
empreintes, le journal d'une action GitHub étant public.

Ce que les tours précédents ont établi :
  1. aucune variante de `SaisieActualites` n'a d'effet, pas même celle de
     pronotepy : PRONOTE accepte la requête et ne fait rien ;
  3. la liste brute dit pourquoi — une information porte `genrePublic: 3` et un
     `public` bien à elle, là où pronotepy envoie `genrePublic: 4` et la
     ressource de connexion.

Ce tour-ci renvoie à PRONOTE exactement ce qu'il annonce.
"""

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402


def forme(valeur, profondeur=4, cle=None):
    """La forme d'un objet JSON, sans son contenu."""
    if isinstance(valeur, dict):
        if profondeur <= 0:
            return f"{{…{len(valeur)} clés}}"
        return {k: forme(v, profondeur - 1, k) for k, v in valeur.items()}
    if isinstance(valeur, list):
        if profondeur <= 0 or not valeur:
            return f"[…{len(valeur)}]"
        return [forme(valeur[0], profondeur - 1, cle), f"…{len(valeur)} au total"]
    if isinstance(valeur, (bool, int)) or valeur is None:
        return valeur
    texte = str(valeur)
    if cle in ("N", "G", "_T") or (len(texte) <= 24 and "#" in texte):
        return texte
    return f"<{len(texte)} car. {fetch.hachage(texte)}>"


class Serveur:
    """Le client, et de quoi repartir quand PRONOTE fait expirer la page."""

    def __init__(self):
        self.client, self.mode = fetch.connexion()
        self.enfant = None

    def choisir(self, enfant) -> None:
        self.enfant = enfant
        self.client.set_child(enfant.name)

    def poste(self, fonction, onglet, data):
        try:
            return self.client.post(fonction, onglet, data)
        except Exception as e:
            if "expir" not in str(e).lower():
                raise
            self.client, _ = fetch.connexion()
            if self.enfant is not None:
                self.client.set_child(self.enfant.name)
            return self.client.post(fonction, onglet, data)

    def actualites(self) -> list:
        """La liste brute, celle que PRONOTE envoie vraiment."""
        brut = self.poste("PageActualites", 8, {"modesAffActus": {"_T": 26, "V": "[0..3]"}})
        return [a for liste in brut["dataSec"]["data"]["listeModesAff"]
                for a in liste["listeActualites"]["V"]]

    def non_lues(self) -> list:
        return [a for a in self.actualites() if not a.get("lue")]

    def descripteur(self, actu: dict) -> dict:
        """Le destinataire tel que PRONOTE l'annonce sur l'information même."""
        public = (actu.get("public") or {}).get("V") or {}
        return {"genrePublic": actu.get("genrePublic"),
                "public": {"N": public.get("N"), "G": public.get("G")}}

    def ouvrir(self, actu: dict):
        """Ce que fait le clic dans le navigateur : demander le détail."""
        return self.poste("PageActualites", 8, {
            "actualite": {"N": actu["N"], **self.descripteur(actu)},
            "genreRequeteActualite": 1,
            "modeAffActu": 0,
        })

    def saisir(self, corps: dict, saisie=False):
        return self.poste("SaisieActualites", 8,
                          {"listeActualites": [corps], "saisieActualite": saisie})


def tentatives(s: "Serveur", actu: dict):
    """Chaque façon plausible de dire « lue », avec ce que PRONOTE annonce."""
    d = s.descripteur(actu)
    entier = {**{k: v for k, v in actu.items() if k not in ("lue",)}, "lue": True}
    return [
        ("ouvrir le détail", lambda: s.ouvrir(actu)),
        ("saisie N + public annoncé", lambda: s.saisir({"N": actu["N"], **d, "lue": True})),
        ("saisie N seul", lambda: s.saisir({"N": actu["N"], "lue": True})),
        ("saisie entrée entière", lambda: s.saisir(entier)),
        ("saisie saisieActualite=True", lambda: s.saisir({"N": actu["N"], **d, "lue": True}, True)),
    ]


def compte_frais(enfant) -> int:
    """Recompte dans une session neuve : la session qui écrit peut être aveugle."""
    client, _ = fetch.connexion()
    client.set_child(enfant.name)
    brut = client.post("PageActualites", 8, {"modesAffActus": {"_T": 26, "V": "[0..3]"}})
    entrees = [a for liste in brut["dataSec"]["data"]["listeModesAff"]
               for a in liste["listeActualites"]["V"]]
    return len([a for a in entrees if not a.get("lue")])


def refuse(reponse) -> bool:
    """PRONOTE dit « saisie refusée » sans jamais lever d'erreur HTTP.

    C'est ce rapport, que pronotepy ne regarde pas, qui a fait croire pendant
    huit tours que le marquage passait. Il sert maintenant d'oracle : une
    tentative qui ne le déclenche pas est la bonne.
    """
    return bool(((reponse or {}).get("dataSec") or {}).get("RapportSaisie", {}).get("_erreurSaisie_"))


def epreuve(s: "Serveur", enfant) -> bool:
    """Tour 9 : trouver la saisie que PRONOTE n'écarte pas.

    Acquis du tour 8 : la messagerie s'écrit (0 → 1 → 0), et l'information est
    refusée — `_erreurSaisie_`. Reste à trouver le destinataire qu'il attend.
    L'information est adressée à un groupe (genrePublic 2, public G=5) : le
    lecteur, lui, doit être nommé autrement.
    """
    s.choisir(enfant)
    nom = fetch.prenom(enfant.name)
    entrees = s.actualites()
    non_lues = [a for a in entrees if not a.get("lue")]
    if not non_lues:
        print(f"  {nom} : aucune information non lue")
        return True
    cible = next((a for a in non_lues if not a.get("estSondage")), non_lues[0])
    avant = len(non_lues)
    annonce = s.descripteur(cible)
    parent, enf = s.client.info.id, enfant.id
    print(f"  {nom} : {avant} non lue(s) · annoncé genrePublic {annonce['genrePublic']} G={annonce['public']['G']}")

    essais = [
        ("genre 2 · parent G=5", {"genrePublic": 2, "public": {"N": parent, "G": 5}}),
        ("genre 5 · parent G=5", {"genrePublic": 5, "public": {"N": parent, "G": 5}}),
        ("genre 2 · enfant G=4", {"genrePublic": 2, "public": {"N": enf, "G": 4}}),
        ("genre 2 · parent G=4", {"genrePublic": 2, "public": {"N": parent, "G": 4}}),
        ("genre annoncé (témoin)", annonce),
        ("sans public", {}),
    ]
    for nom_essai, descripteur in essais:
        corps = {"N": cible["N"], "validationDirecte": True, "lue": True, **descripteur}
        try:
            reponse = s.saisir(corps)
            ecarte = refuse(reponse)
            etat = "ÉCARTÉ" if ecarte else "accepté"
        except Exception as e:
            ecarte, etat = True, f"{type(e).__name__}"
        print(f"    {nom_essai:<26} → {etat}")
        if not ecarte:
            frais = compte_frais(enfant)
            print(f"      session neuve : {avant} → {frais} "
                  + ("✔ PRIS" if frais < avant else "✗ accepté mais sans effet"))
            if frais < avant:
                s.saisir({"N": cible["N"], "validationDirecte": True, "lue": False, **descripteur})
                print(f"      remise en non lue → {compte_frais(enfant)} (départ {avant})")
                return True
    return False


def main() -> int:
    s = Serveur()
    print(f"Connexion : {s.mode} · {len(s.client.children)} enfant(s)")
    s.choisir(s.client.children[0])

    print("Épreuve, enfant par enfant :")
    tous = all(epreuve(s, e) for e in s.client.children)
    print("RÉSULTAT : " + ("le marquage prend ✔" if tous else "le marquage ne prend toujours pas ✗"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
