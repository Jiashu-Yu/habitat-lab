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

Non-dry-run results also include semantic diagnostics. Each object can include `semantic_scene_diagnostics`; each rendered candidate can include `semantic_observation_diagnostics`, `candidate_semantic_ids`, `pixel_counts_by_semantic_id`, `best_semantic_id`, and `visible_pixels`.

Runtime outputs should go under repo-root `outputs/`, which is ignored by git. Do not commit rendered media, debug images, generated viewpoint shards, or logs.
