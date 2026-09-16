"""Épreuve en direct du marquage « lu », contre le vrai PRONOTE.

Lancée par le workflow `diagnostic.yml`, elle répond à une seule question : quelle
requête fait vraiment descendre le compte des non-lus d'un compte parent ?

Deux garde-fous, parce qu'elle écrit sur un vrai compte :
  * réversible — ce qu'elle marque lu, elle le remet non lu ;
  * muette — elle n'imprime que des formes, des nombres et des empreintes. Le
    journal d'une action GitHub est public : aucun texte de message n'en sort.

Tour 1 : aucune variante de `SaisieActualites` n'a eu d'effet, pas même celle de
pronotepy. On regarde donc ce que PRONOTE dit lui-même de ses informations, et on
essaie l'ouverture (`PageActualites`), qui est ce que fait le clic dans le
navigateur.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402

PROFONDEUR = 4
# Ces clés portent des nombres ou des drapeaux, jamais de texte : on peut les
# lire telles quelles pour comprendre ce que PRONOTE attend.
CLES_LISIBLES = {"N", "G", "V", "_T", "genre", "genrePublic", "lue", "estSondage",
                 "estModele", "estModelePartage", "reponseAnonyme", "avecAccuse",
                 "estAccuseLecture", "necessiteAccuse", "public", "listePublics"}


def forme(valeur, profondeur=PROFONDEUR, cle=None):
    """La forme d'un objet JSON, sans son contenu."""
    if isinstance(valeur, dict):
        if profondeur <= 0:
            return f"{{…{len(valeur)} clés}}"
        return {k: forme(v, profondeur - 1, k) for k, v in valeur.items()}
    if isinstance(valeur, list):
        if profondeur <= 0 or not valeur:
            return f"[…{len(valeur)}]"
        return [forme(valeur[0], profondeur - 1, cle), f"…{len(valeur)} au total"] if len(valeur) > 1 \
            else [forme(valeur[0], profondeur - 1, cle)]
    if isinstance(valeur, bool) or isinstance(valeur, int):
        return valeur
    if valeur is None:
        return None
    texte = str(valeur)
    # Un identifiant court et technique est lisible ; une phrase, non.
    if cle in ("N", "G", "_T") or (len(texte) <= 24 and "#" in texte):
        return texte
    return f"<{len(texte)} car. {fetch.hachage(texte)}>"


def compte(client) -> int:
    return len(list(client.information_and_surveys(only_unread=True)))


def essai(nom, fonction, client, avant) -> bool:
    """Tente quelque chose, puis recompte. Renvoie True si le compte a bougé."""
    try:
        fonction()
        etat = "posté"
    except Exception as e:
        etat = f"refusé ({type(e).__name__} {fetch.court(str(e), 80)})"
    reste = compte(client)
    print(f"    {nom:<34} → {etat:<46} {avant} → {reste} "
          + ("✔ PRIS" if reste < avant else "✗ sans effet"))
    return reste < avant


def main() -> int:
    client, mode = fetch.connexion()
    print(f"Connexion : {mode} · {len(client.children)} enfant(s) · onglets {sorted(client.communication.authorized_onglets)}")
    enfant = client.children[0]
    client.set_child(enfant.name)
    non_lues = client.information_and_surveys(only_unread=True)
    print(f"{fetch.prenom(enfant.name)} : {len(non_lues)} information(s) non lue(s)")
    if not non_lues:
        print("rien à éprouver")
        return 0
    cible = non_lues[0]
    avant = len(non_lues)

    import json
    # pronotepy jette le JSON brut après construction (`del self._resolver`) :
    # on redemande la liste pour voir ce que PRONOTE dit lui-même de ses
    # informations — c'est là que doit se lire ce qu'il attend en retour.
    brut = client.post("PageActualites", 8, {"modesAffActus": {"_T": 26, "V": "[0..3]"}})
    entrees = [a for liste in brut["dataSec"]["data"]["listeModesAff"]
               for a in liste["listeActualites"]["V"]]
    print(f"Forme de l'enveloppe : {json.dumps(forme(brut['dataSec']['data'], 2), ensure_ascii=False)[:600]}")
    non_lue = next((a for a in entrees if not a.get("lue")), None)
    print("Forme brute d'une information non lue :")
    print(json.dumps(forme(non_lue), ensure_ascii=False, indent=1)[:3500])
    print(f"ressource de connexion : {fetch.hachage(client.info.id)} · enfant : {fetch.hachage(enfant.id)}")

    def ouvrir(public, genre):
        return lambda: client.post("PageActualites", 8, {
            "actualite": {"N": cible.id, "genrePublic": genre, "public": {"N": public, "G": genre}},
            "genreRequeteActualite": 1,
            "modeAffActu": 0,
        })

    def saisir(public, genre, lue=True):
        return lambda: client.post("SaisieActualites", 8, {
            "listeActualites": [{"N": cible.id, "validationDirecte": True, "genrePublic": genre,
                                 "public": {"N": public, "G": genre}, "lue": lue}],
            "saisieActualite": False,
        })

    def accuser(public, genre):
        return lambda: client.post("SaisieActualites", 8, {
            "listeActualites": [{"N": cible.id, "genrePublic": genre,
                                 "public": {"N": public, "G": genre}, "lue": True,
                                 "avecAccuse": True}],
            "saisieActualite": True,
        })

    print("Tentatives :")
    tentatives = [
        ("ouvrir  public=enfant G=4", ouvrir(enfant.id, 4)),
        ("ouvrir  public=parent G=4", ouvrir(client.info.id, 4)),
        ("ouvrir  public=enfant G=3", ouvrir(enfant.id, 3)),
        ("lire le contenu (pronotepy)", cible.content),
        ("saisie  saisieActualite=True", accuser(enfant.id, 4)),
        ("saisie  public=enfant G=5", saisir(enfant.id, 5)),
        ("saisie  public=parent G=5", saisir(client.info.id, 5)),
    ]
    for nom, fonction in tentatives:
        if essai(nom, fonction, client, avant):
            print(f"  ⇒ « {nom} » fait descendre le compte. Remise en l'état :")
            essai("saisie lue=False (enfant G=4)", saisir(enfant.id, 4, False), client, avant - 1)
            essai("saisie lue=False (parent G=4)", saisir(client.info.id, 4, False), client, avant - 1)
            break
    else:
        print("  aucune tentative n'a fait descendre le compte")
    print(f"état final : {compte(client)} non lue(s) (au départ {avant})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
