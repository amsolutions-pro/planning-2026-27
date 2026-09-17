"""Épreuve en direct du marquage « lu », contre le vrai PRONOTE.

Lancée par le workflow `diagnostic.yml`. Réversible — ce qu'elle change, elle le
remet — et muette : elle n'imprime que des nombres et des empreintes, le journal
d'une action GitHub étant public.

Neuf tours d'enquête ont établi ceci, mesuré dans des sessions neuves :
  * la messagerie s'écrit (une discussion passe de lue à non lue et revient) ;
  * le « lu » d'une information est écarté par le serveur, quel que soit le
    destinataire envoyé et jusque dans l'autre sens — `_erreurSaisie_` —, sans
    la moindre erreur HTTP. pronotepy ne regarde pas ce rapport : c'est ce
    silence qui faisait croire au robot qu'il avait marqué.

Ce dernier tour n'éprouve plus des requêtes, mais le code livré : `marquer_lu`
doit marquer le message et ranger l'information parmi les écartés.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402


def non_lus(enfant) -> tuple[int, int]:
    """Recompte dans une session neuve : la session qui écrit peut être aveugle."""
    client, _ = fetch.connexion()
    client.set_child(enfant.name)
    return (len(list(client.discussions(only_unread=True))),
            len(list(client.information_and_surveys(only_unread=True))))


def main() -> int:
    client, mode = fetch.connexion()
    enfant = client.children[0]
    client.set_child(enfant.name)
    nom = fetch.prenom(enfant.name)
    print(f"Connexion : {mode} · épreuve sur {nom}")

    discussions = list(client.discussions())
    informations = client.information_and_surveys(only_unread=True)
    if not discussions:
        print("aucune discussion : rien à éprouver")
        return 0

    # On se donne un non-lu à marquer, puisqu'il n'en reste plus.
    d = discussions[0]
    d.mark_as(False)
    depart = non_lus(enfant)
    print(f"départ (session neuve) : {depart[0]} msg / {depart[1]} info")

    demandes = [fetch.identite(fetch.contenu_discussion(d), None)]
    attendu_ecarte = []
    if informations:
        i = informations[0]
        attendu_ecarte = [fetch.identite(fetch.contenu_information(i), None)]
        demandes += attendu_ecarte

    client, _ = fetch.connexion()          # comme le robot : une session à lui
    faits, introuvables, ecartes = fetch.marquer_lu(client, demandes)
    apres = non_lus(enfant)
    print(f"marquer_lu : {len(faits)} fait(s) · {len(ecartes)} écarté(s) · {len(introuvables)} introuvable(s)")
    print(f"après (session neuve) : {apres[0]} msg / {apres[1]} info")

    msg_ok = (faits == demandes[:1]) and apres[0] == depart[0] - 1
    info_ok = (ecartes == attendu_ecarte) and apres[1] == depart[1]
    print(f"  message marqué et compté comme fait : {'✔' if msg_ok else '✗'}")
    print(f"  information écartée, et dite écartée : {'✔' if info_ok else '✗'}"
          + ("" if attendu_ecarte else "  (aucune information non lue à éprouver)"))
    print("RÉSULTAT : " + ("le code livré dit vrai ✔" if msg_ok and info_ok
                           else "à revoir ✗"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
