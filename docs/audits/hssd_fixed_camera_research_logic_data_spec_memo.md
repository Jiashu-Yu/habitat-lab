# HSSD Fixed-Camera ObjectNav Research Logic + Data Spec Memo

Date: 2026-05-19

Latest planning update, 2026-05-19:

- Jing is testing how low the viewpoint thresholds can go and whether a unified
  threshold profile can work.
- A likely compromise is a two-profile split: tiny objects vs regular objects.
- Camera tilt remains out of scope unless the real robot camera can tilt.
- Data storage/rendering should move toward `256x256`, while the fixed-camera
  simulator/eval standard can stay conceptually aligned with the current
  `640x480` probes.
- Jing pushed WIP branch
  `refactor/repo-cleanup-and-dual-tier` at commit `04e3f85`. It restructures
  the rendering repo and adds a dual-tier label resolver.
- HSSD raw category metadata should preserve official
  `hssd-hab/metadata/hssd_obj_semantics_condensed.csv` columns 3 and 4, but
  ObjectNav-6 task labels should now be resolved with the stricter dual-tier
  policy: v0.2.5 white-list first, then WordNet synset mapping, then
  condensed+room fallback.

## 1. Core Research Claim

This project is not simply a `success_distance` tuning exercise. The goal is to
turn HSSD into a controllable synthetic ObjectNav data factory that can produce
OVON-style trajectory data with auditable semantics, visual quality, navigation
validity, and scalable category coverage.

The central question is:

> Can HSSD metadata + fixed-camera viewpoint QA + trajectory rendering produce
> reliable MP4/Parquet ObjectNav data for training and evaluating open-vocabulary
> embodied navigation policies?

## 2. End-to-End Pipeline

```text
HSSD metadata / object inventory
  -> target instance grounding
  -> raw/canonical/task category assignment
  -> fixed-camera candidate viewpoint generation
  -> train/eval viewpoint selection profiles
  -> single-view visual QA
  -> HSSD ObjectNav episode split export
  -> trajectory rendering
  -> MP4 + episode parquet + step parquet
  -> trajectory/video QA
  -> model training input construction
  -> policy training + evaluation + ablations
  -> larger category / open-vocabulary scaling
```

Each stage should preserve enough identifiers and diagnostic fields to make
failures traceable back to scene, object, candidate viewpoint, selected goal
viewpoint, trajectory, and final rendered observation.

## 3. Semantic Grounding Layer

Problem: regular HSSD scenes do not expose reliable object-level semantic scene
annotations for ObjectNav use. Category-level masks are too noisy for instance
visibility checks.

Current solution:

- match an HSSD metadata object to a runtime rigid object;
- temporarily assign a sentinel semantic id, currently `90000`;
- render RGB + semantic observation from candidate poses;
- count only pixels equal to the sentinel id;
- restore the object's original semantic id.

Research implication: target visibility is instance-grounded rather than broad
category-grounded. This is the foundation that makes later QA meaningful.

## 4. Category Source And Label Policy

The key HSSD raw category file is:

```text
hssd-hab/metadata/hssd_obj_semantics_condensed.csv
```

The relevant columns are:

```text
column 3: Semantic Category: CONDENSED
column 4: Semantic Category: The primary semantic category for the object
```

Local audit result:

```text
rows: 17993
both columns filled: 17993
same condensed/primary label: 14606
different condensed/primary label: 3387
```

Interpretation:

- `condensed_category` should remain the default coarse grouping label for
  broad inventory summaries and threshold buckets.
- `primary_semantic_category` should be preserved as the more fine-grained,
  corrected object label. It is useful for open-vocabulary prompts, audits, and
  synonym mapping.
- Do not overwrite one with the other. Store both in every downstream artifact.
- Do not treat `condensed_category` alone as the final ObjectNav-6 task label.
  Jing's audit found at least one concrete failure: a Pet House was labeled as
  `bed` by HSSD's condensed CSV but should not be a bed target.

Current code already reads this file and uses:

```text
condensed_category -> primary_semantic_category -> main_category -> clean_category -> super_category
```

as the fallback order for canonical category choice.

Jing's `refactor/repo-cleanup-and-dual-tier` branch adds a stricter task-label
resolver:

```text
Tier A: navobj6_*
  HSSD ObjectNav-6 aligned label in {chair, bed, couch, potted_plant, toilet, tv, None}
  priority:
    1. HSSD v0.2.5 objectnav goals_by_category white-list match
    2. WordNet synset whitelist/blacklist mapping
    3. condensed_category + room-consistency fallback when synset is empty

Tier B: open_vocab
  Always populated with wnsynsetkey, WordNet lemmas/gloss/hypernyms,
  FloorPlanner tags, raw condensed label, and raw object name.
```

For training/eval, separate at least four label groups:

```text
raw_category_fields: all HSSD metadata labels preserved for audit
canonical_category: usually condensed_category
navobj6_category: strict HSSD ObjectNav-6-compatible label, nullable
open_vocab: richer language/category metadata for OVON-style training
```

Examples:

- `wnsynsetkey=chair.n.01` maps to `navobj6_category=chair`.
- `wnsynsetkey=pet_house.n.01` should map to `navobj6_category=None` even if
  the condensed CSV says `bed`.
- `condensed_category=plant` can become `navobj6_category=potted_plant` only
  through approved synset or fallback logic, while open-vocab still preserves
  the raw plant wording.

This prevents a common bug: using a good coarse HSSD category for grouping but
accidentally changing the policy's target vocabulary.

Current WIP branch caveat: the dual-tier resolver is in
`viewpoints/_object_label_schema.py` in Jing's rendering repo branch, not yet in
our stable rendering branch. Treat it as the direction to adopt after Jing
finishes the branch, not as a finalized merged API.

## 5. Viewpoint Layer

Fixed-camera viewpoints are not the final training data. They are upstream goal
anchors and quality-control artifacts.

Current fixed-camera assumptions:

- camera height: `0.88m`;
- pitch: `0deg`;
- HFOV: `79deg`;
- target-facing yaw after navmesh snap;
- no look-up / look-down / tilt sweep.

Tilt plan:

- do not add tilt for the current data path;
- revisit only if the real robot camera can tilt or the target deployment
  requires tilt actions;
- keep eval and train camera assumptions matched to the deployed sensor.

Resolution plan:

- current Stage 1 supports `--image-width` and `--image-height`, defaulting to
  `640x480`;
- rendering scripts already support square `--image-size`, with `256` as the
  likely storage-friendly target;
- Stage 3 `--render-missing` currently has a fixed internal `480x640` render
  size and should be parameterized or inferred before using it for 256 runs;
- if Stage 1 moves from `640x480` to `256x256`, absolute pixel gates such as
  `--min-visible-pixels 300` must be rescaled or de-emphasized in favor of
  fraction-based metrics.

Approximate visible-pixel scaling:

```text
640x480 area = 307200
256x256 area = 65536
300 pixels at 640x480 ~= 64 pixels at 256x256
```

Yaw correctness is a hard prerequisite. The yawfix uses:

```text
yaw = atan2(-view_dir.x, -view_dir.z)
```

The old sign convention mirrored left/right off-axis targets and could push
plants, TVs, chairs, or toilets toward frame edges. Any production viewpoint run
used for train data should be generated after this fix.

## 6. Train vs Eval Viewpoint Profiles

Train and eval should not share one unexamined threshold policy.

Train profile:

- strict visual quality;
- target should be clear in the final view;
- reject slivers, sparse masks, severe edge cases, and semantic-but-not-visual
  close-ups;
- accept losing some objects if the sample would teach poor visual grounding.

Eval profile:

- closer to Habitat/HSSD/OVON goal semantics;
- reachable and reasonably visible;
- less aggressively filtered than train;
- avoids false negatives caused by an overly narrow "pretty frame" definition.

Important benchmark decision: do not redefine success as raw
`distance_to_bbox <= 1m`. Keep ObjectNav success based on goal `view_points`.
Control quality by deciding which viewpoints enter the goal set.

## 7. Recommended Train-Quality Selection Logic

The current post-yawfix train-quality selection direction is:

```text
bbox_metric = max_axis
connector = AND
distance = distance_to_bbox first
fallback distance = distance_to_bbox_estimated, then distance_to_object
```

Recommended gates:

- both `image_fraction` and bbox size should pass;
- use `max_axis` rather than bbox area for elongated objects;
- use per-category visibility/bbox thresholds;
- use fill-ratio to reject sparse masks;
- use min-axis to reject slivers;
- use category-specific close-up caps for bed-like failure modes;
- avoid hard-rejecting `near_full_frame_bbox` by default, because some large
  objects are valid close views.

Bed deserves special caution because its bbox can include surrounding structure,
bed frame, wall panels, or nearby objects. Some bed views are semantically
correct but visually poor for training.

Near-term threshold research should compare:

```text
A. current per-category yawfix profile
B. one unified threshold profile for all categories
C. two-profile setup: tiny objects vs regular objects
D. relaxed eval profile aligned with reasonable HSSD/OVON-style goals
```

The comparison should be judged by category/object pass rate, Stage 3 visual QA,
MP4 tail QA, and eventually training/eval performance. A unified threshold is
only acceptable if it does not quietly damage tiny-object or thin-object quality.

## 8. Single-View QA Contract

Stage 3 QA should answer:

- is the target visible?
- is the target semantically correct?
- is the target centered or at least not an accidental edge sliver?
- does the BEV camera direction agree with the rendered view?
- are rejected candidates rejected for understandable reasons?
- are failure modes category-specific or systematic?

Preferred review artifact:

```text
RGB | Overlay | Mask
BEV | Text    | Depth
```

The QA pack should include target metadata, selection status, rejection reasons,
distance-to-center, distance-to-bbox, selected thresholds, and image links.

## 9. Trajectory Data Product

The final train/eval product is not only final-frame viewpoints. It is rendered
navigation trajectories:

- MP4 videos for human review and possible video-centric pipelines;
- episode parquet for episode-level metadata;
- step parquet for per-step observations/actions/states;
- review packs for final frames and tail clips.

Minimum episode-level fields:

```text
episode_id
scene_id
category
canonical_category
object_id / instance_index / object_uid
object_name / template_name / rigid_object_handle
raw_category_fields
canonical_category
task_category
split
start_position
start_rotation
target_viewpoint_position
target_viewpoint_rotation
target_viewpoint_candidate_index
target_viewpoint_selection_rule
initial_geodesic
target_viewpoint_geodesic
success / failure_reason
visibility_verified
final_visible_pixels
final_image_fraction
final_bbox_fraction
final_bbox_max_axis_fraction
final_distance_to_bbox
final_distance_to_object
selection_profile
selection_reasons
render_image_size
```

Minimum step-level fields:

```text
episode_id
step_index
scene_id
rgb_path or video_frame_ref
agent_position
agent_rotation
action
geodesic_to_target_viewpoint
euclidean_to_target_bbox
target_visible_pixels
target_image_fraction
target_bbox
target_bbox_area_fraction
target_bbox_max_axis_fraction
is_final_step
image_size
```

If the training input uses temporal context, step parquet or the dataloader must
support retrieving at least the previous 4 visual frames for each supervised
training sample.

## 10. Trajectory QA Contract

Single-view QA is necessary but not sufficient. Before scaling, trajectory QA
should check:

- final STOP frame sees the target;
- last 4 frames provide useful visual context;
- target does not only appear as a tiny/edge sliver at the end;
- path does not cross floors unexpectedly;
- trajectory is not dominated by collision/follower artifacts;
- selected viewpoint metadata matches the rendered final camera;
- category-balanced MP4 review samples look trainable.

For training, `visibility_verified=False` should initially be treated as a hard
filter or at least a separately reportable diagnostic bucket. We should avoid
mixing unverified and verified samples without an explicit ablation.

## 11. Training Input Assumptions

Current expected model input direction:

- goal category or language target;
- current RGB observation;
- at least 4 past RGB observations or frame references;
- action / trajectory supervision derived from rendered episodes;
- optional state/geodesic diagnostics for analysis, not necessarily policy
  input.

Open question: whether MP4 is only a review artifact or also the canonical image
source for training. The safer data contract is to keep MP4 plus structured
step parquet references, so either video decoding or direct frame extraction can
be supported later.

## 12. Scaling and Open Vocabulary

For fixed OVON-style categories, per-category thresholds are acceptable and
useful. For open vocabulary, too many handcrafted thresholds become brittle.

Likely scaling path:

1. keep geometry and sentinel-instance grounding unchanged;
2. start with a small set of threshold profiles by object size/type;
3. record rich visual metrics for every candidate;
4. build a human-reviewed good/bad viewpoint set;
5. later replace or augment static thresholds with semantic scoring, such as
   CLIP/SAM-style image-target agreement.

The pipeline should therefore preserve raw candidate metrics even when the
current selector makes a hard accept/reject decision.

## 13. Immediate Decisions Before Full Train Run

Before a large server/HPC run, decide:

1. exact train selection profile and output name;
2. whether train uses per-category, unified, or tiny-vs-regular thresholds;
3. whether eval uses a relaxed profile;
4. exact `task_category` mapping from condensed/primary categories;
5. final image size for Stage 1 metrics, Stage 3 QA, and MP4 rendering;
6. visible-pixel threshold scaling for 256 runs;
7. per-object `top_k` accepted viewpoints for export;
8. episodes per object and start-distance distribution;
9. whether `visibility_verified` is a hard filter;
10. bed-specific and plant-specific manual QA rules;
11. final episode parquet and step parquet schema;
12. category-balanced MP4 review sample size;
13. whether to exclude known bad scene `108736611_177263226`;
14. how past-4-frame training samples are indexed.

## 14. Updated Short-Term Plan

1. Pull Jing's next push and inspect code/docs, especially threshold profiles,
   image-size changes, and category handling.
2. Confirm whether category selection still uses
   `hssd_obj_semantics_condensed.csv` columns 3/4 and whether a new
   `navobj6_category` / `open_vocab` field is introduced.
3. Adopt the explicit label mapping layer:
   raw fields -> canonical category -> navobj6/open_vocab labels.
4. Check WIP command/API mismatches before running. In commit `04e3f85`,
   `run_full_pipeline.sh` passes `--output-data-root` and
   `--scene-dataset-config` to `episodes/export_selection_to_hssd.py`, but the
   parser exposes `--data-root` and no `--scene-dataset-config`.
5. Decide the threshold experiment grid: per-category vs unified vs
   tiny/regular.
6. Decide the image-size strategy. If running Stage 1 at 256, adjust
   `min_visible_pixels` and parameterize Stage 3 `--render-missing`.
7. Run small server-side sanity batches only after the above contract is fixed.
8. Use Maxwell/server runs for actual rendering; local work remains code/docs
   and static validation.

## 15. Working Principle

Prefer smaller, cleaner, auditable training data over larger noisy data. Scale
only after the failure modes are visible in single-view QA, trajectory QA, and
parquet summaries.
