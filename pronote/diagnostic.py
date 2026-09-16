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


def epreuve(s: "Serveur", enfant) -> bool:
    """Tour 8 : l'aller-retour, dans l'autre sens.

    Sept tours ont échoué à faire descendre le compte des informations. Reste
    une question, et une seule : le drapeau « lu » est-il seulement inscriptible
    depuis un compte parent ? On prend donc une information DÉJÀ LUE et on tente
    de la repasser en non lue. Si même cela ne prend pas, PRONOTE ne laisse pas
    écrire ce drapeau, et il faudra le dire au lieu de le promettre.

    On éprouve du même coup la messagerie, où le marquage semble marcher : une
    discussion lue est repassée non lue, puis relue. Si le compte bouge dans les
    deux sens, le « Vu » tient sa promesse pour les messages.
    """
    s.choisir(enfant)
    nom = fetch.prenom(enfant.name)

    # -- messagerie
    toutes = list(s.client.discussions())
    if toutes:
        d = toutes[0]
        avant = compte_msg(enfant)
        try:
            d.mark_as(False)
            monte = compte_msg(enfant)
            d.mark_as(True)
            redescend = compte_msg(enfant)
            print(f"  {nom} · messagerie : non lus {avant} → {monte} (mise en non lu) "
                  f"→ {redescend} (remise en lu) "
                  + ("✔ LE MARQUAGE ÉCRIT" if monte > avant and redescend == avant else "✗"))
        except Exception as e:
            print(f"  {nom} · messagerie : {type(e).__name__} {fetch.court(str(e), 70)}")
    else:
        print(f"  {nom} · messagerie : aucune discussion")

    # -- informations
    entrees = s.actualites()
    lues = [a for a in entrees if a.get("lue")]
    avant = len([a for a in entrees if not a.get("lue")])
    if not lues:
        print(f"  {nom} · informations : aucune déjà lue, rien à éprouver dans ce sens")
        return False
    cible = lues[0]
    etat = s.saisir({"N": cible["N"], **s.descripteur(cible), "lue": False})
    monte = compte_frais(enfant)
    print(f"  {nom} · informations : non lues {avant} → {monte} (mise en NON lue) → {etat}")
    if monte > avant:
        s.saisir({"N": cible["N"], **s.descripteur(cible), "lue": True})
        print(f"    remise en lue → {compte_frais(enfant)} ✔ le drapeau s'écrit")
        return True
    print("    ✗ le drapeau « lu » d'une information ne s'écrit pas depuis ce compte")
    return False


def compte_msg(enfant) -> int:
    client, _ = fetch.connexion()
    client.set_child(enfant.name)
    return len(list(client.discussions(only_unread=True)))


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
