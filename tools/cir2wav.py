#!/usr/bin/env python3
"""
cir2wav.py
===========
Convertit une sortie wrdata de ngspice (2 colonnes: temps, tension) en
fichier .wav ecoutable, pour "entendre" un kit EX-SYSTEM simule.

Usage:
    python tools/cir2wav.py out/earphone.txt out/kit087.wav
"""
import sys

import numpy as np
import scipy.io.wavfile as wav


def main():
    if len(sys.argv) != 3:
        print("Usage: cir2wav.py <input.txt> <output.wav>", file=sys.stderr)
        sys.exit(1)

    in_path, out_path = sys.argv[1], sys.argv[2]
    data = np.loadtxt(in_path, skiprows=1)
    t, v = data[:, 0], data[:, 1]

    peak = np.max(np.abs(v))
    if peak > 0:
        v = v / (peak * 1.1)

    sample_rate = int(round(1 / (t[1] - t[0])))
    wav.write(out_path, sample_rate, (v * 32767).astype("<h"))
    print(f"Ecrit {out_path} ({sample_rate} Hz, {len(v)} echantillons)")


if __name__ == "__main__":
    main()
