# HSSD Viewpoint Tools

This directory contains prototype and future production tools for HSSD ObjectNav viewpoint generation and quality audits.

Current tool:

- `hssd_fixed_camera_viewpoint_prototype.py`: prototype fixed-camera viewpoint visibility audit/generator.
- `run_fixed_camera_viewpoint_prototype.sh`: Linux wrapper with `dry`, `small`, and `full` modes.

Output JSON schema landmarks:

- top-level result key: `object_results`
- per-object metadata key: `object`
- per-object candidate list key: `candidate_results`
- scene initialization/load failures: `failed_scenes`
- per-object processing failures: `failed_objects`
- candidate-level failures: `candidate_results[*].candidate_error`

Non-dry-run results also include semantic diagnostics. Each object can include `semantic_scene_diagnostics` and `candidate_semantic_id_diagnostics`; each rendered candidate can include `semantic_observation_diagnostics`, `raw_candidate_semantic_ids`, `candidate_semantic_ids`, `invalid_candidate_semantic_ids_removed`, `pixel_counts_by_semantic_id`, `best_semantic_id`, and `visible_pixels`.

Target-mask construction filters semantic ID `0` because HSSD semantic frames can use it for background/void/unlabeled pixels. Non-zero heuristic IDs are still provisional until the HSSD rigid-object/sentinel mapping is implemented.

Runtime outputs should go under repo-root `outputs/`, which is ignored by git. Do not commit rendered media, debug images, generated viewpoint shards, or logs.
