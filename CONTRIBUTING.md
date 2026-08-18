# Contribuer un Denshi Block

Merci de vouloir enrichir la platine virtuelle ! Voici comment proposer :

## A) Un montage officiel du manuel (nouvelle page)

1. Ajoutez vos notes de lecture dans `scans/pXXX_notes.md` (pas le scan
   lui-même — voir `scans/README.md`).
2. Créez `examples/wiring_kitNNN_slug.json` en suivant le format de
   `examples/wiring_kit087.json`, en réutilisant les blocs existants du
   `catalog/blocks.json` autant que possible.
3. Lancez localement :
   ```bash
   python tools/validate_wiring.py examples/wiring_kitNNN_slug.json
   python tools/wiring_to_netlist.py examples/wiring_kitNNN_slug.json > netlists/kitNNN_slug.cir
   ngspice -b netlists/kitNNN_slug.cir
   ```
4. Ajoutez une ligne au tableau de chasse dans `README.md` avec les mesures
   obtenues et ce que dit le manuel (fréquence, tension attendue...).
5. Ouvrez une Pull Request — la CI relance automatiquement toutes les
   simulations.

## B) Un Denshi Block personnel (bloc inédit)

1. Écrivez le subcircuit SPICE dans `lib/community/<votre_bloc>.lib`.
2. Décrivez ses métadonnées dans `catalog/blocks.json`, en respectant
   `schema/block_schema.json` :
   - `pins` doit lister les pins **dans le même ordre** que dans votre
     `.subckt`.
   - Déclarez `constraints.vmax` et `polarity_sensitive` de façon réaliste :
     c'est ce qui protège les autres contributeurs qui réutiliseront votre
     bloc dans un câblage.
   - Si votre bloc a des combinaisons de pins qui créent un court-circuit
     connu, listez-les dans `forbidden_direct_links`.
3. Fournissez un exemple de câblage minimal dans `examples/` qui utilise
   votre bloc, pour prouver qu'il fonctionne.
4. `source: "communaute"` dans les métadonnées (réservé aux blocs officiels
   sinon).

## Style des netlists

- Un fichier `.lib` par catégorie de composant, jamais un montage complet
  codé en dur dans une lib.
- Les fichiers dans `netlists/` sont **générés** par
  `tools/wiring_to_netlist.py` à partir de `examples/*.json` — ne les éditez
  pas à la main, éditez le JSON de câblage.
- Toute mesure comparée au manuel doit passer par `.meas` dans le JSON de
  simulation, pas juste par un `plot` visuel — c'est ce qui permet à la CI
  de détecter une régression.
