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

    base = {"N": cible.id, "validationDirecte": True, "lue": True}
    routes = []
    if enfant_res is not None:
        routes.append(("adressée à l'enfant (G=4)",
                       {"listeActualites": [dict(base, genrePublic=4,
                                                 public={"N": enfant_res.id, "G": 4})],
                        "saisieActualite": False}))
    if parent_res is not None:
        g = getattr(parent_res, "_raw_g", 4)
        routes.append(("adressée au parent, comme pronotepy (G=4)",
                       {"listeActualites": [dict(base, genrePublic=4,
                                                 public={"N": parent_res.id, "G": 4})],
                        "saisieActualite": False}))
        routes.append(("adressée au parent, G=3",
                       {"listeActualites": [dict(base, genrePublic=3,
                                                 public={"N": parent_res.id, "G": 3})],
                        "saisieActualite": False}))
    # Ce que PRONOTE décrit lui-même : on le lui rend tel quel.
    for chemin, g in descripteurs(brut)[:4]:
        cible_desc = brut
        for morceau in chemin.split("."):
            if not morceau or morceau.endswith("[]"):
                cible_desc = None
                break
            cible_desc = (cible_desc or {}).get(morceau)
        if isinstance(cible_desc, dict) and "N" in cible_desc:
            routes.append((f"descripteur de PRONOTE « {chemin} » (G={g})",
                           {"listeActualites": [dict(base, genrePublic=g,
                                                     public={"N": cible_desc["N"], "G": g})],
                            "saisieActualite": False}))
    routes.append(("sans public, lue seule",
                   {"listeActualites": [dict(base)], "saisieActualite": False}))

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
