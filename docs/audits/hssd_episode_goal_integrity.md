# HSSD Episode-to-Goal Integrity Audit

Dataset root: `hssd\habitat-lab\data\datasets\objectnav\hssd-hab`

This audit reads local HSSD ObjectNav JSON/JSON.GZ shards only. It does not import Habitat, launch simulation, render scenes, train models, or modify source code.

## What Was Checked

For each `train/content` and `val/content` shard, the scanner checked:

- total files, episodes, goals, and `view_points`,
- episode `object_category` distribution,
- whether every episode category is one of the six known native HSSD ObjectNav categories,
- whether each episode can resolve to a `goals_by_category` key using the local shard convention,
- whether the resolved target goal list is non-empty,
- whether target goals have non-empty `view_points`,
- whether any target goals have suspiciously tiny viewpoint sets of 0 or 1 viewpoint,
- whether native HSSD episodes contain `children_object_categories`.

## Why This Chain Matters

A native HSSD ObjectNav episode is meaningful only if this chain is intact:

```text
episode -> object_category -> goals_by_category key -> target goals -> view_points
```

The agent is asked to find the episode's `object_category`. Habitat-style `VIEW_POINTS` distance then uses the target goals' `view_points` as success regions. If the category is malformed, the key is missing, or the target goals have bad viewpoint sets, then distance-to-goal and success can become scientifically misleading before any model is trained.

## Summary

| split | files | episodes | goals | view_points | bad categories | missing keys | children fields |
| --- | --- | --- | --- | --- | --- | --- | --- |
| train | 122 | 120552 | 3781 | 884196 | 0 | 0 | 0 |
| val | 42 | 1248 | 1723 | 432873 | 0 | 0 | 0 |

| total files | total episodes | total goals | total view_points |
| --- | --- | --- | --- |
| 164 | 121800 | 5504 | 1317069 |

## Object Category Distribution

| category | episodes |
| --- | --- |
| bed | 20300 |
| chair | 23445 |
| couch | 22362 |
| potted_plant | 22386 |
| toilet | 14157 |
| tv | 19150 |

## Goal-Key Resolution

The scanner did not blindly assume one key format. For each episode it tried raw `scene_id`, normalized path basename, shard filename stem, and unique category-suffix matching against the file's actual `goals_by_category` keys.

| resolution method | episodes |
| --- | --- |
| raw_scene_id_category | 121800 |

## Integrity Findings

- Malformed episode categories: **0**.
- Missing target `goals_by_category` keys: **0**.
- Ambiguous target `goals_by_category` keys: **0**.
- Empty resolved target goal lists: **0**.
- Episodes whose target goal set contains at least one goal with 0 viewpoints: **0**.
- Episodes whose target goal set contains at least one goal with exactly 1 viewpoint: **2332**.
- Episodes whose target goal set contains at least one goal with 0 or 1 viewpoint: **2332**.
- Unique goals with 0 viewpoints: **0**.
- Unique goals with exactly 1 viewpoint: **17**.
- Unique goals with 0 or 1 viewpoint: **17**.
- Episodes containing `children_object_categories`: **0**.
- Episodes with raw `goals_key` field stored in JSON: **0**.

## Beginner-Friendly Interpretation

At the episode-to-goal level, the native HSSD dataset appears internally consistent: every episode has a valid six-class category, resolves to a target goals key, and has non-empty target viewpoints.
As expected for native HSSD ObjectNav, `children_object_categories` does not appear in the scanned episodes. That means the local HSSD data is not already OVON-style child-category expanded.
Some unique goals have tiny viewpoint sets of 0 or 1 viewpoint. Even if no episode is structurally broken, these cases may be brittle success regions and are worth visual or statistical follow-up.

## Meaning for HSSD-to-OVON / VLM / Cosmos Use

This audit checks the static dataset plumbing, not visual correctness. Passing this audit means the episode category can be linked to target goals and target viewpoints. It does **not** prove that:

- object labels are semantically correct in the 3D scene,
- target objects are visible in final rendered frames,
- viewpoints were generated under the same camera assumptions as the policy,
- HSSD is OVON-compatible,
- HSSD success rates are comparable to OVON success rates.

For OVON-style or VLM/Cosmos training, this is a necessary first check. The next layer should audit label correctness and viewpoint/visibility quality, because video-language training needs the rendered frames to actually match the requested object goal.

## Sample Problem Records

Only the first few examples are stored in the JSON summary. If all counts above are zero for a problem type, its sample list may be absent.

Machine-readable details: `ovon_hssd_audit/outputs/hssd_episode_goal_integrity.json`
