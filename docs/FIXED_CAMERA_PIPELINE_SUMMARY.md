# Fixed-Camera HSSD ObjectNav — Pipeline Summary & Iteration Log

This document summarizes the full data-collection + training pipeline for the
fixed-camera HSSD ObjectNav setup, the bugs we fixed in this iteration, the
final filter configuration, and known limitations / scaling considerations.

It is intended as a hand-off so a teammate can continue improving the pipeline
or scale it to more scenes / open-vocabulary categories.

---

## 1. Pipeline at a glance

```
HSSD scene + inventory
        │
   Stage 1  hssd_fixed_camera_viewpoint_prototype.py
   ───────  per (scene, object): sample 160 candidate poses around the OBB
            surface, render at 0° pitch, dump metrics (~50k candidates total).
        │   output: outputs/<RUN>/hssd_fixed_camera_viewpoint_prototype.json
        ▼
   Stage 2  select_fixed_camera_viewpoints.py
   ───────  classify each candidate accepted / review / rejected based on
            vis, bbox, fill, min_axis, distance, mask flags. Rank top-K
            accepted per object → fail if 0 accepted.
        │   output: outputs/<RUN>/selection_<CONFIG>/
        ▼
   Stage 3  build_fixed_camera_visual_qa_pack.py
   ───────  for QA only: re-render each accepted/review candidate into a 2×3
            composite (RGB | Overlay | Mask / BEV | Text | Depth) with FoV
            cone + legend. Optional via --render-missing.
        │   output: outputs/<RUN>/review_<CONFIG>/
        ▼
   Stage 4  export_fixed_camera_selection_to_hssd_episodes.py
   ───────  convert accepted viewpoints into HSSD ObjectNav episode JSONs
            (objectnav_<scene>.json.gz). Lives in /local_data/jz6676/objnav_render/.
        │
        ▼
   Stage 5  render_objnav_mp4.py (+ render_objnav_episodes.py)
   ───────  for each episode, run GreedyGeodesicFollower from start → goal
            viewpoint, render RGB into MP4 + per-step Parquet. This is the
            actual training data for the cosmos-policy.
        │   output: videos/primary/scene_*.mp4 + data/worker_XXXX.parquet
        ▼
   Stage 6  build_fixed_camera_mp4_review_pack.py
   ───────  sanity sample MP4s into a review pack.
        ▼
   Stage 7  summarize_fixed_camera_mp4_outputs.py
   ───────  aggregate statistics (per-scene success/failure modes, episode
            counts, parquet schema sanity, etc.).
```

Concretely, **Stages 1-3 live in this repo (`habitat-lab-viewpoint`)**, Stages
4-7 in `/local_data/jz6676/objnav_render/`.

---

## 2. Bug fixes & improvements in this iteration

### 2.1 yaw bug (CRITICAL)
- **File:** `tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py:1559-1576`
- **Symptom:** `yaw_to_face_target` rotated the camera in the **wrong direction**
  around the Y axis, so the rendered RGB showed something other than the target
  for any candidate where `view_dir.x ≠ 0`. Targets ~22° off-axis ended up
  outside the 79° FoV.
- **Cause:** Derivation of `yaw = atan2(view_dir.x, -view_dir.z)` had a sign
  flip on `view_dir.x`. The correct form is `atan2(-view_dir.x, -view_dir.z)`.
- **Impact on pass rate (pilot 10 scenes):**

  | category | v1 buggy | v2 yawfix | Δ |
  |---|---|---|---|
  | bed | 91.4% | 94.3% | +2.9 |
  | chair | 68.0% | 86.0% | **+18** |
  | couch | 81.6% | 92.1% | +10.5 |
  | plant | 68.0% | 79.0% | +11 |
  | tv | 62.5% | 83.3% | **+20.8** |
  | toilet | 61.3% | 93.5% | **+32.2** |
  | **TOTAL** | **71.0%** | **86.0%** | **+15** |

- Same fix applied to Stage 3's `_render_face_quat` in
  `build_fixed_camera_visual_qa_pack.py:1288`.

### 2.2 distance_to_bbox fallback for missing-metadata chairs
- **File:** `tools/hssd_viewpoint/select_fixed_camera_viewpoints.py` (top of file
  + `iter_rows`)
- **Symptom:** 33 chair templates in HSSD lack `metadata_dims`, so Stage 1
  cannot synthesize their `object_bbox_static_approx`. Stage 2's distance gate
  falls back to `distance_to_object` (OBB **centre**), which is much larger
  than `distance_to_bbox` (OBB **surface**) for big chairs → 0.9m cap over-rejects.
- **Fix:** New constant `HALF_XZ_DIAG_BY_CAT_DEFAULT` (computed from pilot
  medians) is used to synthesize an estimated `distance_to_bbox_estimated`
  field whenever `distance_to_bbox is None`. Added to `DISTANCE_KEYS` between
  `distance_to_bbox` and `distance_to_object`.
- **Effect:** chair 92 → 95 pass (+3 / +960 VPs) without any Stage 1 rerun.

### 2.3 `near_full_frame_bbox` was over-rejecting legit canopy / large objects
- **File:** `select_fixed_camera_viewpoints.py:24-29`
- **Symptom:** Canopy beds + 4-poster beds + Taro (big-leaf plant) close-ups got
  rejected because their **OBB projection** filled the frame, even though the
  rendered mask was a healthy ~50-60% of vis_ratio with clear geometry.
- **Fix:** Remove `near_full_frame_bbox` from `--reject-flags` (keep only
  `full_frame_sentinel_mask` + `tiny_sentinel_mask`). Recommended CLI:
  `--reject-flags full_frame_sentinel_mask tiny_sentinel_mask`.

### 2.4 per-category `max_min_axis` + `max_accepted_image_fraction`
- **File:** `select_fixed_camera_viewpoints.py:258-, 308-, 460-`
- **Motivation:** Bunk-bed wall close-ups (`min_axis ≈ 0.96`) still got
  accepted under standard gates because their visible mask was dense and
  recognizable as "bed" by semantic but visually it's just a wood panel.
- **Fix:** Added two new CLI flags:
  - `--max-min-axis` (global) and `--max-min-axis-per-cat KEY=VAL` — rejects
    candidates whose bbox **fills both axes** simultaneously.
  - `--max-accepted-image-fraction-per-cat KEY=VAL` — pushes per-category
    extreme close-ups to review status. Recommended `bed=0.56`.
- Implementation hooked into `thresholds_for_object` (per-cat) and the existing
  fill-ratio / min-axis gate block.

### 2.5 Stage 3 skip zero-visible rejects
- **File:** `build_fixed_camera_visual_qa_pack.py:1654-`
- **Symptom:** Stage 3 was happily rendering candidates with `vis_ratio = 0` and
  `zero_visible_pixels` reject reason — the RGB came out dark/empty because the
  candidate position was often on a different floor than the target (only XZ
  planar distance is small). Useless noise in the review pack.
- **Fix:** `_render_missing_for_rows` now skips rows whose status is
  `rejected` AND reasons contain `zero_visible`.

### 2.6 Stage 3 visualisation improvements
- **2×3 composite layout** (RGB | Overlay | Mask / BEV | Text | Depth).
- **BEV overlay** with FoV cone (yellow, 79°), forward arrow (blue), look-at
  dashed line to bbox centre (red), per-bucket coloured candidate dots, and a
  legend in the top-right showing only the buckets that appear in this BEV.
- **Text panel** distinguishes `d_to_center (OBB center)` from
  `d_to_bbox (OBB surface)` so the user can immediately see why a candidate
  passed / failed the distance gate.

---

## 3. Final recommended Stage 2 config

The configuration we converged on after iterating against a 10-scene val pilot
and a 10-scene fresh train batch. Pass rate ≈ 88-89% val / ~78-82% train.

```bash
python tools/hssd_viewpoint/select_fixed_camera_viewpoints.py \
  --input-json outputs/$RUN/hssd_fixed_camera_viewpoint_prototype.json \
  --output-dir outputs/$RUN/selection_final \
  \
  --bbox-metric max_axis \
  --connector and \
  \
  --threshold-profile low_small \
  --low-small-categories toilet vase potted_plant \
  \
  --bbox-per-cat bed=0.10 couch=0.10 chair=0.05 tv=0.05 potted_plant=0.02 toilet=0.02 \
  --vis-per-cat  bed=0.10 couch=0.10 chair=0.025 tv=0.025 potted_plant=0.005 toilet=0.01 \
  \
  --min-fill-ratio 0.40 \
  --min-axis 0.10 \
  --max-min-axis-per-cat bed=0.92 \
  \
  --max-distance 0.89 \
  --max-accepted-image-fraction 1.0 \
  --max-accepted-image-fraction-per-cat bed=0.56 \
  \
  --reject-flags full_frame_sentinel_mask tiny_sentinel_mask \
  --min-viewpoints-per-object 1 \
  --top-k 8
```

**Why each knob:**

| flag | rationale |
|---|---|
| `--connector and` | OR-rescued candidates with low vis but high bbox tend to be "couch peeking from kitchen edge" — bad for policy training. |
| `--bbox-metric max_axis` | Matches V3 reshard; more permissive for elongated objects than `area`. |
| `--vis-per-cat ... chair=0.025 ... plant=0.005` | Small/distant chairs and plants legitimately have low vis; relaxing per-cat preserves them. |
| `--min-fill-ratio 0.40` | Filters "target at frame edge, mostly bg in bbox" (e.g. toilet sliver, vase corner). |
| `--min-axis 0.10` | Filters sliver bboxes (e.g. side-on TV showing only thin frame). |
| `--max-min-axis-per-cat bed=0.92` | Allows canopy / 4-poster beds (`min_axis ≈ 0.91`) while still rejecting bunk-bed wall views (`min_axis ≈ 0.96`). |
| `--max-accepted-image-fraction-per-cat bed=0.56` | Pushes bunk-bed wood-panel close-ups (`vis ≈ 0.95`) to review status. |
| `--max-distance 0.89` | Strict `< 0.9m` (matches HSSD ObjectNav `success_distance = 1.0m` modulo our radius sampling). |
| `--reject-flags ...` | Drop `near_full_frame_bbox` from defaults to admit canopy beds + Taro etc. |

---

## 4. Pipeline outputs reference

### 4.1 Pilot (val) and train batches

| Batch | Stage 1 JSON | Stage 2 selection | Stage 3 review |
|---|---|---|---|
| val pilot 10 scenes (final config) | `outputs/pilot10_v2_yawfix/hssd_fixed_camera_viewpoint_prototype.json` | `outputs/pilot10_v2_yawfix/selection_final_bed070_vis056/` | `outputs/pilot10_v2_yawfix/review_final_bed070_vis056/` |
| train 10 fresh scenes (v5 final) | `outputs/train10_v1_yawfix/hssd_fixed_camera_viewpoint_prototype.json` | `outputs/train10_v1_yawfix/selection_v5/` | (re-render after fill=0.40 + zero-visible skip) |

### 4.2 Episode video samples (manual sanity checks)

```
outputs/pilot10_v2_yawfix/episode_videos/
  bed_inst227_cand53.mp4                 # nice bedroom episode
  chair_inst269_cand136.mp4              # recliner / chair close-up (illustrates the "wall-view" issue)
outputs/train10_v1_yawfix/episode_videos/
  couch_inst407_cand152.mp4              # Mid-Century sofa close-up
```

Rendered with `/tmp/render_episode_video.py` (uses
`habitat_sim.nav.GreedyGeodesicFollower`).

---

## 5. Pass rate evolution (val pilot, AND mode)

| config | pass | total VPs | rationale |
|---|---|---|---|
| V0 (OR + area, single threshold) | ~60% | — | original |
| P1 (AND + max_axis + per-cat tiers + fill+min_axis) | 71.0% | — | P1 introduced quality gates |
| P1b (plant vis 0.010) | 71.0% | — | small-plant gate |
| v1 (yawfix re-run) | **86.0%** | 23338 | yaw bug fix dominated |
| v2 (yawfix + d≤0.9) | 88.1% | 24990 | balanced |
| v2 + d<0.9 + bboxfb + no-fill | 88.7% | 23383 | + chair fallback |
| v2 + bed_wallcap | 88.7% | 23676 | + bed close-up filter |
| **final** (bed070+vis056) | **88.4%** | **23318** | adopted for pilot |

train batch with **v5 (final + fill 0.40)**: 78.3% pass, 19016 VPs. Plant
58→48 because train scenes have far more multi-storey buildings with plants
on upper floors (XZ-only candidate sampling can't see them).

---

## 6. Known limitations

1. **Per-pitch fixed 0° camera** misses targets on shelves / upper floors.
   HSSD's official viewpoint generator uses 3 pitches (look_down, look_up,
   look_up) summed at `frame_cov_thresh = 0.05`. We're stricter on single-pitch.
2. **Fill-ratio doesn't catch foreground occlusion** outside the bbox (e.g.
   camera behind a table looking at a bed — the bed is visible above but a
   wooden table top dominates the bottom 1/3 of the frame). This would need
   depth-based foreground-pixel ratio analysis at Stage 1.
3. **`HALF_XZ_DIAG_BY_CAT_DEFAULT` is hard-coded from pilot medians.** If we
   move to a much larger training set, recompute these or wire them up via a
   per-category metadata table.
4. **Sentinel-ID semantic tagging** can miss articulated parts of large
   objects (e.g. mattress + frame as different instances). We sidestep this
   by treating the whole rigid object handle as "the target", but visible
   pixels can become 0 for very specific viewpoints.

---

## 7. Scaling considerations

### 7.1 More scenes
- The 10-scene val pilot was hand-picked; HSSD has 168 scenes. Stage 1 cost is
  ~5-10 min per scene on a single GPU. Full HSSD scan → ~16-30 hours single GPU.
- The biggest blocker is **navmesh-snap + render** time per candidate
  (~16ms). Doubling `samples_per_object` doubles cost linearly.
- Strongly recommend per-scene checkpointing (already implemented:
  `hssd_fixed_camera_viewpoint_prototype.checkpoint.json`) so a crashed run
  resumes mid-scene.

### 7.2 Open-vocabulary categories
- We currently hard-code the 6 OVON categories. To expand to OVON's full
  category space:
  1. Update `--categories` in Stage 1; the inventory lookup
     (`docs/audits/hssd_category_expansion_inventory.json`) already covers more
     classes via `canonical_category`.
  2. Decide per-cat thresholds (Stage 2). The numbers we settled on are sized
     to typical object dimensions: bed/couch large (vis 0.10), chair/tv medium
     (0.025-0.05), small (plant/toilet 0.005-0.02).
  3. Recompute `HALF_XZ_DIAG_BY_CAT_DEFAULT` from the full HSSD inventory.
  4. For truly open-vocabulary, you'd shift the "category" knob to a
     **semantic-aware** filter: instead of looking up a category in our table,
     score the rendered RGB with CLIP / SAM3 against the requested noun phrase.
     This converts Stage 2 from a static rule engine into a learned classifier;
     the rest of the pipeline (Stage 1 sampling, Stage 3 QA, Stage 4-7
     rendering) stays the same.

### 7.3 Training data quality dials we settled on

If you want to **trade pass rate for quality** (smaller but cleaner train set):
- `--min-fill-ratio 0.55` (vs 0.40) → drops borderline frame-edge views.
- `--max-min-axis-per-cat bed=0.85 tv=0.85` → catches more wall-views.
- `--max-distance 0.75` → stricter distance, only close VPs.

If you want to **trade quality for pass rate** (larger but noisier):
- `--connector or` → recovers OR-rescued samples.
- `--min-fill-ratio 0.0` → drops the fill check entirely.
- `--max-distance 1.5` → admits farther VPs.

---

## 8. Files touched in this iteration

```
tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py   yaw bug fix
tools/hssd_viewpoint/select_fixed_camera_viewpoints.py          bbox fallback + per-cat caps
tools/hssd_viewpoint/build_fixed_camera_visual_qa_pack.py       Stage 3 layout + FoV + legend + zero-visible skip
docs/FIXED_CAMERA_PIPELINE_SUMMARY.md                           this file
```

---

## 9. Next steps suggested

1. Lock the final config (above) and run Stage 1+2+3 on **all 168 HSSD scenes**
   to get the real production pass-rate distribution per category.
2. Build a small CLIP-scored sanity pass over Stage 3 outputs to estimate the
   **semantic correctness** of the accepted viewpoints (independent of our
   geometric rules).
3. Run Stage 4-7 with the final selection to produce MP4 + Parquet for the
   cosmos-policy training.
4. If you scale to open vocabulary, the next blocker is the per-cat threshold
   table — consider learning a **calibrated per-category vis/bbox threshold**
   from a small human-labelled set of "good vs bad viewpoint" examples.
