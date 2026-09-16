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

    def marquer(self, actu: dict, lue: bool, genre=None, public=None) -> str:
        """Renvoie à PRONOTE le destinataire qu'il a lui-même annoncé."""
        genre = actu.get("genrePublic") if genre is None else genre
        public = (actu.get("public") or {}).get("V") if public is None else public
        try:
            self.poste("SaisieActualites", 8, {
                "listeActualites": [{
                    "N": actu["N"],
                    "validationDirecte": True,
                    "genrePublic": genre,
                    "public": {"N": public["N"], "G": public["G"]},
                    "lue": lue,
                }],
                "saisieActualite": False,
            })
            return "posté"
        except Exception as e:
            return f"refusé ({type(e).__name__} {fetch.court(str(e), 70)})"


def epreuve(s: Serveur, enfant) -> bool:
    s.choisir(enfant)
    non_lues = s.non_lues()
    nom = fetch.prenom(enfant.name)
    if not non_lues:
        print(f"  {nom} : aucune information non lue")
        return True
    cible = non_lues[0]
    avant = len(non_lues)
    public = (cible.get("public") or {}).get("V") or {}
    print(f"  {nom} : {avant} non lue(s) · cible {fetch.hachage(cible['N'])}"
          f" · genrePublic {cible.get('genrePublic')}"
          f" · public {fetch.hachage(public.get('N'))} G={public.get('G')}")

    etat = s.marquer(cible, True)
    reste = len(s.non_lues())
    pris = reste < avant
    print(f"    tel que PRONOTE l'annonce → {etat} · {avant} → {reste} "
          + ("✔ PRIS" if pris else "✗ sans effet"))
    if not pris:
        return False

    remis = s.marquer(cible, False)
    retour = len(s.non_lues())
    print(f"    remise en non lue → {remis} · {reste} → {retour}"
          + ("  ✔ restitué" if retour == avant else "  ⚠ ÉTAT NON RESTITUÉ"))
    return True


def main() -> int:
    s = Serveur()
    print(f"Connexion : {s.mode} · {len(s.client.children)} enfant(s)")
    s.choisir(s.client.children[0])
    exemple = next((a for a in s.actualites() if not a.get("lue")), None)
    if exemple is not None:
        print("Forme brute d'une information non lue :")
        print(json.dumps(forme(exemple, 3), ensure_ascii=False)[:1200])

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
