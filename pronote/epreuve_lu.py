"""Le « lu » posé ici arrive-t-il jusqu'à PRONOTE ? Épreuve en direct.

Elle écrit sur le vrai compte, donc : **réversible** — tout ce qu'elle marque,
elle le remet comme elle l'a trouvé — et **à la demande** seulement.

Elle n'imprime que des nombres, des noms de champs et des verdicts. Jamais un
titre, jamais un auteur, jamais un texte : le journal de l'action est public.

Deux questions, séparées :
  1. une DISCUSSION peut-elle passer en lu depuis un compte parent ?
  2. une INFORMATION le peut-elle ? On a établi que la route de pronotepy se
     fait écarter en silence ; on essaie ici plusieurs adressages, dont celui
     que PRONOTE décrit lui-même dans sa propre liste.
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402


def compte(client) -> str:
    return fetch.non_lus(client)


def rapport(reponse) -> str:
    """Le verdict de PRONOTE, en un mot — sans rien du contenu."""
    r = ((reponse or {}).get("dataSec") or {}).get("RapportSaisie")
    if r is None:
        return "aucun rapport"
    return "ÉCARTÉ" if r.get("_erreurSaisie_") else f"pris (clés {sorted(r)})"


def brut_des_informations(client) -> dict:
    """La liste crue de l'onglet 8, indexée par N — pronotepy jette le brut."""
    reponse = client.post("PageActualites", 8, {"modesAffActus": {"_T": 26, "V": "[0..3]"}})
    par_id = {}
    # La forme peut surprendre : mieux vaut une liste vide qu'une épreuve morte
    # à mi-chemin sur le vrai compte.
    try:
        listes = reponse["dataSec"]["data"]["listeModesAff"]
    except (KeyError, TypeError):
        print(f"      (liste crue illisible : clés {sorted((reponse or {}).get('dataSec', {}).get('data', {}) or {})})")
        return par_id
    for liste in listes:
        for a in ((liste.get("listeActualites") or {}).get("V") or []):
            par_id[str(a.get("N"))] = a
    return par_id


def descripteurs(entree: dict) -> list:
    """Tout ce qui, dans l'entrée crue, ressemble à un destinataire {N, G}."""
    trouves = []

    def fouille(x, chemin):
        if isinstance(x, dict):
            if "N" in x and "G" in x and isinstance(x.get("G"), int):
                trouves.append((chemin, x["G"]))
            for k, v in x.items():
                fouille(v, f"{chemin}.{k}" if chemin else k)
        elif isinstance(x, list):
            for v in x[:3]:
                fouille(v, f"{chemin}[]")

    fouille(entree, "")
    return trouves


def essai(client, nom: str, corps: dict) -> str:
    try:
        return f"    {nom} → {rapport(client.post('SaisieActualites', 8, corps))}"
    except Exception as e:
        return f"    {nom} → exception {type(e).__name__}"


def discussions(client, enfant) -> None:
    client.set_child(enfant.name)
    nom = fetch.prenom(enfant.name)
    cible = next((d for d in client.discussions() if (d.unread or 0)), None)
    if cible is None:
        print(f"  {nom} · discussion : aucune non lue, rien à éprouver")
        return
    avant = compte(client)
    pris = fetch.marquer_discussion(client, cible)
    apres = compte(client)
    print(f"  {nom} · DISCUSSION : saisie {'prise' if pris else 'ÉCARTÉE'}")
    print(f"      non-lus avant : {avant}")
    print(f"      non-lus après : {apres}")
    print(f"      VERDICT : {'le compteur a bougé' if avant != apres else 'le compteur n’a pas bougé'}")
    # On remet comme on a trouvé.
    try:
        client.post("SaisieMessage", 131, {
            "commande": "pourLu", "lu": False,
            "listePossessionsMessages": cible._possessions,
        })
        print(f"      remis non lu : {compte(client)}")
    except Exception as e:
        print(f"      ATTENTION, remise en non-lu échouée ({type(e).__name__})")


def informations(client, enfant) -> None:
    client.set_child(enfant.name)
    nom = fetch.prenom(enfant.name)
    cible = next((i for i in client.information_and_surveys() if not i.read), None)
    if cible is None:
        print(f"  {nom} · information : aucune non lue, rien à éprouver")
        return
    brut = brut_des_informations(client).get(str(cible.id), {})
    print(f"  {nom} · INFORMATION : {len(brut)} champ(s) dans l'entrée crue")
    print(f"      champs : {sorted(brut)}")
    print(f"      destinataires décrits par PRONOTE : {descripteurs(brut) or '—'}")

    enfant_res = getattr(client, "_selected_child", None)
    parent_res = getattr(client, "info", None)
    avant = compte(client)
    print(f"      non-lus avant : {avant}")

    # PRONOTE a donné une entrée entière ; on la lui rend, au lieu d'en
    # fabriquer une minimale de cinq champs. C'est l'erreur des tours
    # précédents : le client web du collège, lui, sait marquer — le droit
    # existe, c'était la forme de la requête qui n'allait pas.
    allege = {k: v for k, v in brut.items() if k != "informationListeContenu"}
    print(f"      genrePublic de l'entrée : {brut.get('genrePublic')!r}")
    print(f"      forme de « public » : {type(brut.get('public')).__name__}"
          f" · clés {sorted(brut['public']) if isinstance(brut.get('public'), dict) else '—'}")
    print(f"      nature : G={((brut.get('nature') or {}).get('V') or {}).get('G')!r}"
          f" · estSondage={brut.get('estSondage')!r} · estAuteur={brut.get('estAuteur')!r}")

    enfant_res = getattr(client, "_selected_child", None)
    avant = compte(client)
    print(f"      non-lus avant : {avant}")

    routes = []
    if brut:
        routes.append(("l'entrée crue entière, lue=True",
                       {"listeActualites": [dict(allege, lue=True)],
                        "saisieActualite": False}))
        routes.append(("l'entrée crue entière, lue=True, saisieActualite=True",
                       {"listeActualites": [dict(allege, lue=True)],
                        "saisieActualite": True}))
        # Le strict nécessaire, mais avec le public et le genrePublic de PRONOTE,
        # rendus tels quels — pas reconstruits.
        maigre = {"N": brut.get("N"), "lue": True}
        for champ in ("genrePublic", "public", "estSondage", "nature", "estAuteur"):
            if champ in brut:
                maigre[champ] = brut[champ]
        routes.append(("N + public et genrePublic de PRONOTE, verbatim",
                       {"listeActualites": [dict(maigre)], "saisieActualite": False}))
        routes.append(("idem, avec validationDirecte=False",
                       {"listeActualites": [dict(maigre, validationDirecte=False)],
                        "saisieActualite": False}))
        routes.append(("idem, avec validationDirecte=True",
                       {"listeActualites": [dict(maigre, validationDirecte=True)],
                        "saisieActualite": False}))
    routes.append(("N et lue seuls",
                   {"listeActualites": [{"N": cible.id, "lue": True}],
                    "saisieActualite": False}))
    if enfant_res is not None:
        routes.append(("l'ancienne route (enfant G=4), pour mémoire",
                       {"listeActualites": [{"N": cible.id, "validationDirecte": True,
                                             "genrePublic": 4,
                                             "public": {"N": enfant_res.id, "G": 4},
                                             "lue": True}],
                        "saisieActualite": False}))

    for nom_route, corps in routes:
        print(essai(client, nom_route, corps))
        maintenant = compte(client)
        if maintenant != avant:
            print(f"      LE COMPTEUR A BOUGÉ : {avant} → {maintenant}")
            try:
                client.post("SaisieActualites", 8, {
                    "listeActualites": [dict(corps["listeActualites"][0], lue=False)],
                    "saisieActualite": False})
                print(f"      remis non lu : {compte(client)}")
            except Exception as e:
                print(f"      ATTENTION, remise en non-lu échouée ({type(e).__name__})")
            return
    print(f"      non-lus après toutes les routes : {compte(client)}")
    print(f"      VERDICT : aucune route n'a fait bouger le compteur")


def main() -> int:
    client, mode = fetch.connexion()
    if not getattr(client, "logged_in", True):
        print("Connexion refusée par PRONOTE.", file=sys.stderr)
        return 2
    print(f"Connexion : {mode} · {len(client.children)} enfant(s)")
    print(f"Non-lus au départ : {compte(client)}")
    for enfant in client.children:
        try:
            discussions(client, enfant)
        except Exception:
            traceback.print_exc(limit=2)
        try:
            informations(client, enfant)
        except Exception:
            traceback.print_exc(limit=2)
    print(f"Non-lus à l'arrivée : {compte(client)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
