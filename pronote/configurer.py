#!/usr/bin/env python3
"""Prépare, sur votre ordinateur, les identifiants à mettre dans les secrets GitHub.

Deux voies :

  python3 pronote/configurer.py --qr
      Sur PRONOTE (espace Parents) → Mon compte → « Générer un QR code de
      connexion à l'application mobile » ; vous choisissez un code à 4 chiffres.
      Copiez le contenu du QR code (un JSON avec « login », « jeton », « url »),
      collez-le ici avec le code : le script imprime le secret PRONOTE_TOKEN_JSON.
      Le vrai mot de passe du compte ne quitte jamais votre ordinateur.

  python3 pronote/configurer.py --mdp
      Vérifie la connexion par identifiant + mot de passe, et enregistre cet
      « appareil » si le compte a la double authentification (code PIN demandé).
      Imprime le PRONOTE_CLIENT_ID à conserver pour que PRONOTE reconnaisse
      l'appareil aux connexions suivantes.

Rien n'est envoyé ailleurs qu'à PRONOTE ; les valeurs affichées sont à coller
dans Settings → Secrets and variables → Actions du dépôt.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import uuid

URL_DEFAUT = "https://0940575p.index-education.net/pronote/parent.html"


def _pronotepy():
    try:
        import pronotepy
    except ImportError:
        sys.exit("pronotepy manque : pip install -r pronote/requirements.txt")
    return pronotepy


def voie_qr(appareil: str) -> None:
    pronotepy = _pronotepy()
    print("Collez le JSON du QR code (une seule ligne), puis Entrée :")
    brut = input("> ").strip()
    try:
        qr = json.loads(brut)
    except ValueError:
        sys.exit("Ce n'est pas un JSON. Il doit contenir « login », « jeton » et « url ».")
    code = getpass.getpass("Code à 4 chiffres choisi pour le QR code : ").strip()
    pin = getpass.getpass("Code PIN du compte (double authentification), vide si aucun : ").strip() or None

    client = pronotepy.ParentClient.qrcode_login(
        qr, code, uuid=str(uuid.uuid4()), account_pin=pin, device_name=appareil,
    )
    if not client.logged_in:
        sys.exit("Connexion refusée.")
    print(f"\nConnecté. Enfants : {', '.join(c.name for c in client.children)}")
    print("\nSecret PRONOTE_TOKEN_JSON (une ligne, à coller tel quel) :\n")
    print(json.dumps(client.export_credentials()))
    print("\nLe jeton change à chaque connexion : le workflow le remet à jour lui-même,"
          "\nà condition d'avoir le secret PRONOTE_SECRETS_PAT (voir README).")


def voie_mdp(appareil: str) -> None:
    pronotepy = _pronotepy()
    url = input(f"URL de l'espace Parents [{URL_DEFAUT}] : ").strip() or URL_DEFAUT
    utilisateur = input("Identifiant : ").strip()
    mot_de_passe = getpass.getpass("Mot de passe : ")
    pin = getpass.getpass("Code PIN (double authentification), vide si aucun : ").strip() or None
    client_id = input("PRONOTE_CLIENT_ID existant (vide pour en obtenir un) : ").strip() or None

    client = pronotepy.ParentClient(
        url, username=utilisateur, password=mot_de_passe,
        account_pin=pin, client_identifier=client_id, device_name=appareil,
    )
    if not client.logged_in:
        sys.exit("Connexion refusée : identifiants ?")
    print(f"\nConnecté. Enfants : {', '.join(c.name for c in client.children)}")
    print("\nSecrets à créer :")
    print(f"  PRONOTE_URL        = {url}")
    print(f"  PRONOTE_USERNAME   = {utilisateur}")
    print("  PRONOTE_PASSWORD   = (votre mot de passe)")
    if pin:
        print("  PRONOTE_PIN        = (votre code PIN)")
    print(f"  PRONOTE_CLIENT_ID  = {client.client_identifier}")
    print(f"  PRONOTE_DEVICE_NAME = {appareil}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--qr", action="store_true", help="jeton d'application mobile (recommandé)")
    g.add_argument("--mdp", action="store_true", help="identifiant et mot de passe")
    p.add_argument("--appareil", default="Planning famille", help="nom de l'appareil enregistré")
    args = p.parse_args()
    (voie_qr if args.qr else voie_mdp)(args.appareil)


if __name__ == "__main__":
    main()
