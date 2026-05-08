#!/usr/bin/env python3
"""Static HSSD ObjectNav episode-to-goal integrity audit.

This script reads Habitat ObjectNav JSON/JSON.GZ shards only. It does not import
Habitat, launch simulation, or modify dataset/source files.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VALID_CATEGORIES = {"bed", "chair", "couch", "potted_plant", "toilet", "tv"}
DEFAULT_DATASET_ROOT = Path("data/datasets/objectnav/hssd-hab")
DEFAULT_OUTPUT_JSON = Path("outputs/hssd_episode_goal_integrity.json")
DEFAULT_OUTPUT_MD = Path("outputs/hssd_episode_goal_integrity.md")
MAX_SAMPLES = 25


def load_json(path: Path) -> dict[str, Any]:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def strip_known_suffixes(name: str) -> str:
    """Normalize scene-like filenames to the key stem commonly used in goals."""
    out = name
    changed = True
    suffixes = [
        ".scene_instance.json",
        ".basis.glb",
        ".semantic.glb",
        ".glb",
        ".json",
        ".gz",
    ]
    while changed:
        changed = False
        for suffix in suffixes:
            if out.endswith(suffix):
                out = out[: -len(suffix)]
                changed = True
    return out


def shard_scene_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".json.gz"):
        return name[: -len(".json.gz")]
    if name.endswith(".json"):
        return name[: -len(".json")]
    return path.stem


def basename_for_any_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").split("/")[-1]


def add_sample(samples: list[dict[str, Any]], item: dict[str, Any]) -> None:
    if len(samples) < MAX_SAMPLES:
        samples.append(item)


def resolve_goal_key(
    *,
    goals_keys: set[str],
    scene_id: Any,
    category: str,
    file_stem: str,
) -> tuple[str | None, str, list[str]]:
    """Resolve the target goals_by_category key for an episode.

    Returns (key, method, attempted_candidates).
    """
    scene_text = "" if scene_id is None else str(scene_id)
    base = basename_for_any_path(scene_text)
    norm_base = strip_known_suffixes(base)
    norm_scene = strip_known_suffixes(scene_text)

    candidates: list[tuple[str, str]] = []
    for method, prefix in [
        ("raw_scene_id_category", scene_text),
        ("normalized_scene_id_category", norm_scene),
        ("basename_category", base),
        ("normalized_basename_category", norm_base),
        ("file_stem_category", file_stem),
    ]:
        if prefix:
            candidates.append((method, f"{prefix}_{category}"))

    seen = set()
    unique_candidates: list[tuple[str, str]] = []
    for method, key in candidates:
        if key not in seen:
            seen.add(key)
            unique_candidates.append((method, key))

    for method, key in unique_candidates:
        if key in goals_keys:
            return key, method, [c for _, c in unique_candidates]

    suffix = f"_{category}"
    matches = sorted(k for k in goals_keys if k.endswith(suffix))
    if len(matches) == 1:
        return matches[0], "unique_category_suffix_match", [c for _, c in unique_candidates]
    if len(matches) > 1:
        return None, "ambiguous_category_suffix_match", [c for _, c in unique_candidates] + matches
    return None, "missing", [c for _, c in unique_candidates]


def empty_split_stats() -> dict[str, Any]:
    return {
        "files": 0,
        "episodes": 0,
        "goals": 0,
        "view_points": 0,
        "object_category_distribution": Counter(),
        "invalid_object_category_episodes": 0,
        "missing_goal_key_episodes": 0,
        "ambiguous_goal_key_episodes": 0,
        "empty_goal_list_episodes": 0,
        "episodes_with_any_empty_target_goal_viewpoints": 0,
        "episodes_with_any_one_viewpoint_target_goal": 0,
        "episodes_with_any_tiny_target_goal_viewpoints": 0,
        "episodes_with_children_object_categories": 0,
        "episodes_with_raw_goals_key": 0,
        "unique_goals_with_zero_viewpoints": 0,
        "unique_goals_with_one_viewpoint": 0,
        "unique_goals_with_tiny_viewpoints": 0,
        "goal_key_resolution_methods": Counter(),
        "shard_errors": 0,
    }


def counter_to_dict(obj: Any) -> Any:
    if isinstance(obj, Counter):
        return dict(sorted(obj.items()))
    if isinstance(obj, dict):
        return {k: counter_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [counter_to_dict(v) for v in obj]
    return obj


def scan_dataset(dataset_root: Path) -> dict[str, Any]:
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    split_stats: dict[str, dict[str, Any]] = {}
    totals = empty_split_stats()
    seen_goal_records: set[tuple[str, str, int]] = set()

    for split in ["train", "val"]:
        stats = empty_split_stats()
        content_dir = dataset_root / split / "content"
        files = []
        if content_dir.exists():
            files = sorted(content_dir.glob("*.json")) + sorted(content_dir.glob("*.json.gz"))

        for shard_path in files:
            stats["files"] += 1
            totals["files"] += 1
            file_stem = shard_scene_stem(shard_path)

            try:
                shard = load_json(shard_path)
            except Exception as exc:  # pragma: no cover - defensive reporting
                stats["shard_errors"] += 1
                totals["shard_errors"] += 1
                add_sample(
                    samples["shard_errors"],
                    {"split": split, "file": str(shard_path), "error": repr(exc)},
                )
                continue

            goals_by_category = shard.get("goals_by_category", {}) or {}
            goals_keys = set(goals_by_category.keys())

            for goals_key, goals in goals_by_category.items():
                if not isinstance(goals, list):
                    add_sample(
                        samples["non_list_goals_by_category"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "goals_key": goals_key,
                            "type": type(goals).__name__,
                        },
                    )
                    continue
                stats["goals"] += len(goals)
                totals["goals"] += len(goals)

                for goal_index, goal in enumerate(goals):
                    record_id = (str(shard_path), goals_key, goal_index)
                    if record_id in seen_goal_records:
                        continue
                    seen_goal_records.add(record_id)
                    view_points = goal.get("view_points", []) or []
                    vp_count = len(view_points) if isinstance(view_points, list) else 0
                    stats["view_points"] += vp_count
                    totals["view_points"] += vp_count

                    if vp_count == 0:
                        stats["unique_goals_with_zero_viewpoints"] += 1
                        totals["unique_goals_with_zero_viewpoints"] += 1
                        add_sample(
                            samples["unique_goals_with_zero_viewpoints"],
                            {
                                "split": split,
                                "file": str(shard_path),
                                "goals_key": goals_key,
                                "goal_index": goal_index,
                                "object_id": goal.get("object_id"),
                                "object_category": goal.get("object_category"),
                            },
                        )
                    if vp_count == 1:
                        stats["unique_goals_with_one_viewpoint"] += 1
                        totals["unique_goals_with_one_viewpoint"] += 1
                    if vp_count <= 1:
                        stats["unique_goals_with_tiny_viewpoints"] += 1
                        totals["unique_goals_with_tiny_viewpoints"] += 1
                        add_sample(
                            samples["unique_goals_with_tiny_viewpoints"],
                            {
                                "split": split,
                                "file": str(shard_path),
                                "goals_key": goals_key,
                                "goal_index": goal_index,
                                "object_id": goal.get("object_id"),
                                "object_category": goal.get("object_category"),
                                "view_points": vp_count,
                            },
                        )

            episodes = shard.get("episodes", []) or []
            for ep_index, episode in enumerate(episodes):
                stats["episodes"] += 1
                totals["episodes"] += 1

                category = episode.get("object_category")
                category_text = "" if category is None else str(category)
                stats["object_category_distribution"][category_text] += 1
                totals["object_category_distribution"][category_text] += 1

                if category_text not in VALID_CATEGORIES:
                    stats["invalid_object_category_episodes"] += 1
                    totals["invalid_object_category_episodes"] += 1
                    add_sample(
                        samples["invalid_object_category_episodes"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                        },
                    )

                if "children_object_categories" in episode:
                    stats["episodes_with_children_object_categories"] += 1
                    totals["episodes_with_children_object_categories"] += 1
                    add_sample(
                        samples["episodes_with_children_object_categories"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                            "children_object_categories": episode.get("children_object_categories"),
                        },
                    )

                if "goals_key" in episode:
                    stats["episodes_with_raw_goals_key"] += 1
                    totals["episodes_with_raw_goals_key"] += 1

                key, method, attempted = resolve_goal_key(
                    goals_keys=goals_keys,
                    scene_id=episode.get("scene_id"),
                    category=category_text,
                    file_stem=file_stem,
                )
                stats["goal_key_resolution_methods"][method] += 1
                totals["goal_key_resolution_methods"][method] += 1

                if key is None:
                    if method.startswith("ambiguous"):
                        stats["ambiguous_goal_key_episodes"] += 1
                        totals["ambiguous_goal_key_episodes"] += 1
                        sample_name = "ambiguous_goal_key_episodes"
                    else:
                        stats["missing_goal_key_episodes"] += 1
                        totals["missing_goal_key_episodes"] += 1
                        sample_name = "missing_goal_key_episodes"
                    add_sample(
                        samples[sample_name],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                            "resolution_method": method,
                            "attempted_or_matched_keys": attempted[:20],
                        },
                    )
                    continue

                target_goals = goals_by_category.get(key)
                if not isinstance(target_goals, list) or len(target_goals) == 0:
                    stats["empty_goal_list_episodes"] += 1
                    totals["empty_goal_list_episodes"] += 1
                    add_sample(
                        samples["empty_goal_list_episodes"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                            "resolved_goals_key": key,
                        },
                    )
                    continue

                vp_counts = [
                    len(goal.get("view_points", []) or [])
                    if isinstance(goal.get("view_points", []) or [], list)
                    else 0
                    for goal in target_goals
                ]
                if any(count == 0 for count in vp_counts):
                    stats["episodes_with_any_empty_target_goal_viewpoints"] += 1
                    totals["episodes_with_any_empty_target_goal_viewpoints"] += 1
                    add_sample(
                        samples["episodes_with_any_empty_target_goal_viewpoints"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                            "resolved_goals_key": key,
                            "target_goal_viewpoint_counts": vp_counts,
                        },
                    )
                if any(count == 1 for count in vp_counts):
                    stats["episodes_with_any_one_viewpoint_target_goal"] += 1
                    totals["episodes_with_any_one_viewpoint_target_goal"] += 1
                if any(count <= 1 for count in vp_counts):
                    stats["episodes_with_any_tiny_target_goal_viewpoints"] += 1
                    totals["episodes_with_any_tiny_target_goal_viewpoints"] += 1
                    add_sample(
                        samples["episodes_with_any_tiny_target_goal_viewpoints"],
                        {
                            "split": split,
                            "file": str(shard_path),
                            "episode_index": ep_index,
                            "episode_id": episode.get("episode_id"),
                            "scene_id": episode.get("scene_id"),
                            "object_category": category,
                            "resolved_goals_key": key,
                            "target_goal_viewpoint_counts": vp_counts,
                        },
                    )

        split_stats[split] = counter_to_dict(stats)

    summary = {
        "dataset_root": str(dataset_root),
        "valid_native_hssd_categories": sorted(VALID_CATEGORIES),
        "splits": split_stats,
        "totals": counter_to_dict(totals),
        "samples": dict(samples),
        "conclusion_flags": {},
    }

    total_flags = summary["totals"]
    summary["conclusion_flags"] = {
        "all_episode_categories_valid": total_flags["invalid_object_category_episodes"] == 0,
        "all_episode_goal_keys_resolved": (
            total_flags["missing_goal_key_episodes"] == 0
            and total_flags["ambiguous_goal_key_episodes"] == 0
        ),
        "all_resolved_goal_lists_non_empty": total_flags["empty_goal_list_episodes"] == 0,
        "all_target_goals_have_viewpoints": (
            total_flags["episodes_with_any_empty_target_goal_viewpoints"] == 0
        ),
        "native_hssd_has_no_children_object_categories": (
            total_flags["episodes_with_children_object_categories"] == 0
        ),
        "has_tiny_viewpoint_goals": total_flags["unique_goals_with_tiny_viewpoints"] > 0,
    }
    return summary


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    totals = summary["totals"]
    flags = summary["conclusion_flags"]
    category_counts = totals["object_category_distribution"]

    split_rows = []
    for split, stats in summary["splits"].items():
        split_rows.append(
            [
                split,
                stats["files"],
                stats["episodes"],
                stats["goals"],
                stats["view_points"],
                stats["invalid_object_category_episodes"],
                stats["missing_goal_key_episodes"],
                stats["episodes_with_children_object_categories"],
            ]
        )

    category_rows = [
        [cat, category_counts.get(cat, 0)]
        for cat in sorted(set(category_counts) | VALID_CATEGORIES)
    ]

    method_rows = [
        [method, count]
        for method, count in totals["goal_key_resolution_methods"].items()
    ]

    lines = [
        "# HSSD Episode-to-Goal Integrity Audit",
        "",
        f"Dataset root: `{summary['dataset_root']}`",
        "",
        "This audit reads local HSSD ObjectNav JSON/JSON.GZ shards only. It does not import Habitat, launch simulation, render scenes, train models, or modify source code.",
        "",
        "## What Was Checked",
        "",
        "For each `train/content` and `val/content` shard, the scanner checked:",
        "",
        "- total files, episodes, goals, and `view_points`,",
        "- episode `object_category` distribution,",
        "- whether every episode category is one of the six known native HSSD ObjectNav categories,",
        "- whether each episode can resolve to a `goals_by_category` key using the local shard convention,",
        "- whether the resolved target goal list is non-empty,",
        "- whether target goals have non-empty `view_points`,",
        "- whether any target goals have suspiciously tiny viewpoint sets of 0 or 1 viewpoint,",
        "- whether native HSSD episodes contain `children_object_categories`.",
        "",
        "## Why This Chain Matters",
        "",
        "A native HSSD ObjectNav episode is meaningful only if this chain is intact:",
        "",
        "```text",
        "episode -> object_category -> goals_by_category key -> target goals -> view_points",
        "```",
        "",
        "The agent is asked to find the episode's `object_category`. Habitat-style `VIEW_POINTS` distance then uses the target goals' `view_points` as success regions. If the category is malformed, the key is missing, or the target goals have bad viewpoint sets, then distance-to-goal and success can become scientifically misleading before any model is trained.",
        "",
        "## Summary",
        "",
        md_table(
            ["split", "files", "episodes", "goals", "view_points", "bad categories", "missing keys", "children fields"],
            split_rows,
        ),
        "",
        md_table(
            ["total files", "total episodes", "total goals", "total view_points"],
            [[totals["files"], totals["episodes"], totals["goals"], totals["view_points"]]],
        ),
        "",
        "## Object Category Distribution",
        "",
        md_table(["category", "episodes"], category_rows),
        "",
        "## Goal-Key Resolution",
        "",
        "The scanner did not blindly assume one key format. For each episode it tried raw `scene_id`, normalized path basename, shard filename stem, and unique category-suffix matching against the file's actual `goals_by_category` keys.",
        "",
        md_table(["resolution method", "episodes"], method_rows),
        "",
        "## Integrity Findings",
        "",
        f"- Malformed episode categories: **{totals['invalid_object_category_episodes']}**.",
        f"- Missing target `goals_by_category` keys: **{totals['missing_goal_key_episodes']}**.",
        f"- Ambiguous target `goals_by_category` keys: **{totals['ambiguous_goal_key_episodes']}**.",
        f"- Empty resolved target goal lists: **{totals['empty_goal_list_episodes']}**.",
        f"- Episodes whose target goal set contains at least one goal with 0 viewpoints: **{totals['episodes_with_any_empty_target_goal_viewpoints']}**.",
        f"- Episodes whose target goal set contains at least one goal with exactly 1 viewpoint: **{totals['episodes_with_any_one_viewpoint_target_goal']}**.",
        f"- Episodes whose target goal set contains at least one goal with 0 or 1 viewpoint: **{totals['episodes_with_any_tiny_target_goal_viewpoints']}**.",
        f"- Unique goals with 0 viewpoints: **{totals['unique_goals_with_zero_viewpoints']}**.",
        f"- Unique goals with exactly 1 viewpoint: **{totals['unique_goals_with_one_viewpoint']}**.",
        f"- Unique goals with 0 or 1 viewpoint: **{totals['unique_goals_with_tiny_viewpoints']}**.",
        f"- Episodes containing `children_object_categories`: **{totals['episodes_with_children_object_categories']}**.",
        f"- Episodes with raw `goals_key` field stored in JSON: **{totals['episodes_with_raw_goals_key']}**.",
        "",
        "## Beginner-Friendly Interpretation",
        "",
    ]

    if (
        flags["all_episode_categories_valid"]
        and flags["all_episode_goal_keys_resolved"]
        and flags["all_resolved_goal_lists_non_empty"]
        and flags["all_target_goals_have_viewpoints"]
    ):
        lines.append(
            "At the episode-to-goal level, the native HSSD dataset appears internally consistent: every episode has a valid six-class category, resolves to a target goals key, and has non-empty target viewpoints."
        )
    else:
        lines.append(
            "The native HSSD dataset has at least one episode-to-goal integrity issue. Inspect the JSON samples for exact cases before rendering or training."
        )

    if flags["native_hssd_has_no_children_object_categories"]:
        lines.append(
            "As expected for native HSSD ObjectNav, `children_object_categories` does not appear in the scanned episodes. That means the local HSSD data is not already OVON-style child-category expanded."
        )
    else:
        lines.append(
            "`children_object_categories` appears in at least one scanned episode. That would be unexpected for native HSSD ObjectNav and should be inspected."
        )

    if flags["has_tiny_viewpoint_goals"]:
        lines.append(
            "Some unique goals have tiny viewpoint sets of 0 or 1 viewpoint. Even if no episode is structurally broken, these cases may be brittle success regions and are worth visual or statistical follow-up."
        )
    else:
        lines.append(
            "No unique goals with 0 or 1 viewpoint were found."
        )

    lines.extend(
        [
            "",
            "## Meaning for HSSD-to-OVON / VLM / Cosmos Use",
            "",
            "This audit checks the static dataset plumbing, not visual correctness. Passing this audit means the episode category can be linked to target goals and target viewpoints. It does **not** prove that:",
            "",
            "- object labels are semantically correct in the 3D scene,",
            "- target objects are visible in final rendered frames,",
            "- viewpoints were generated under the same camera assumptions as the policy,",
            "- HSSD is OVON-compatible,",
            "- HSSD success rates are comparable to OVON success rates.",
            "",
            "For OVON-style or VLM/Cosmos training, this is a necessary first check. The next layer should audit label correctness and viewpoint/visibility quality, because video-language training needs the rendered frames to actually match the requested object goal.",
            "",
            "## Sample Problem Records",
            "",
            "Only the first few examples are stored in the JSON summary. If all counts above are zero for a problem type, its sample list may be absent.",
            "",
            f"Machine-readable details: `outputs/hssd_episode_goal_integrity.json`",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    summary = scan_dataset(args.dataset_root)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(counter_to_dict(summary), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_markdown(summary, args.output_md)

    totals = summary["totals"]
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(
        "Scanned "
        f"{totals['files']} files, {totals['episodes']} episodes, "
        f"{totals['goals']} goals, {totals['view_points']} view_points."
    )
    print(
        "Integrity flags: "
        + ", ".join(
            f"{name}={value}" for name, value in summary["conclusion_flags"].items()
        )
    )


if __name__ == "__main__":
    main()

