#!/usr/bin/env python3
"""
validate_wiring.py
====================
Verifie un fichier de cablage JSON AVANT simulation :
  - chaque instance reference un bloc existant dans le catalogue
  - chaque pin declare par le bloc est bien connecte
  - aucune connexion ne depasse la tension max declaree par un bloc
    (approxime a partir de la tension batterie declaree)
  - aucun "forbidden_direct_link" du catalogue n'est cree par le cablage
    (deux pins interdits relies au meme noeud)

C'est un DRC (Design Rule Check) simplifie : il n'analyse pas le
comportement electrique reel (il faudrait ngspice pour ca), seulement la
coherence topologique et les contraintes declarees dans catalog/blocks.json.

Usage:
    python tools/validate_wiring.py examples/wiring_kit087.json
Sortie : code 0 si valide, 1 si erreurs (listees sur stderr).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_catalog(catalog_path: Path) -> dict:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {b["id"]: b for b in data["blocks"]}


def validate(wiring: dict, catalog: dict) -> list[str]:
    errors = []
    batt_voltage = wiring.get("battery", {}).get("voltage", 0)

    # Regroupe les pins par noeud logique pour detecter les liens interdits
    node_to_pins = {}  # noeud -> liste de (instance_id, pin_name, block_id)

    for inst in wiring.get("instances", []):
        block = catalog.get(inst["block_id"])
        ref = inst.get("instance_id", "?")

        if block is None:
            errors.append(f"[{ref}] bloc inconnu dans le catalogue : '{inst['block_id']}'")
            continue

        expected_pins = set(block["pins"])
        given_pins = set(inst.get("connections", {}).keys())

        missing = expected_pins - given_pins
        extra = given_pins - expected_pins
        if missing:
            errors.append(f"[{ref}] pins non connectees pour '{block['id']}': {sorted(missing)}")
        if extra:
            errors.append(f"[{ref}] pins inconnues pour '{block['id']}': {sorted(extra)}")

        constraints = block.get("constraints", {})
        vmax = constraints.get("vmax")
        if vmax is not None and batt_voltage > vmax:
            errors.append(
                f"[{ref}] tension batterie declaree ({batt_voltage}V) depasse le "
                f"vmax du bloc '{block['id']}' ({vmax}V)"
            )

        for pin_name, node in inst.get("connections", {}).items():
            node_to_pins.setdefault(node, []).append((ref, pin_name, block["id"]))

    # Verification des forbidden_direct_links : deux pins interdits du MEME
    # bloc/instance ne doivent pas se retrouver sur le meme noeud.
    for inst in wiring.get("instances", []):
        block = catalog.get(inst["block_id"])
        if block is None:
            continue
        forbidden = block.get("constraints", {}).get("forbidden_direct_links", [])
        conn = inst.get("connections", {})
        for pin_a, pin_b in forbidden:
            node_a = conn.get(pin_a)
            node_b = conn.get(pin_b)
            if node_a is not None and node_a == node_b:
                errors.append(
                    f"[{inst['instance_id']}] lien interdit : '{pin_a}' et '{pin_b}' "
                    f"sont relies au meme noeud '{node_a}' (court-circuit connu du bloc "
                    f"'{block['id']}')"
                )

    # Un noeud avec un seul pin est probablement un oubli de cablage
    for node, pins in node_to_pins.items():
        if len(pins) == 1 and node not in (wiring.get("battery", {}).get("node_plus"),
                                            wiring.get("battery", {}).get("node_minus")):
            ref, pin_name, block_id = pins[0]
            errors.append(
                f"[{ref}] la pin '{pin_name}' (bloc '{block_id}') est seule sur le "
                f"noeud '{node}' - cablage probablement incomplet"
            )

    return errors


def main():
    if len(sys.argv) != 2:
        print("Usage: validate_wiring.py <wiring.json>", file=sys.stderr)
        sys.exit(1)

    wiring_path = Path(sys.argv[1])
    wiring = json.loads(wiring_path.read_text(encoding="utf-8"))
    catalog = load_catalog(ROOT / "catalog" / "blocks.json")

    errors = validate(wiring, catalog)
    if errors:
        print(f"❌ {len(errors)} erreur(s) trouvee(s) dans {wiring_path.name} :", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"✅ {wiring_path.name} est valide.")
        sys.exit(0)


if __name__ == "__main__":
    main()
