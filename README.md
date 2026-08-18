# EX-150 → ngSpice

**Résurrection virtuelle du kit d'électronique LANSAY / Gakken EX-SYSTEM
(EX-150) des années 80.**

Ce projet transforme le manuel du kit en une bibliothèque de simulation
ngSpice : chaque page devient un netlist, chaque brique physique de la
platine devient un subcircuit réutilisable, et vous pouvez concevoir vos
propres **Denshi Blocks** et les tester avant de souder quoi que ce soit.

> ⚠️ **Disclaimer** : projet de passionné, non affilié à LANSAY, Gakken ou
> leurs ayants droit. « EX-SYSTEM » et « Denshi Block » sont cités à titre
> purement descriptif/éducatif. Les scans du manuel ne sont pas
> redistribués ici — voir `scans/README.md`.

---

## Sommaire

1. [Pourquoi ce projet](#pourquoi-ce-projet)
2. [Installation](#installation)
3. [Démarrage rapide (5 minutes)](#démarrage-rapide-5-minutes)
4. [Comment ça marche : les trois couches](#comment-ça-marche--les-trois-couches)
5. [Tutoriel — simuler le kit 87 pas à pas](#tutoriel--simuler-le-kit-87-pas-à-pas)
6. [Tutoriel — ajouter une nouvelle page du manuel](#tutoriel--ajouter-une-nouvelle-page-du-manuel)
7. [Tutoriel — créer votre propre Denshi Block](#tutoriel--créer-votre-propre-denshi-block)
8. [Référence : format du câblage JSON](#référence--format-du-câblage-json)
9. [Référence : format d'un bloc du catalogue](#référence--format-dun-bloc-du-catalogue)
10. [Intégration continue (CI)](#intégration-continue-ci)
11. [Dépannage](#dépannage)
12. [Glossaire](#glossaire)
13. [Arborescence complète](#arborescence-complète)
14. [Tableau de chasse](#tableau-de-chasse)
15. [Feuille de route](#feuille-de-route)

---

## Pourquoi ce projet

Le kit EX-SYSTEM permettait d'assembler des circuits en enfichant des
composants sur une platine à ressorts, sans soudure — un peu le "Lego" de
l'électronique des années 80. Mais deux limites en freinaient
l'expérimentation :

- on ne pouvait tester **que** les montages décrits dans le manuel,
- une erreur de câblage pouvait griller un composant.

Ce projet lève ces deux limites : les montages officiels sont modélisés en
SPICE et validés automatiquement contre les valeurs annoncées par le
manuel (fréquence, tension...), et un **validateur de câblage** détecte les
erreurs de montage *avant* toute simulation — donc avant tout risque, y
compris pour vos propres créations ("Denshi Blocks" personnels).

## Installation

Prérequis : Python ≥ 3.9, et [ngSpice](https://ngspice.sourceforge.io/)
installé et accessible dans votre `PATH`.

```bash
# Cloner le dépôt
git clone https://github.com/<votre-compte>/ex150-ngspice.git
cd ex150-ngspice

# Installer les dépendances Python (numpy, scipy pour l'export audio)
pip install -r requirements.txt

# Vérifier que ngspice est bien installé
ngspice -v
```

Sous Debian/Ubuntu, si `ngspice -v` échoue : `sudo apt install ngspice`.
Sous macOS avec Homebrew : `brew install ngspice`.

## Démarrage rapide (5 minutes)

Ces quatre commandes valident, génèrent, simulent et sonifient le montage
du **kit n°87 — Générateur à courant alternatif** (page 95 du manuel) :

```bash
# 1. Vérifier que le câblage JSON est cohérent (sans lancer SPICE)
python tools/validate_wiring.py examples/wiring_kit087.json

# 2. Générer le netlist ngspice à partir du câblage JSON
python tools/wiring_to_netlist.py examples/wiring_kit087.json > netlists/kit087_gen-ca.cir

# 3. Lancer la simulation
ngspice -b netlists/kit087_gen-ca.cir

# 4. Écouter le résultat (le manuel annonce un son audible, ~1 kHz)
python tools/cir2wav.py out/earphone.txt out/kit087.wav
```

Si tout se passe bien, l'étape 3 affiche une mesure `freq_osc` proche de
**~1 ms** de période (donc ~1 kHz), et `out/kit087.wav` contient le son que
produirait le kit réel dans l'écouteur cristal.

## Comment ça marche : les trois couches

Le principe central du projet : **on ne code jamais un montage en dur**.
Trois couches indépendantes, chacune avec sa responsabilité :

```
┌─────────────────────────────────────────────────────────┐
│ 1. lib/*.lib                                              │
│    Les briques physiques réelles du kit, en subcircuits   │
│    SPICE : résistance, transfo, écouteur, transistor...   │
├─────────────────────────────────────────────────────────┤
│ 2. catalog/blocks.json                                    │
│    Les métadonnées de chaque bloc : quelles pins, quelles │
│    contraintes (tension max, polarité), quel .lib l'héberge│
├─────────────────────────────────────────────────────────┤
│ 3. examples/*.json  (câblage)                              │
│    "Quel pin de quel bloc va sur quel nœud" — le montage   │
│    lui-même, en JSON pur, sans une ligne de SPICE.         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
        tools/wiring_to_netlist.py  (génère automatiquement)
                          │
                          ▼
                netlists/*.cir  (prêt pour ngspice)
```

**Pourquoi cette séparation ?** Parce qu'elle permet d'ajouter un bloc une
seule fois (couche 1+2) puis de l'utiliser dans n'importe quel montage
(couche 3) sans jamais retoucher le cœur du simulateur — que ce montage
soit une page officielle du manuel ou un Denshi Block que vous inventez.

Le fichier `tools/validate_wiring.py` intervient **avant** la génération :
il relit la couche 3 à la lumière des contraintes déclarées en couche 2, et
refuse de continuer si une pin manque, si une tension dépasse le maximum
déclaré, ou si deux pins connues pour créer un court-circuit se retrouvent
sur le même nœud.

## Tutoriel — simuler le kit 87 pas à pas

Ce tutoriel déroule en détail ce que fait le "démarrage rapide" ci-dessus,
pour comprendre chaque fichier impliqué.

### Étape 1 — Comprendre le montage d'origine

Le kit 87 (page 95 du manuel) est un **multivibrateur astable push-pull** :
deux transistors couplés en croix par des condensateurs oscillent, et un
transformateur à point milieu convertit ce signal en tension alternative
qui alimente un écouteur cristal. Le manuel annonce un son audible
(~1 kHz) et une tension secondaire de 10 à 20 V.

### Étape 2 — Repérer les blocs dans le catalogue

Ouvrez `catalog/blocks.json` : le montage utilise `r_10k`, `c_0_05u`,
`c_0_1u`, `transistor_npn`, `transfo_exsystem`, `r_4_7k` et
`ecouteur_cristal`. Chacun pointe vers un `.subckt` dans `lib/`.

### Étape 3 — Lire le câblage JSON

Ouvrez `examples/wiring_kit087.json`. Chaque entrée de `"instances"`
instancie un bloc du catalogue et précise, pour **chaque pin déclarée par
le bloc**, à quel nœud électrique elle se connecte :

```json
{ "instance_id": "R1", "block_id": "r_10k",
  "connections": { "1": "plus", "2": "b1" } }
```

→ "Instanciez une résistance 10K nommée R1, sa pin 1 va sur le nœud
`plus` (le +batterie), sa pin 2 va sur le nœud `b1` (la base de Q1)."

### Étape 4 — Valider avant de simuler

```bash
python tools/validate_wiring.py examples/wiring_kit087.json
```

Le validateur vérifie que toutes les pins de tous les blocs sont
connectées, qu'aucune tension déclarée n'est dépassée, et qu'aucun nœud
n'est "orphelin" (une seule pin dessus = câblage probablement incomplet).

### Étape 5 — Générer et simuler

```bash
python tools/wiring_to_netlist.py examples/wiring_kit087.json > netlists/kit087_gen-ca.cir
ngspice -b netlists/kit087_gen-ca.cir
```

Le script traduit chaque instance en ligne SPICE (`X...` pour un
subcircuit, `Q...` pour un transistor discret), ajoute les `.include` des
bibliothèques utilisées, la source de tension `VIN`, les conditions
initiales (`.ic`, nécessaires pour "casser la symétrie" et démarrer
l'oscillation), et le bloc `.control` avec les mesures et exports définis
dans `"simulation"`.

### Étape 6 — Écouter le résultat

```bash
python tools/cir2wav.py out/earphone.txt out/kit087.wav
```

Le signal `v_ear` (différentiel aux bornes de l'écouteur, exporté par
`wrdata` dans le netlist) est normalisé et converti en `.wav` 16 bits.

## Tutoriel — ajouter une nouvelle page du manuel

Supposons que vous scannez la page 88 du manuel (à adapter à ce qu'elle
contient réellement) :

1. **Notez le montage** dans `scans/p088_notes.md` : composants, valeurs,
   comportement attendu selon le manuel (voir `scans/README.md` pour la
   politique sur les scans eux-mêmes).

2. **Vérifiez si les blocs existent déjà** dans `catalog/blocks.json`. Si
   le montage réutilise une résistance 10K ou l'écouteur cristal, rien à
   ajouter. S'il introduit un composant inédit (une LED, un moteur...),
   passez par le tutoriel suivant pour l'ajouter au catalogue.

3. **Créez le câblage** dans `examples/wiring_kit088_<slug>.json`, sur le
   modèle de `wiring_kit087.json`.

4. **Validez, générez, simulez** :
   ```bash
   python tools/validate_wiring.py examples/wiring_kit088_<slug>.json
   python tools/wiring_to_netlist.py examples/wiring_kit088_<slug>.json > netlists/kit088_<slug>.cir
   ngspice -b netlists/kit088_<slug>.cir
   ```

5. **Comparez les mesures** obtenues aux valeurs annoncées par le manuel,
   et ajoutez une ligne dans le [tableau de chasse](#tableau-de-chasse).

6. **Committez** `scans/p088_notes.md`, le fichier de câblage, et le
   netlist généré, puis ouvrez une Pull Request — la CI rejoue
   automatiquement toutes les simulations du dépôt.

## Tutoriel — créer votre propre Denshi Block

C'est le deuxième objectif du projet : concevoir un bloc qui n'existe pas
dans le kit d'origine, et le tester en toute sécurité avant tout câblage
physique.

### Étape 1 — Écrire le subcircuit SPICE

Créez `lib/community/mon_bloc.lib` avec votre subcircuit :

```spice
* mon_bloc.lib - clignoteur LED communautaire
.subckt XFLASH in_plus in_moins out
* ... votre logique SPICE ici ...
.ends XFLASH
```

### Étape 2 — Décrire le bloc dans le catalogue

Ajoutez une entrée à `catalog/blocks.json`, conforme à
`schema/block_schema.json` :

```json
{
  "id": "mon_clignoteur",
  "label": "Mon clignoteur LED",
  "category": "actif",
  "source": "communaute",
  "manual_page": null,
  "pins": ["in_plus", "in_moins", "out"],
  "subckt": "XFLASH",
  "subckt_file": "lib/community/mon_bloc.lib",
  "constraints": {
    "vmax": 15,
    "polarity_sensitive": true,
    "forbidden_direct_links": [["in_plus", "in_moins"]]
  }
}
```

L'ordre de `"pins"` **doit** correspondre exactement à l'ordre des pins
dans votre `.subckt` — c'est ce qui garantit que le générateur relie les
bons nœuds aux bonnes broches.

Déclarez `constraints` avec honnêteté : c'est ce qui protège tout
contributeur qui réutilisera votre bloc dans un câblage qu'il n'a pas
conçu lui-même.

### Étape 3 — Écrire un câblage minimal de démonstration

Créez `examples/wiring_mon_clignoteur.json` qui instancie votre bloc et
prouve qu'il fonctionne isolément (batterie + bloc + une charge simple).

### Étape 4 — Valider, générer, simuler

Exactement les mêmes trois commandes que pour un montage officiel :

```bash
python tools/validate_wiring.py examples/wiring_mon_clignoteur.json
python tools/wiring_to_netlist.py examples/wiring_mon_clignoteur.json > netlists/mon_clignoteur.cir
ngspice -b netlists/mon_clignoteur.cir
```

Si le validateur remonte une erreur (pin manquante, tension excessive,
lien interdit détecté), corrigez le câblage — c'est précisément ce
garde-fou logiciel qui remplace le composant grillé du kit physique.

### Étape 5 — Partager

Voir `CONTRIBUTING.md` pour le format exact de Pull Request attendu.

## Référence : format du câblage JSON

Un fichier `examples/wiring_*.json` a la structure suivante :

| Champ | Type | Description |
|---|---|---|
| `title` | string | Nom lisible du montage |
| `manual_page` | int / null | Page du manuel, ou `null` pour un montage perso |
| `battery.node_plus` | string | Nom du nœud relié au + de la pile |
| `battery.node_minus` | string | Nom du nœud relié au − (souvent `"0"`, la masse SPICE) |
| `battery.voltage` | number | Tension de la pile, en volts |
| `instances[]` | array | Liste des composants instanciés (voir ci-dessous) |
| `simulation.initial_conditions` | object | Conditions initiales `.ic` (utile pour démarrer une oscillation) |
| `simulation.tran_step` / `tran_stop` | string | Pas et durée de l'analyse transitoire |
| `simulation.measurements[]` | array | Lignes SPICE brutes (`let`, `meas tran`...) injectées dans `.control` |
| `simulation.plots[]` | array | Expressions à tracer (`plot ...`) |
| `simulation.export_wav_signal` | string | Nom du signal à exporter vers `out/earphone.txt` pour `cir2wav.py` |

Chaque élément de `instances[]` :

| Champ | Type | Description |
|---|---|---|
| `instance_id` | string | Référence unique dans le netlist (ex: `"R1"`) |
| `block_id` | string | Doit exister dans `catalog/blocks.json` |
| `connections` | object | `{ "<pin_du_bloc>": "<nœud_du_montage>" }`, une entrée par pin déclarée par le bloc |
| `params` | object (optionnel) | Surcharge les `params` par défaut du bloc (ex: une valeur de résistance différente) |

## Référence : format d'un bloc du catalogue

Voir `schema/block_schema.json` pour la spécification complète (validable
avec `jsonschema`). Les champs clés :

- **`pins`** : ordre exact attendu par le `.subckt` — c'est la seule chose
  qui doit rester strictement synchronisée entre le catalogue et le fichier
  `.lib`.
- **`subckt`** : nom du subcircuit SPICE. Cas particulier : un composant
  discret défini par `.model` plutôt que `.subckt` (typiquement un
  transistor) utilise la convention `"__MODEL_<nom>__"` — le générateur
  produit alors une ligne `Q<ref>` au lieu de `X<ref>`.
- **`constraints.vmax`** : tension maximale tolérée entre deux pins du
  bloc ; le validateur la compare à `battery.voltage` du câblage.
- **`constraints.forbidden_direct_links`** : paires de pins qui ne doivent
  jamais partager le même nœud (court-circuit connu).

## Intégration continue (CI)

`.github/workflows/ci.yml` s'exécute à chaque push / Pull Request :

1. installe `ngspice` et les dépendances Python,
2. valide **tous** les fichiers `examples/*.json`,
3. régénère **tous** les netlists depuis ces fichiers de câblage,
4. lance `ngspice -b` sur chaque netlist généré,
5. publie les sorties (`out/`) comme artefact téléchargeable.

Concrètement : si vous modifiez une bibliothèque `.lib` (par exemple pour
affiner un modèle de transistor), la CI rejoue automatiquement tous les
montages existants et vous saurez immédiatement si le changement casse un
montage qui fonctionnait auparavant.

## Dépannage

**`ngspice` reste en équilibre / n'oscille jamais** : un montage
symétrique (comme le multivibrateur du kit 87) a besoin d'une condition
initiale qui casse la symétrie — vérifiez `simulation.initial_conditions`
dans votre câblage JSON.

**Erreur SPICE sur un couplage à trois inductances (`K... L1 L2 L3`)** :
certaines versions de ngspice n'acceptent qu'un couplage entre deux
inductances à la fois. Remplacez un `K` à trois enroulements par trois `K`
deux-à-deux (`K12 L1 L2 val`, `K13 L1 L3 val`, `K23 L2 L3 val`).

**`validate_wiring.py` signale un nœud "orphelin" alors que c'est
volontaire** (ex: une pin de test non reliée) : c'est un avertissement de
cohérence, pas une règle SPICE absolue — dans ce cas de figure précis,
reliez tout de même la pin à un nœud existant (même une résistance de
forte valeur vers la masse) pour éviter un flottement numérique qui
ralentit ou empêche la convergence.

**Le fichier `.wav` généré est silencieux ou saturé** : vérifiez que
`simulation.export_wav_signal` pointe vers un signal réellement
différentiel (ex: `v_ear`, pas directement `v(s1)`), et que la simulation
tourne assez longtemps (`tran_stop`) pour capturer plusieurs périodes du
signal.

## Glossaire

- **Denshi Block** : terme désignant, dans ce projet, un bloc de
  composant enfichable — qu'il soit d'origine (page du manuel) ou créé par
  la communauté.
- **Subcircuit (`.subckt`)** : construction SPICE qui encapsule un
  ensemble de composants derrière une interface de pins, réutilisable par
  instanciation (`X...`).
- **DRC (Design Rule Check)** : ici, une vérification purement
  topologique du câblage (pins connectées, contraintes respectées) —
  distincte d'une simulation électrique réelle.
- **Analyse transitoire (`.tran`)** : simulation de l'évolution du circuit
  dans le temps, par opposition à une analyse en régime permanent.

## Arborescence complète

```
ex150-ngspice/
├── README.md                 # ce fichier
├── LICENSE                   # MIT (code) + disclaimer marque
├── CONTRIBUTING.md           # comment proposer une page ou un Denshi Block
├── requirements.txt          # dépendances Python (numpy, scipy)
├── .gitignore
├── scans/
│   └── README.md             # politique sur les scans du manuel
├── lib/                      # blocs "hardware", en subcircuits SPICE
│   ├── passifs.lib
│   ├── actifs.lib
│   ├── transducteurs.lib
│   └── community/            # blocs proposés par la communauté
├── catalog/
│   └── blocks.json           # métadonnées + contraintes de chaque bloc
├── schema/
│   └── block_schema.json     # JSON Schema validant catalog/blocks.json
├── netlists/                 # .cir générés (ne pas éditer à la main)
├── examples/                 # câblages JSON (montages officiels + perso)
│   └── wiring_kit087.json
├── tools/
│   ├── wiring_to_netlist.py  # JSON de câblage → .cir ngspice
│   ├── validate_wiring.py    # DRC simplifié avant simulation
│   └── cir2wav.py            # signal simulé → .wav
├── out/                      # résultats générés (non versionné)
└── .github/workflows/ci.yml  # simule tout le dépôt à chaque push
```

## Tableau de chasse

| No. | Titre                            | Simu | Mesures conformes au manuel | Audio |
|-----|-----------------------------------|------|------------------------------|-------|
| 87  | Générateur à courant alternatif   | ✅   | ✅ ~970 Hz (manuel: audible)  | ✅    |
| …   | (à scanner / à simuler)           | ⬜   | ⬜                            | ⬜    |

## Feuille de route

- [ ] Couvrir davantage de pages du manuel (au fil des scans disponibles)
- [ ] Éditeur graphique (glisser-déposer) générant directement le câblage
      JSON, sur le modèle d'une platine virtuelle
- [ ] Bibliothèque `capteurs.lib` complète (LDR déjà présente, à étendre)
- [ ] Génération automatique du tableau de chasse depuis les résultats CI
