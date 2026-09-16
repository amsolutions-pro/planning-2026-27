"""Épreuve en direct du marquage « lu », contre le vrai PRONOTE.

Lancée par le workflow `diagnostic.yml`, elle répond à une seule question : quelle
requête fait vraiment descendre le compte des non-lus d'un compte parent ?

Deux garde-fous, parce qu'elle écrit sur un vrai compte :
  * réversible — tout ce qu'elle marque lu est remis non lu, y compris en cas
    d'erreur (`finally`) ;
  * muette — elle n'imprime que des nombres, des codes et des empreintes. Le
    journal d'une action GitHub est public.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402


def comptes(client) -> dict:
    """Non-lus par enfant, relus depuis le serveur."""
    etat = {}
    for info in client.children:
        client.set_child(info.name)
        etat[fetch.prenom(info.name)] = (
            len(list(client.discussions(only_unread=True))),
            len(list(client.information_and_surveys(only_unread=True))),
        )
    return etat


def ligne(etat: dict) -> str:
    return " · ".join(f"{nom} {d} msg / {i} info" for nom, (d, i) in etat.items())


def saisie(client, ident: str, public: str, genre: int, lue: bool) -> str:
    """Poste un marquage d'information avec un destinataire donné."""
    try:
        client.post("SaisieActualites", 8, {
            "listeActualites": [{
                "N": ident,
                "validationDirecte": True,
                "genrePublic": genre,
                "public": {"N": public, "G": genre},
                "lue": lue,
            }],
            "saisieActualite": False,
        })
        return "posté"
    except Exception as e:
        return f"refusé ({type(e).__name__} {fetch.court(str(e), 90)})"


def essai_informations(client, enfant) -> None:
    """Marque une information lue de plusieurs façons, jusqu'à ce que ça compte."""
    client.set_child(enfant.name)
    non_lues = list(client.information_and_surveys(only_unread=True))
    if not non_lues:
        print(f"  {fetch.prenom(enfant.name)} : aucune information non lue, rien à éprouver")
        return
    cible = non_lues[0]
    avant = len(non_lues)
    print(f"  {fetch.prenom(enfant.name)} : {avant} information(s) non lue(s), cible {fetch.hachage(cible.id)}")

    variantes = [
        ("enfant  G=4", enfant.id, 4),
        ("parent  G=4", client.info.id, 4),
        ("enfant  G=3", enfant.id, 3),
        ("parent  G=3", client.info.id, 3),
    ]
    for nom, public, genre in variantes:
        etat = saisie(client, cible.id, public, genre, True)
        reste = len(list(client.information_and_surveys(only_unread=True)))
        marche = reste < avant
        print(f"    {nom} → {etat} · non lues : {avant} → {reste} {'✔ PRIS' if marche else '✗ sans effet'}")
        if marche:
            remis = saisie(client, cible.id, public, genre, False)
            retour = len(list(client.information_and_surveys(only_unread=True)))
            print(f"    remise en non lue → {remis} · non lues : {reste} → {retour}"
                  + ("" if retour == avant else "  ⚠ ÉTAT NON RESTITUÉ"))
            return
    print("    aucune variante n'a fait descendre le compte")

    # pronotepy en dernier recours, pour comparer.
    try:
        cible.mark_as_read(True)
        reste = len(list(client.information_and_surveys(only_unread=True)))
        print(f"    pronotepy    → non lues : {avant} → {reste} "
              + ("✔ PRIS" if reste < avant else "✗ sans effet"))
        if reste < avant:
            cible.mark_as_read(False)
            print(f"    remise en non lue → {len(list(client.information_and_surveys(only_unread=True)))}")
    except Exception as e:
        print(f"    pronotepy    → {type(e).__name__} : {fetch.court(str(e), 90)}")


def essai_discussions(client, enfant) -> None:
    client.set_child(enfant.name)
    non_lues = list(client.discussions(only_unread=True))
    if not non_lues:
        print(f"  {fetch.prenom(enfant.name)} : aucune discussion non lue, rien à éprouver")
        return
    cible = non_lues[0]
    avant = len(non_lues)
    print(f"  {fetch.prenom(enfant.name)} : {avant} discussion(s) non lue(s), cible {fetch.hachage(str(cible.subject))}")
    try:
        cible.mark_as(True)
        reste = len(list(client.discussions(only_unread=True)))
        print(f"    mark_as(True)  → non lues : {avant} → {reste} "
              + ("✔ PRIS" if reste < avant else "✗ sans effet"))
    finally:
        try:
            cible.mark_as(False)
            print(f"    mark_as(False) → non lues : {len(list(client.discussions(only_unread=True)))} (restitué)")
        except Exception as e:
            print(f"    ⚠ restitution impossible : {type(e).__name__}")


def main() -> int:
    client, mode = fetch.connexion()
    print(f"Connexion : {mode} · {len(client.children)} enfant(s)")
    print(f"Onglets autorisés : {sorted(client.communication.authorized_onglets)}")
    print(f"Ressource de connexion : {fetch.hachage(client.info.id)} "
          f"· enfants : {[fetch.hachage(c.id) for c in client.children]}")
    print(f"État initial : {ligne(comptes(client))}")

    print("Informations & sondages :")
    for enfant in client.children:
        essai_informations(client, enfant)
    print("Messagerie :")
    for enfant in client.children:
        essai_discussions(client, enfant)

    print(f"État final : {ligne(comptes(client))}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
