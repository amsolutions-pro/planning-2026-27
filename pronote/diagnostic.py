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
    """Recompte dans une session neuve.

    Les cinq tours précédents recomptaient dans la session qui venait d'écrire :
    si PRONOTE y sert une liste figée, ils étaient aveugles. Une reconnexion
    lève le doute — c'est cher, mais c'est la seule mesure qui vaille.
    """
    client, _ = fetch.connexion()
    client.set_child(enfant.name)
    brut = client.post("PageActualites", 8, {"modesAffActus": {"_T": 26, "V": "[0..3]"}})
    entrees = [a for liste in brut["dataSec"]["data"]["listeModesAff"]
               for a in liste["listeActualites"]["V"]]
    return len([a for a in entrees if not a.get("lue")])


def epreuve(s: "Serveur", enfant) -> bool:
    s.choisir(enfant)
    non_lues = s.non_lues()
    nom = fetch.prenom(enfant.name)
    if not non_lues:
        print(f"  {nom} : aucune information non lue")
        return True
    cible = next((a for a in non_lues if not a.get("estSondage")), non_lues[0])
    avant = len(non_lues)
    public = (cible.get("public") or {}).get("V") or {}
    print(f"  {nom} : {avant} non lue(s) · cible {fetch.hachage(cible['N'])}"
          f" · genrePublic {cible.get('genrePublic')} · public G={public.get('G')}")

    essais = [
        ("saisie, descripteur annoncé", lambda: s.saisir({"N": cible["N"], **s.descripteur(cible), "lue": True})),
        ("ouvrir le détail", lambda: s.ouvrir(cible)),
        ("saisie, public = enfant G=4", lambda: s.saisir(
            {"N": cible["N"], "validationDirecte": True, "genrePublic": 4,
             "public": {"N": enfant.id, "G": 4}, "lue": True})),
    ]
    for nom_essai, faire in essais:
        try:
            faire()
            etat = "posté"
        except Exception as e:
            etat = f"refusé ({type(e).__name__} {fetch.court(str(e), 60)})"
        meme = len(s.non_lues())
        frais = compte_frais(enfant)
        pris = frais < avant
        print(f"    {nom_essai:<28} → {etat:<24} même session {meme} · session neuve {frais} "
              + ("✔ PRIS" if pris else "✗"))
        if pris:
            s.saisir({"N": cible["N"], **s.descripteur(cible), "lue": False})
            print(f"    remise en non lue → session neuve {compte_frais(enfant)} (départ {avant})")
            return True
    return False


def main() -> int:
    s = Serveur()
    print(f"Connexion : {s.mode} · {len(s.client.children)} enfant(s)")
    s.choisir(s.client.children[0])
    exemple = next((a for a in s.actualites() if not a.get("lue") and not a.get("estSondage")), None)
    if exemple is not None:
        print("Forme brute d'une information ordinaire non lue :")
        print(json.dumps(forme(exemple, 3), ensure_ascii=False)[:1400])

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
