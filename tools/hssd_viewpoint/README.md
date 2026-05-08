# HSSD Viewpoint Tools

This directory contains prototype and future production tools for HSSD ObjectNav viewpoint generation and quality audits.

Current tool:

- `hssd_fixed_camera_viewpoint_prototype.py`: prototype fixed-camera viewpoint visibility audit/generator.
- `inspect_hssd_semantic_mapping.py`: narrow diagnostic for mapping one `scene_instance.json` object to a Habitat-Sim rigid object handle and optional sentinel render check.
- `run_fixed_camera_viewpoint_prototype.sh`: Linux wrapper with `dry`, `small`, and `full` modes.

Output JSON schema landmarks:

- top-level result key: `object_results`
- per-object metadata key: `object`
- per-object candidate list key: `candidate_results`
- scene initialization/load failures: `failed_scenes`
- per-object processing failures: `failed_objects`
- candidate-level failures: `candidate_results[*].candidate_error`

Non-dry-run results also include semantic diagnostics. Each object can include `semantic_scene_diagnostics`, `semantic_mapping`, and `candidate_semantic_id_diagnostics`; each rendered candidate can include `semantic_observation_diagnostics`, `semantic_mapping_status`, `rigid_object_handle`, `sentinel_semantic_id`, `sentinel_visible_pixels`, `sentinel_bbox`, `sentinel_image_fraction`, `heuristic_candidate_semantic_ids`, `heuristic_best_semantic_id`, `heuristic_visible_pixels`, `pixel_counts_by_semantic_id`, `best_semantic_id`, and `visible_pixels`.

Final target-mask construction uses an instance-level sentinel semantic ID assigned to the matched HSSD rigid object. The older non-zero heuristic semantic IDs are retained only as diagnostics under `heuristic_*` fields. Semantic ID `0` remains filtered from heuristic diagnostics because HSSD semantic frames can use it for background/void/unlabeled pixels.

Runtime outputs should go under repo-root `outputs/`, which is ignored by git. Do not commit rendered media, debug images, generated viewpoint shards, or logs.
