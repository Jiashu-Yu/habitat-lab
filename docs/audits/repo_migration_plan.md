# HSSD Audit Tool Repo Migration Plan

This plan moves reusable static audit scripts and compact audit snapshots from the standalone `ovon_hssd_audit/` workspace into the git-managed HSSD/Habitat repo at `hssd/habitat-lab`.

No Habitat simulation, rendering, training, dataset edits, or source-training/evaluation edits are required.

## Target Repo

- Repo root: `hssd/habitat-lab`
- Python tools: `tools/hssd_audit/`
- Future viewpoint tools placeholder: `tools/hssd_viewpoint/README.md`
- Audit documentation/snapshots: `docs/audits/`
- Generated run outputs: `outputs/` and ignored by `.gitignore`

## Files To Migrate

### Python Tools To `tools/hssd_audit/`

These are reusable, static/read-only scripts and should be committed:

| source | target | why migrate |
| --- | --- | --- |
| `ovon_hssd_audit/scripts/hssd_dataset_stats.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_dataset_stats.py` | lightweight ObjectNav dataset stats without Habitat imports |
| `ovon_hssd_audit/scripts/hssd_episode_goal_integrity.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_episode_goal_integrity.py` | verifies episode -> goal key -> goal list -> view_points integrity |
| `ovon_hssd_audit/scripts/hssd_one_viewpoint_goals.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_one_viewpoint_goals.py` | finds exactly-one-viewpoint goals |
| `ovon_hssd_audit/scripts/hssd_one_viewpoint_object_sanity.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_one_viewpoint_object_sanity.py` | static object/label sanity check for one-viewpoint goals |
| `ovon_hssd_audit/scripts/hssd_generated_dataset_candidates.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_generated_dataset_candidates.py` | discovers generated/modified ObjectNav dataset candidates |
| `ovon_hssd_audit/scripts/hssd_category_expansion_inventory.py` | `hssd/habitat-lab/tools/hssd_audit/hssd_category_expansion_inventory.py` | inventories HSSD semantic categories for target expansion |
| `ovon_hssd_audit/scripts/find_visibility_and_eval_code.py` | `hssd/habitat-lab/tools/hssd_audit/find_visibility_and_eval_code.py` | static keyword search for visibility/evaluation/VLM code |

The migration script rewrites repo-local defaults in copied Python files:

- `hssd/habitat-lab/data/datasets/objectnav/hssd-hab` -> `data/datasets/objectnav/hssd-hab`
- `hssd/habitat-lab/data/scene_datasets/hssd-hab` -> `data/scene_datasets/hssd-hab`
- `ovon_hssd_audit/outputs/...` -> `outputs/...`

### Viewpoint Tool Placeholder

`hssd/habitat-lab/tools/hssd_viewpoint/README.md` is added so git preserves the target directory before fixed-camera viewpoint generation scripts are implemented.

### Audit Snapshots To `docs/audits/`

These are small or moderate static audit snapshots that are useful as baseline documentation:

| source | target | note |
| --- | --- | --- |
| `ovon_hssd_audit/outputs/hssd_dataset_stats.json` | `hssd/habitat-lab/docs/audits/hssd_dataset_stats.json` | native sampled/full dataset stats snapshot |
| `ovon_hssd_audit/outputs/hssd_episode_goal_integrity.json` | `hssd/habitat-lab/docs/audits/hssd_episode_goal_integrity.json` | machine-readable integrity result |
| `ovon_hssd_audit/outputs/hssd_episode_goal_integrity.md` | `hssd/habitat-lab/docs/audits/hssd_episode_goal_integrity.md` | beginner-readable integrity report |
| `ovon_hssd_audit/outputs/hssd_one_viewpoint_goals.json` | `hssd/habitat-lab/docs/audits/hssd_one_viewpoint_goals.json` | machine-readable one-viewpoint goal list |
| `ovon_hssd_audit/outputs/hssd_one_viewpoint_goals.md` | `hssd/habitat-lab/docs/audits/hssd_one_viewpoint_goals.md` | readable one-viewpoint goal report |
| `ovon_hssd_audit/outputs/hssd_one_viewpoint_object_sanity.json` | `hssd/habitat-lab/docs/audits/hssd_one_viewpoint_object_sanity.json` | object metadata sanity snapshot |
| `ovon_hssd_audit/outputs/hssd_one_viewpoint_object_sanity.md` | `hssd/habitat-lab/docs/audits/hssd_one_viewpoint_object_sanity.md` | readable object sanity report |
| `ovon_hssd_audit/outputs/hssd_generated_dataset_candidates.json` | `hssd/habitat-lab/docs/audits/hssd_generated_dataset_candidates.json` | generated/modified dataset candidate index |
| `ovon_hssd_audit/outputs/hssd_generated_dataset_candidates.md` | `hssd/habitat-lab/docs/audits/hssd_generated_dataset_candidates.md` | readable candidate report |
| `ovon_hssd_audit/outputs/hssd_category_expansion_inventory.json` | `hssd/habitat-lab/docs/audits/hssd_category_expansion_inventory.json` | machine-readable category expansion inventory |
| `ovon_hssd_audit/outputs/hssd_category_expansion_inventory.md` | `hssd/habitat-lab/docs/audits/hssd_category_expansion_inventory.md` | readable category expansion report |

### Mentioned But Not Found Locally

These names were mentioned in the request but were not found under `ovon_hssd_audit/scripts/` or `ovon_hssd_audit/outputs/` during this pass, so they are not migrated:

- `hssd_one_viewpoint_object_ids.json`
- `hssd_one_viewpoint_goal_sanity.py`
- `hssd_one_viewpoint_goal_sanity.json`
- `hssd_one_viewpoint_goal_sanity.md`

If they exist elsewhere, add them explicitly to the copy script after confirming they are small, static, and useful.

## Files Not To Migrate

Do not commit debug images, rendered videos, large generated outputs, logs, caches, or training artifacts:

- `outputs/`
- `*_debug/`
- `*.png`, `*.jpg`, `*.jpeg`
- `*.mp4`, `*.avi`, `*.mov`
- `*.log`
- `__pycache__/`, `*.pyc`

## PowerShell Migration Command

From the workspace root:

```powershell
powershell -ExecutionPolicy Bypass -File ovon_hssd_audit/outputs/organize_hssd_tools_for_repo.ps1
```

Dry run:

```powershell
powershell -ExecutionPolicy Bypass -File ovon_hssd_audit/outputs/organize_hssd_tools_for_repo.ps1 -DryRun
```

With explicit paths:

```powershell
powershell -ExecutionPolicy Bypass -File ovon_hssd_audit/outputs/organize_hssd_tools_for_repo.ps1 `
  -WorkspaceRoot D:\workspace\NYU\workspace `
  -RepoRoot D:\workspace\NYU\workspace\hssd\habitat-lab
```

## `.gitignore` Patch

The repo already ignored `outputs/`, `*.log`, `__pycache__/`, and `*.py[cod]`. This pass added the missing generated media/debug patterns and the explicit `*.pyc` rule requested for clarity:

```diff
 # Byte-compiled / optimized / DLL files
 __pycache__/
 *.py[cod]
+*.pyc
+
 # Hydra
 outputs/
+
+# HSSD audit/generated artifacts
+*_debug/
+*.png
+*.jpg
+*.jpeg
+*.mp4
+*.avi
+*.mov
```

The migration script also checks the full requested ignore list idempotently:

- `outputs/`
- `*_debug/`
- `*.png`
- `*.jpg`
- `*.jpeg`
- `*.mp4`
- `*.avi`
- `*.mov`
- `*.log`
- `__pycache__/`
- `*.pyc`

## Server Usage After `git pull`

From `hssd/habitat-lab` on the server:

```bash
python tools/hssd_audit/hssd_episode_goal_integrity.py
python tools/hssd_audit/hssd_one_viewpoint_goals.py
python tools/hssd_audit/hssd_one_viewpoint_object_sanity.py
python tools/hssd_audit/hssd_generated_dataset_candidates.py --root .
python tools/hssd_audit/hssd_category_expansion_inventory.py
```

Default outputs should go to `outputs/`, which is ignored by git.

## Sanity Checks Before Commit

Because this Windows sandbox sees the repo as a different owner, `git status` may require:

```bash
git config --global --add safe.directory D:/workspace/NYU/workspace/hssd/habitat-lab
```

Then check:

```bash
git -C hssd/habitat-lab status --short
git -C hssd/habitat-lab diff -- .gitignore tools/hssd_audit docs/audits
```
