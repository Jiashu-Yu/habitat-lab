# Maxwell Migration Runbook

Date: 2026-05-19

This runbook moves the fixed-camera HSSD ObjectNav workflow from AutoDL to
NYU Maxwell. The working model remains:

```text
local machine: edit code/docs -> commit/push
maxwell: pull latest code -> run GPU jobs -> keep generated data off git
```

## 1. Maxwell Starting Point

User workspace:

```text
/local_data/jy5946/
  checkpoints/
  datasets/
  logs/
  miniconda3/
  workspace/
```

Observed GPU host:

```text
8x NVIDIA RTX 6000 Ada, 49140 MiB each
driver 595.58.03, CUDA 13.2
```

Before launching jobs, always check current load:

```bash
nvidia-smi
top
```

Use a single relatively free GPU for Stage 1-4 probes. Do not launch multi-GPU
render workers while other users occupy most cards.

## 2. Recommended Directory Layout

```bash
export USER_ROOT=/local_data/jy5946
export WORK=$USER_ROOT/workspace/hssd
export DATA_ROOT=$USER_ROOT/datasets/habitat
export OUTPUT_ROOT=$USER_ROOT/datasets/hssd_fixedcam_outputs
export LOG_ROOT=$USER_ROOT/logs/hssd_fixedcam

export VIEWPOINT_REPO=$WORK/habitat-lab-viewpoint
export RENDER_REPO=$WORK/ObjectNavigationRendering_fixedcam

mkdir -p "$WORK" "$DATA_ROOT" "$OUTPUT_ROOT" "$LOG_ROOT"
```

If Jing's shared data is readable, we can temporarily point `DATA_ROOT` at her
copy to avoid re-downloading:

```bash
ls /local_data/jz6676/habitat/scene_datasets/hssd-hab
ls /local_data/jz6676/habitat/datasets/objectnav/hssd-hab/train/content
```

If those paths are not readable, keep `DATA_ROOT=/local_data/jy5946/datasets/habitat`
and download/copy the data there.

## 3. Clone / Pull Repositories

Stable current branches:

```bash
cd "$WORK"

git clone -b hssd-objectnav-workflow \
  https://github.com/Jiashu-Yu/habitat-lab.git \
  habitat-lab-viewpoint

git clone -b hssd-fixedcam-workflow \
  https://github.com/jingz6676/ObjectNavigationRendering.git \
  ObjectNavigationRendering_fixedcam
```

Pull updates after local push:

```bash
cd "$VIEWPOINT_REPO"
git pull --ff-only origin hssd-objectnav-workflow

cd "$RENDER_REPO"
git pull --ff-only origin hssd-fixedcam-workflow
```

Jing's WIP refactor branch, for inspection or testing only:

```bash
cd "$RENDER_REPO"
git fetch origin refactor/repo-cleanup-and-dual-tier
git switch -c refactor/repo-cleanup-and-dual-tier \
  --track origin/refactor/repo-cleanup-and-dual-tier
```

Do this only in a clean worktree or a separate clone, because the branch
renames/deletes many top-level files.

## 4. Python Environment

If an environment already exists, prefer reusing it:

```bash
conda env list
conda activate vagen-habitat
python -c "import habitat_sim; print('habitat_sim ok')"
```

If not:

```bash
conda create -n vagen-habitat python=3.9 -y
conda activate vagen-habitat

conda install -c conda-forge -c aihabitat habitat-sim=0.3.3 withbullet headless -y

pip install -r "$RENDER_REPO/requirements.txt"
```

Then install Habitat-Lab if needed:

```bash
git clone --branch v0.3.3 https://github.com/facebookresearch/habitat-lab.git \
  "$WORK/habitat-lab-v0.3.3"
pip install -e "$WORK/habitat-lab-v0.3.3/habitat-lab"
pip install -e "$WORK/habitat-lab-v0.3.3/habitat-baselines"
```

Sanity check:

```bash
python - <<'PY'
import habitat_sim
print("habitat_sim import ok")
PY
```

### Current WIP requirements workaround

Jing's `refactor/repo-cleanup-and-dual-tier` commit `04e3f85` pins:

```text
numpy==1.26.4
opencv-python-headless==4.13.0.92
```

On Python 3.9, `opencv-python-headless==4.13.0.92` requires `numpy>=2`, so
`pip install -r requirements.txt` fails. Until the branch is updated, install
the runtime dependencies manually with an OpenCV version compatible with
`numpy==1.26.4`:

```bash
pip install \
  numpy==1.26.4 \
  numpy-quaternion==2023.0.4 \
  opencv-python-headless==4.11.0.86 \
  pillow==10.4.0 \
  pyarrow==21.0.0 \
  h5py==3.14.0 \
  av==15.1.0 \
  decord==0.6.0 \
  pandas \
  tqdm \
  pyyaml
```

Then check:

```bash
python - <<'PY'
import numpy, pandas, pyarrow, av, cv2, h5py, decord
print("core deps ok")
print("numpy", numpy.__version__)
print("cv2", cv2.__version__)
PY
```

## 5. Data Requirements

The pipeline expects:

```text
$DATA_ROOT/
  scene_datasets/
    hssd-hab/
      hssd-hab.scene_dataset_config.json
      scenes/
      metadata/
      objects/
      stages/
  datasets/
    objectnav/
      hssd-hab/
        train/content/*.json.gz
        val/content/*.json.gz
```

The official HSSD ObjectNav v0.2.5 `train/content` and `val/content` are needed
by Jing's dual-tier label resolver for the NavObj6 white-list. HSSD scenes are
needed by Stage 1, Stage 3 render-missing, Stage 4 start sampling, and Stage 5
rendering.

## 6. Current Branch Strategy

As of commit `04e3f85`, Jing's
`refactor/repo-cleanup-and-dual-tier` branch is useful but still WIP.

Important changes:

- repo layout becomes `viewpoints/`, `episodes/`, `render/`, `postprocess/`,
  `lib/`, `ops/`;
- Stage 1/3 are parameterized for `--image-size 256`;
- Stage 1 default sampling moves to 360 candidates with radii
  `0.15 0.3 0.45 0.6 0.75 0.85`;
- Stage 4 adds dual-tier labels:
  `navobj6_*` and `open_vocab`;
- `README_FIXED_CAMERA_HSSD.md` is deleted and content is folded into
  `README.md` + `docs/fixed-camera-hssd-workflow.md`.

Known WIP mismatch in `04e3f85`:

```text
run_full_pipeline.sh calls:
  episodes/export_selection_to_hssd.py --output-data-root ... --scene-dataset-config ...

but the parser currently defines:
  --data-root
  no --scene-dataset-config
```

Before running the wrapper, either wait for Jing's next push or call Stage 4
manually with `--data-root`.

## 7. Minimal Server Smoke Plan

Once code and data are ready, run a small probe before any full run:

```bash
cd "$RENDER_REPO"
conda activate vagen-habitat

export DATA_ROOT=/local_data/jy5946/datasets/habitat
export GPU=0
export RUN_TAG=maxwell_smoke_102344022
export OUT=$OUTPUT_ROOT/$RUN_TAG

CUDA_VISIBLE_DEVICES=$GPU python viewpoints/hssd_fixed_camera_viewpoint_prototype.py \
  --scene-root "$DATA_ROOT/scene_datasets/hssd-hab" \
  --scene-dataset-config "$DATA_ROOT/scene_datasets/hssd-hab/hssd-hab.scene_dataset_config.json" \
  --inventory-json "$VIEWPOINT_REPO/docs/audits/hssd_category_expansion_inventory.json" \
  --output-dir "$OUT/prototype" \
  --categories bed chair couch potted_plant toilet tv \
  --scene-ids 102344022 \
  --max-scenes 0 \
  --max-objects-per-category 2 \
  --samples-per-object 60 \
  --candidate-radii 0.15 0.3 0.45 0.6 0.75 0.85 \
  --image-size 256 \
  --seed 13 \
  --gpu-device-id 0 \
  2>&1 | tee "$LOG_ROOT/${RUN_TAG}_stage1.log"
```

Then selection:

```bash
python viewpoints/select_fixed_camera_viewpoints.py \
  --input-json "$OUT/prototype/hssd_fixed_camera_viewpoint_prototype.json" \
  --output-dir "$OUT/selection_v10" \
  --bbox-metric max_axis \
  --connector and \
  --threshold-profile low_small \
  --low-small-categories toilet vase potted_plant \
  --bbox-per-cat bed=0.10 couch=0.10 chair=0.05 tv=0.05 potted_plant=0.02 toilet=0.02 \
  --vis-per-cat bed=0.10 couch=0.05 chair=0.015 tv=0.05 potted_plant=0.005 toilet=0.01 \
  --min-axis 0.10 \
  --max-min-axis-per-cat bed=0.92 couch=0.85 \
  --max-distance 0.89 \
  --max-accepted-image-fraction 1.0 \
  --max-accepted-image-fraction-per-cat bed=0.56 \
  --reject-flags full_frame_sentinel_mask tiny_sentinel_mask \
  --min-viewpoints-per-object 1 \
  --top-k 8
```

Stage 4 dry-run with dual-tier labels:

```bash
python episodes/export_selection_to_hssd.py \
  --selection-json "$OUT/selection_v10/fixed_camera_viewpoint_selection.json" \
  --data-root "$DATA_ROOT" \
  --split fixedcam_maxwell_smoke \
  --max-scenes 1 \
  --max-objects-per-category 2 \
  --episodes-per-object 1 \
  --dry-run
```

If this prints selected objects and does not warn about missing v0.2.5/fpmodels,
the Maxwell environment is ready for a real small render.

### Smoke result, 2026-05-19

Environment and no/low-cost checks passed:

```text
habitat_sim: 0.3.3
habitat: import ok
numpy: 1.26.4
opencv-python-headless: 4.11.0
all refactor entry points Stage 1-7: --help ok
HSSD scenes: 168
official objectnav train content: 122 scene files
official objectnav val content: 42 scene files
dual-tier resolver index: 874 (scene, category) entries
fpmodels rows: 20451
```

GPU smoke on `102344022`, `--image-size 256`, `--samples-per-object 12`,
`--max-objects-per-category 1`, GPU 4:

```text
Stage 1:
  objects_processed: 6
  failed_scene_count: 0
  failed_object_count: 0
  candidate_error_count: 0
  objects_with_any_visible_pixels: 6
  rendered_candidates: 67
  candidates_with_visible_pixels: 54

Stage 2:
  candidate_status_counts: accepted=54, rejected=18
  object_status_counts: pass=6
  all six categories passed: bed, chair, couch, potted_plant, toilet, tv

Stage 4 dry-run:
  dual-tier resolver loaded
  selected 5 objects with --max-objects-per-category 1 dry-run cap
```

Manual resolver inspection on the Stage 2 objects confirmed the intended label
separation:

```text
Flat TV:
  category=tv, canonical=tv, navobj6=tv, source=v025_listed

Toilette/toilette Casual:
  category=toilet, canonical=toilet, navobj6=toilet,
  source=condensed_room_ok:bathroom

Torino 2 seater:
  category=couch, canonical=couch, navobj6=couch, source=v025_listed

White Swivel Desk Chair:
  category=chair, canonical=seat, navobj6=chair, source=v025_listed,
  wnsynset=swivel_chair.n.01

Full Saddle Back Upholstered Bed:
  category=bed, canonical=bed, navobj6=bed, source=v025_listed

Mini potted poinsettia:
  category=potted_plant, canonical=plant, navobj6=potted_plant,
  source=v025_listed
```

This validates the important research distinction:

```text
selection category != canonical HSSD condensed category != strict navobj6 label
```

The Maxwell environment is ready for the next small probe after Jing's WIP
branch is updated.

## 8. GPU Etiquette For First Runs

For first probes:

```bash
export CUDA_VISIBLE_DEVICES=0
```

Inside scripts still pass `--gpu-device-id 0`, because after
`CUDA_VISIBLE_DEVICES=0` Habitat sees the chosen physical GPU as local device
0.

For multi-worker rendering, explicitly edit the launcher GPU list after checking
`nvidia-smi`. On a shared Maxwell node, avoid taking all 8 GPUs unless the node
is idle and this has been coordinated.
