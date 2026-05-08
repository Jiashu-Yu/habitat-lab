#!/usr/bin/env python3
"""Summarize Habitat ObjectNav-style JSON/JSON.GZ dataset shards.

This script intentionally avoids Habitat imports so it can run before the
simulator environment is configured.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_OUT_JSON = Path("outputs/hssd_dataset_stats.json")
DEFAULT_OUT_CSV = Path("outputs/hssd_category_stats.csv")


def read_json(path: Path) -> Dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_split_files(dataset_root: Path, split: str) -> Iterable[Path]:
    content_dir = dataset_root / split / "content"
    if content_dir.exists():
        yield from sorted(content_dir.glob("*.json"))
        yield from sorted(content_dir.glob("*.json.gz"))
        return

    split_dir = dataset_root / split
    if split_dir.exists():
        yield from sorted(split_dir.glob("*.json"))
        yield from sorted(split_dir.glob("*.json.gz"))
        return

    for suffix in (".json", ".json.gz"):
        fp = dataset_root / f"{split}{suffix}"
        if fp.exists():
            yield fp


def category_for_goal_key(
    goal_key: str,
    key_to_category: Dict[str, str],
    seen_categories: Iterable[str],
) -> str:
    if goal_key in key_to_category:
        return key_to_category[goal_key]
    for cat in sorted(set(seen_categories), key=len, reverse=True):
        if goal_key == cat or goal_key.endswith("_" + cat):
            return cat
    return goal_key or "<missing>"


def viewpoint_count(goal: Dict[str, Any]) -> int:
    view_points = goal.get("view_points", [])
    if isinstance(view_points, list):
        return len(view_points)
    return 0


def collect_known_categories(dataset_root: Path) -> List[str]:
    known = set()
    for split in ("train", "val"):
        for fp in iter_split_files(dataset_root, split):
            data = read_json(fp)
            for map_key in (
                "category_to_task_category_id",
                "category_to_scene_annotation_category_id",
            ):
                mapping = data.get(map_key, {})
                if isinstance(mapping, dict):
                    known.update(str(k) for k in mapping.keys())
            episodes = data.get("episodes", [])
            if isinstance(episodes, list):
                for ep in episodes:
                    if isinstance(ep, dict) and ep.get("object_category"):
                        known.add(str(ep["object_category"]))
    return sorted(known)


def summarize_dataset(dataset_root: Path) -> Dict[str, Any]:
    known_categories = collect_known_categories(dataset_root)
    split_summaries: Dict[str, Dict[str, Any]] = {}
    category_rows: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "category": "",
            "episodes": 0,
            "goals": 0,
            "viewpoints": 0,
            "viewpoints_per_goal_values": [],
            "splits": Counter(),
        }
    )
    all_top_level_keys = Counter()
    all_episode_keys = Counter()
    sampled_top_level_keys: List[List[str]] = []
    sampled_episode_keys: List[List[str]] = []

    total_files = 0
    total_episodes = 0
    total_goals = 0
    total_viewpoints = 0
    total_children_field = 0
    global_vp_per_goal: List[int] = []

    for split in ("train", "val"):
        files = list(iter_split_files(dataset_root, split))
        split_counter = {
            "files": len(files),
            "episodes": 0,
            "episodes_with_children_object_categories": 0,
            "goals": 0,
            "viewpoints": 0,
            "categories": Counter(),
            "top_level_keys": Counter(),
            "episode_keys": Counter(),
        }
        split_vp_per_goal: List[int] = []

        for fp in files:
            total_files += 1
            data = read_json(fp)
            top_keys = sorted(data.keys())
            all_top_level_keys.update(top_keys)
            split_counter["top_level_keys"].update(top_keys)
            if len(sampled_top_level_keys) < 10:
                sampled_top_level_keys.append(top_keys)

            episodes = data.get("episodes", [])
            if not isinstance(episodes, list):
                episodes = []
            key_to_category = {}
            seen_categories = set()

            for ep in episodes:
                if not isinstance(ep, dict):
                    continue
                ep_keys = sorted(ep.keys())
                all_episode_keys.update(ep_keys)
                split_counter["episode_keys"].update(ep_keys)
                if len(sampled_episode_keys) < 10:
                    sampled_episode_keys.append(ep_keys)

                category = str(ep.get("object_category") or "<missing>")
                seen_categories.add(category)
                goals_key = str(ep.get("goals_key") or "")
                if goals_key:
                    key_to_category[goals_key] = category

                split_counter["episodes"] += 1
                total_episodes += 1
                split_counter["categories"][category] += 1
                row = category_rows[category]
                row["category"] = category
                row["episodes"] += 1
                row["splits"][split] += 1

                if "children_object_categories" in ep:
                    split_counter["episodes_with_children_object_categories"] += 1
                    total_children_field += 1

            goals_by_category = data.get("goals_by_category", {})
            if not isinstance(goals_by_category, dict):
                goals_by_category = {}
            for goal_key, goals in goals_by_category.items():
                if not isinstance(goals, list):
                    continue
                category = category_for_goal_key(
                    str(goal_key),
                    key_to_category,
                    set(known_categories) | seen_categories,
                )
                row = category_rows[category]
                row["category"] = category
                for goal in goals:
                    if not isinstance(goal, dict):
                        continue
                    vp_count = viewpoint_count(goal)
                    row["goals"] += 1
                    row["viewpoints"] += vp_count
                    row["viewpoints_per_goal_values"].append(vp_count)
                    split_counter["goals"] += 1
                    split_counter["viewpoints"] += vp_count
                    total_goals += 1
                    total_viewpoints += vp_count
                    split_vp_per_goal.append(vp_count)
                    global_vp_per_goal.append(vp_count)

        split_summaries[split] = {
            "files": split_counter["files"],
            "episodes": split_counter["episodes"],
            "episodes_with_children_object_categories": split_counter[
                "episodes_with_children_object_categories"
            ],
            "goals": split_counter["goals"],
            "viewpoints": split_counter["viewpoints"],
            "categories": dict(sorted(split_counter["categories"].items())),
            "top_level_keys": dict(sorted(split_counter["top_level_keys"].items())),
            "episode_keys": dict(sorted(split_counter["episode_keys"].items())),
            "viewpoints_per_goal_avg": (
                sum(split_vp_per_goal) / len(split_vp_per_goal)
                if split_vp_per_goal
                else 0.0
            ),
            "viewpoints_per_goal_min": min(split_vp_per_goal) if split_vp_per_goal else 0,
            "viewpoints_per_goal_max": max(split_vp_per_goal) if split_vp_per_goal else 0,
        }

    category_summary = []
    for category, row in category_rows.items():
        values = row["viewpoints_per_goal_values"]
        category_summary.append(
            {
                "category": category,
                "episodes": int(row["episodes"]),
                "train_episodes": int(row["splits"]["train"]),
                "val_episodes": int(row["splits"]["val"]),
                "goals": int(row["goals"]),
                "viewpoints": int(row["viewpoints"]),
                "viewpoints_per_goal_avg": (sum(values) / len(values) if values else 0.0),
                "viewpoints_per_goal_min": min(values) if values else 0,
                "viewpoints_per_goal_max": max(values) if values else 0,
            }
        )
    category_summary.sort(key=lambda r: (r["episodes"], r["goals"], r["category"]), reverse=True)

    return {
        "dataset_root": str(dataset_root),
        "splits": split_summaries,
        "totals": {
            "files": total_files,
            "episodes": total_episodes,
            "goals": total_goals,
            "viewpoints": total_viewpoints,
            "episodes_with_children_object_categories": total_children_field,
            "categories": len(category_summary),
            "viewpoints_per_goal_avg": (
                sum(global_vp_per_goal) / len(global_vp_per_goal) if global_vp_per_goal else 0.0
            ),
            "viewpoints_per_goal_min": min(global_vp_per_goal) if global_vp_per_goal else 0,
            "viewpoints_per_goal_max": max(global_vp_per_goal) if global_vp_per_goal else 0,
        },
        "top_level_keys": dict(sorted(all_top_level_keys.items())),
        "episode_keys": dict(sorted(all_episode_keys.items())),
        "sampled_top_level_keys": sampled_top_level_keys,
        "sampled_episode_keys": sampled_episode_keys,
        "known_categories_from_maps_and_episodes": known_categories,
        "category_summary": category_summary,
    }


def write_category_csv(rows: List[Dict[str, Any]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "category",
        "episodes",
        "train_episodes",
        "val_episodes",
        "goals",
        "viewpoints",
        "viewpoints_per_goal_avg",
        "viewpoints_per_goal_min",
        "viewpoints_per_goal_max",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize ObjectNav JSON/JSON.GZ shards.")
    parser.add_argument("--dataset-root", required=True, help="Dataset root containing train/content and val/content.")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON), help="Output JSON summary path.")
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV), help="Output category CSV path.")
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root does not exist: {dataset_root}")

    summary = summarize_dataset(dataset_root)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_category_csv(summary["category_summary"], Path(args.out_csv))

    totals = summary["totals"]
    print(json.dumps({"dataset_root": str(dataset_root), "totals": totals}, indent=2, sort_keys=True))
    print(f"Wrote {out_json}")
    print(f"Wrote {args.out_csv}")


if __name__ == "__main__":
    main()

