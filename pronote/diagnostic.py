"""D'où viennent les annulations de cours, chez vous ?

Deux sources possibles, et le traitement n'est pas le même :
  * l'emploi du temps — PRONOTE marque la séance `canceled` ou lui donne un
    `status` (« Cours annulé », « Prof. absent »…). C'est net, daté, exploitable
    tel quel : on peut barrer la case sur la grille de la semaine ;
  * un message ou une information du collège — il faut alors lire le texte pour
    savoir quel cours, et quel jour. C'est un tout autre travail.

Cette épreuve ne fait que **lire**. Elle n'imprime que des nombres, le vocabulaire
de PRONOTE lui-même et des écarts en jours : le journal d'une action est public.
"""

import datetime as dt
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch  # noqa: E402

MOTS = re.compile(r"annul|déplac|deplac|report|absent|remplac|libér|liber|modifi", re.I)
# « le 22 septembre », « mardi 22 », « 22/09 » : de quoi dater un texte.
DATES = re.compile(r"\b\d{1,2}[/-]\d{1,2}|\b\d{1,2}\s+(?:janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec)", re.I)
JOURS = re.compile(r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi)\b", re.I)


def emploi_du_temps(client, enfant) -> None:
    client.set_child(enfant.name)
    debut = dt.date.today()
    fin = debut + dt.timedelta(days=14)
    seances = list(client.lessons(debut, fin))
    perturbees = [l for l in seances if l.canceled or l.status]
    statuts = sorted({(l.status or "canceled") for l in perturbees})
    print(f"  {fetch.prenom(enfant.name)} : {len(seances)} séance(s) sur 14 jours, "
          f"{len(perturbees)} perturbée(s)")
    for l in perturbees:
        ecart = (l.start.date() - debut).days
        print(f"      « {l.status or 'annulé'} » · J{ecart:+d} · {l.start.strftime('%H:%M')}")
    if not perturbees:
        print(f"      aucun statut posé par le collège sur l'emploi du temps")
    print(f"      vocabulaire rencontré : {statuts or '—'}")


def communications(client, enfant) -> None:
    client.set_child(enfant.name)
    nom = fetch.prenom(enfant.name)
    aujourdhui = dt.date.today()

    parlantes = 0
    for d in list(client.discussions())[:fetch.MAX_DISCUSSIONS]:
        msgs = list(d.messages)
        if not msgs:
            continue
        texte = f"{d.subject or ''} {msgs[-1].content or ''}"
        if not MOTS.search(texte):
            continue
        parlantes += 1
        ecart = (msgs[-1].created.date() - aujourdhui).days
        print(f"      message J{ecart:+d} · mot d'annulation : oui · date dans le texte : "
              f"{'oui' if DATES.search(texte) else 'non'} · jour nommé : "
              f"{'oui' if JOURS.search(texte) else 'non'}")
    print(f"  {nom} · messagerie : {parlantes} discussion(s) parlant d'annulation")

    parlantes = 0
    lues = 0
    for i in client.information_and_surveys():
        texte = i.title or ""
        if lues < 12:
            lues += 1
            try:
                texte += " " + (i.content() or "")
            except Exception:
                pass
        if not MOTS.search(texte):
            continue
        parlantes += 1
        quand = (i.start_date or i.creation_date)
        ecart = (quand.date() - aujourdhui).days if quand else 0
        print(f"      information J{ecart:+d} · date dans le texte : "
              f"{'oui' if DATES.search(texte) else 'non'} · jour nommé : "
              f"{'oui' if JOURS.search(texte) else 'non'}")
    print(f"  {nom} · informations : {parlantes} parlant d'annulation")


def main() -> int:
    client, mode = fetch.connexion()
    print(f"Connexion : {mode} · {len(client.children)} enfant(s) · {dt.date.today()}")
    print("Emploi du temps (ce que PRONOTE marque lui-même) :")
    for enfant in client.children:
        emploi_du_temps(client, enfant)
    print("Communications (ce qu'il faudrait lire dans le texte) :")
    for enfant in client.children:
        communications(client, enfant)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
