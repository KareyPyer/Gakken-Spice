#!/usr/bin/env python3
"""
wiring_to_netlist.py
=====================
Transforme un fichier de cablage JSON (voir examples/wiring_kit087.json)
en netlist ngSpice complet (.cir), en s'appuyant sur catalog/blocks.json
pour resoudre chaque instance de bloc vers son subcircuit SPICE.

Usage:
    python tools/wiring_to_netlist.py examples/wiring_kit087.json > netlists/kit087_gen-ca.cir
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_catalog(catalog_path: Path) -> dict:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {b["id"]: b for b in data["blocks"]}


def instance_line(instance: dict, block: dict) -> str:
    """Construit la ligne d'instanciation SPICE pour une instance de bloc."""
    conn = instance["connections"]
    pins_ordered = [conn[p] for p in block["pins"]]
    ref = instance["instance_id"]

    if block["subckt"].startswith("__MODEL_"):
        # Cas special : ce n'est pas un .subckt mais un .model (ex: transistor
        # discret). On genere une ligne Q<ref> c b e MODELNAME.
        model_name = block["subckt"].replace("__MODEL_", "").strip("_")
        c, b, e = pins_ordered
        return f"Q{ref} {c} {b} {e} {model_name}"

    params = block.get("params", {})
    override = instance.get("params", {})
    merged = {**params, **override}
    param_str = " ".join(f"{k}={v}" for k, v in merged.items())
    pins_str = " ".join(pins_ordered)
    line = f"X{ref} {pins_str} {block['subckt']}"
    if param_str:
        line += f" {param_str}"
    return line


def build_netlist(wiring: dict, catalog: dict) -> str:
    lines = []
    lines.append(f"* ============================================================")
    lines.append(f"* {wiring.get('title', 'Sans titre')}")
    lines.append(f"* Genere automatiquement par wiring_to_netlist.py - ne pas editer a la main")
    lines.append(f"* ============================================================\n")

    # .include pour chaque fichier .lib distinct utilise
    lib_files = sorted({catalog[i["block_id"]]["subckt_file"] for i in wiring["instances"]})
    for lib in lib_files:
        lines.append(f".include {lib}")
    lines.append("")

    # Alimentation
    batt = wiring["battery"]
    lines.append(f"VIN {batt['node_plus']} {batt['node_minus']} DC {batt['voltage']}")
    lines.append("")

    # Instances
    lines.append("*--- Composants du montage")
    for inst in wiring["instances"]:
        block = catalog.get(inst["block_id"])
        if block is None:
            raise ValueError(f"Bloc inconnu dans le catalogue : {inst['block_id']}")
        lines.append(instance_line(inst, block))
    lines.append("")

    # Simulation
    sim = wiring.get("simulation", {})
    if "initial_conditions" in sim:
        ic = " ".join(f"{k}={v}" for k, v in sim["initial_conditions"].items())
        lines.append(f".ic {ic}")
    if "tran_step" in sim and "tran_stop" in sim:
        lines.append(f".tran {sim['tran_step']} {sim['tran_stop']} UIC")
    lines.append("")

    lines.append(".control")
    lines.append("run")
    for meas in sim.get("measurements", []):
        lines.append(meas)
    for plot in sim.get("plots", []):
        lines.append(f"plot {plot}")
    if "export_wav_signal" in sim:
        lines.append(f"wrdata out/earphone.txt {sim['export_wav_signal']}")
    lines.append(".endc")
    lines.append(".end")

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        print("Usage: wiring_to_netlist.py <wiring.json>", file=sys.stderr)
        sys.exit(1)

    wiring_path = Path(sys.argv[1])
    wiring = json.loads(wiring_path.read_text(encoding="utf-8"))
    catalog = load_catalog(ROOT / "catalog" / "blocks.json")

    netlist = build_netlist(wiring, catalog)
    print(netlist)


if __name__ == "__main__":
    main()
