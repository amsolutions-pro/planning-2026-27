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


def compte(client):
    """Le compte des non-lus, ou None si la session n'a pas répondu.

    Distinction capitale : la dernière épreuve a pris une session expirée pour
    un compteur qui bouge, et s'est arrêtée sur une fausse victoire.
    """
    texte = fetch.non_lus(client)
    return None if "(" in texte else texte


def rejoindre(client, enfant):
    """Rouvre une session quand PRONOTE fait « la page a expiré »."""
    try:
        if compte(client) is not None:
            client.set_child(enfant.name)
            return client
    except Exception:
        pass
    neuf, _ = fetch.connexion()
    neuf.set_child(enfant.name)
    print("      (session rouverte)")
    return neuf


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


def essai(client, nom: str, corps: dict, fonction: str = "SaisieActualites") -> str:
    try:
        reponse = client.post(fonction, 8, corps)
    except Exception as e:
        return f"    {nom} → exception {type(e).__name__}"
    if fonction == "PageActualites":
        # Ici PRONOTE ne rend pas de rapport de saisie : il rend la page. Ce
        # qui compte est qu'il l'ait rendue, et surtout ce que devient le
        # compteur juste après.
        recu = ((reponse or {}).get("dataSec") or {}).get("data") or {}
        return f"    {nom} → page rendue, clés {sorted(recu)[:4]}"
    return f"    {nom} → {rapport(reponse)}"


def onglets(client) -> None:
    """La carte des sous-sections que PRONOTE ouvre à ce compte.

    « Communication » en abrite plusieurs — informations & sondages, discussions,
    agenda, casier… — chacune avec son numéro d'onglet. C'est ce numéro qu'il faut
    pour aller lire une section que la bibliothèque n'expose pas. Rien de personnel
    ici : des numéros et des noms de rubriques.
    """
    donnees = (getattr(client, "parametres_utilisateur", None) or {}).get("dataSec", {}).get("data", {})
    liste = donnees.get("listeOnglets")
    if not liste:
        print("  onglets : rien dans ParametresUtilisateur")
        return
    autorises = getattr(getattr(client, "communication", None), "authorized_onglets", []) or []
    print(f"  onglets autorisés (numéros) : {sorted(autorises)}")

    def parcours(noeud, profondeur=0):
        if isinstance(noeud, dict):
            g, libelle = noeud.get("G"), noeud.get("L") or noeud.get("Libelle")
            if g is not None:
                print(f"      {'  ' * profondeur}onglet {g}"
                      + (f" · « {libelle} »" if libelle else "")
                      + (f" · {len(noeud.get('Onglet', {}).get('V', []) or [])} sous-section(s)"
                         if noeud.get("Onglet") else ""))
            for cle in ("Onglet", "listeOnglets", "V"):
                if cle in noeud:
                    parcours(noeud[cle], profondeur + (1 if g is not None else 0))
        elif isinstance(noeud, list):
            for x in noeud:
                parcours(x, profondeur)

    parcours(liste)


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

    # Ce que le dernier tour a appris, et qui commande l'ordre d'ici :
    #   * l'entrée s'annonce en genrePublic 2, jamais 4 — pronotepy code 4 en dur ;
    #   * son « public » est la classe (G=5), pas une personne ;
    #   * OUVRIR l'information adressée à L'ENFANT (G=4) est la seule requête qui
    #     ait rendu la page de détail. Dans l'espace du collège, ouvrir marque lu.
    # On commence donc par elle, et on mesure aussitôt.
    ouverture = {"genreRequeteActualite": 1, "modeAffActu": 0}
    routes = []
    if enfant_res is not None:
        routes.append(("OUVRIR au nom de l'enfant (G=4) — la seule qui rendait la page",
                       dict(ouverture, actualite={"N": cible.id, "genrePublic": 4,
                                                  "public": {"N": enfant_res.id, "G": 4}}),
                       "PageActualites"))
    # Puis la matrice : le genrePublic annoncé par l'entrée croisé avec chaque
    # destinataire plausible. Deux cases n'avaient jamais été essayées ensemble.
    pub_entree = brut.get("public")
    pub_v = pub_entree.get("V") if isinstance(pub_entree, dict) else None
    destinataires = []
    if enfant_res is not None:
        destinataires.append(("l'enfant G=4", {"N": enfant_res.id, "G": 4}))
    if isinstance(pub_v, dict):
        destinataires.append(("la classe G=%s" % pub_v.get("G"), pub_v))
    if isinstance(pub_entree, dict):
        destinataires.append(("le « public » entier de PRONOTE", pub_entree))
    genres = [g for g in (brut.get("genrePublic"), 4, 2) if g is not None]
    vus_genres = []
    for g in genres:
        if g in vus_genres:
            continue
        vus_genres.append(g)
        for nom_dest, dest in destinataires:
            routes.append((f"SAISIE · genrePublic={g} · {nom_dest}",
                           {"listeActualites": [{"N": cible.id, "lue": True,
                                                 "validationDirecte": True,
                                                 "genrePublic": g, "public": dest}],
                            "saisieActualite": False}))
    if brut:
        routes.append(("SAISIE · l'entrée crue entière",
                       {"listeActualites": [dict(allege, lue=True)],
                        "saisieActualite": False}))
    routes.append(("SAISIE · N et lue seuls",
                   {"listeActualites": [{"N": cible.id, "lue": True}],
                    "saisieActualite": False}))
    if enfant_res is not None:
        routes.append(("OUVRIR avec le genrePublic de l'entrée",
                       dict(ouverture, actualite={"N": cible.id,
                                                  "genrePublic": brut.get("genrePublic", 2),
                                                  "public": {"N": enfant_res.id, "G": 4}}),
                       "PageActualites"))

    for route in routes:
        nom_route, corps = route[0], route[1]
        fonction = route[2] if len(route) > 2 else "SaisieActualites"
        print(essai(client, nom_route, corps, fonction))
        maintenant = compte(client)
        if maintenant is None:
            # Session tombée : on la rouvre et on passe à la suivante, sans
            # rien conclure. Une session morte n'est pas une preuve.
            client = rejoindre(client, enfant)
            maintenant = compte(client)
        if maintenant is not None and avant is not None and maintenant != avant:
            print(f"      LE COMPTEUR A BOUGÉ : {avant} → {maintenant}")
            try:
                if "listeActualites" in corps:
                    client.post("SaisieActualites", 8, {
                        "listeActualites": [dict(corps["listeActualites"][0], lue=False)],
                        "saisieActualite": False})
                else:
                    # L'ouverture a marqué : on repasse en non lu par la saisie,
                    # avec l'adressage de l'entrée.
                    client.post("SaisieActualites", 8, {
                        "listeActualites": [dict(corps["actualite"], lue=False)],
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
    try:
        onglets(client)
    except Exception:
        traceback.print_exc(limit=2)
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
