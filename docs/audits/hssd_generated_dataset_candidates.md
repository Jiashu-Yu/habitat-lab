# Generated/Modified HSSD Dataset Candidate Discovery

Scan root: `.`
Native HSSD root: `hssd\habitat-lab\data\datasets\objectnav\hssd-hab`

This is a static discovery pass. It only reads local JSON/JSON.GZ files and looks for Habitat ObjectNav-like `episodes` and `goals_by_category` structures. It does not run Habitat simulation, render, train, or modify dataset/source files.

Scanned JSON/JSON.GZ files: **19794**
Dataset-like files found: **555**

## Decision

- Clear generated dataset: `None`
- Decision: Multiple non-native HSSD/ObjectNav-like candidates found; do not auto-audit all.

If multiple non-native candidates are present, this script intentionally stops at discovery so a human can choose the intended dataset.

## Candidates

| path | files | has episodes | has goals_by_category | looks HSSD/ObjectNav | differs native | splits | episodes | goals | viewpoints | HSSD categories | path hints | malformed-like categories |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v1 | 164 | True | True | True | True | `{"train": 122, "val": 42}` | 121800 | 5504 | 600956 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v1-smoke | 42 | True | True | True | True | `{"val": 42}` | 1248 | 1723 | 190241 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug | 1 | True | True | True | True | `{"train": 1}` | 1000 | 45 | 9790 | `["bed", "chair", "couch", "potted_plant", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug2 | 1 | True | True | True | True | `{"train": 1}` | 1000 | 45 | 9790 | `["bed", "chair", "couch", "potted_plant", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug3 | 1 | True | True | True | True | `{"train": 1}` | 1000 | 45 | 9634 | `["bed", "chair", "couch", "potted_plant", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug4 | 1 | True | True | True | True | `{"train": 1}` | 1000 | 45 | 9608 | `["bed", "chair", "couch", "potted_plant", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-pilot | 3 | True | True | True | True | `{"train": 3}` | 2992 | 83 | 12913 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-smoke | 1 | True | True | True | True | `{"val": 1}` | 30 | 48 | 14696 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd_hab | 164 | True | True | True | True | `{"train": 122, "val": 42}` | 121800 | 5504 | 1317069 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `[]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab | 164 | True | True | True | False | `{"train": 122, "val": 42}` | 121800 | 5504 | 1317069 | `["bed", "chair", "couch", "potted_plant", "toilet", "tv"]` | `[]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v1-smoke\val | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v1\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v1\val | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug2\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug3\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug4\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-debug\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-pilot\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab-tiltfree-v2-smoke\val | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `["tilt"]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `[]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd-hab\val | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `[]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd_hab\train | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `[]` | `[]` |
| hssd\habitat-lab\data\datasets\objectnav\hssd_hab\val | 1 | True | False | False | True | `{}` | 0 | 0 | 0 | `[]` | `[]` | `[]` |

Machine-readable details: `ovon_hssd_audit/outputs/hssd_generated_dataset_candidates.json`
