# HSSD Viewpoint Tools

This directory contains prototype and future production tools for HSSD ObjectNav viewpoint generation and quality audits.

For the full research logic and end-to-end pipeline from HSSD metadata to
fixed-camera viewpoints, ObjectNav split export, MP4/Parquet rendering, and
review packs, see:

```text
docs/audits/hssd_fixed_camera_objectnav_end_to_end_handoff.md
```

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

Non-dry-run results also include semantic diagnostics. Each object can include `semantic_scene_diagnostics`, `semantic_mapping`, and `candidate_semantic_id_diagnostics`; each rendered candidate can include `semantic_observation_diagnostics`, `semantic_mapping_status`, `rigid_object_handle`, `sentinel_semantic_id`, `sentinel_visible_pixels`, `sentinel_bbox`, `sentinel_bbox_area_fraction`, `sentinel_image_fraction`, `sentinel_total_pixels`, `sentinel_image_shape`, `sentinel_mask_quality_flags`, `heuristic_candidate_semantic_ids`, `heuristic_best_semantic_id`, `heuristic_visible_pixels`, `pixel_counts_by_semantic_id`, `best_semantic_id`, and `visible_pixels`.

Final target-mask construction uses an instance-level sentinel semantic ID assigned to the matched HSSD rigid object. The older non-zero heuristic semantic IDs are retained only as diagnostics under `heuristic_*` fields. Semantic ID `0` remains filtered from heuristic diagnostics because HSSD semantic frames can use it for background/void/unlabeled pixels.

When `--debug-images` is enabled, each saved candidate writes four images: RGB, binary sentinel mask, RGB+mask overlay, and an annotated review image. The review image includes target category, scene, instance, candidate, rigid handle, visible pixel count, quality flags, and brightened RGB/overlay panels for dark HSSD assets. Large/full-frame mask flags are diagnostics for camera/object geometry and candidate quality; they do not automatically reject a candidate.

Use `analyze_fixed_camera_viewpoint_output.py` to summarize a completed JSON run without importing Habitat:

```bash
python tools/hssd_viewpoint/analyze_fixed_camera_viewpoint_output.py \
  --input-json outputs/hssd_fixed_camera_viewpoint_prototype/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_analysis
```

The analyzer understands the current schema, `object_results[*].object` plus `object_results[*].candidate_results`, and writes JSON/CSV/Markdown tables for sentinel-positive, heuristic-only, and quality-flagged candidates. When review images are available, the Markdown tables link to review images first and overlay images second.

Use `select_fixed_camera_viewpoints.py` after manual review has established quality rules:

```bash
python tools/hssd_viewpoint/select_fixed_camera_viewpoints.py \
  --input-json outputs/hssd_fixed_camera_viewpoint_prototype/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/hssd_fixed_camera_viewpoint_selection \
  --min-viewpoints-per-object 3
```

The selector is also static. It classifies candidates as `accepted`, `review`, or `rejected`; full-frame, near-full-frame, and tiny masks are rejected by default, while very-large masks require review by default. It writes per-category and per-object feasibility summaries plus prototype `view_points` records for accepted candidates.

For targeted retry runs, the prototype supports exact filters:

```bash
python tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py \
  --categories cabinet fridge \
  --scene-ids 102343992 \
  --instance-indices 27 140 \
  --max-scenes 0 \
  --max-objects-per-category 0 \
  --samples-per-object 32 \
  --candidate-radii 1.25 1.5 1.75 2.0 2.5 3.0 \
  --debug-images
```

Runtime outputs should go under repo-root `outputs/`, which is ignored by git. Do not commit rendered media, debug images, generated viewpoint shards, or logs.
