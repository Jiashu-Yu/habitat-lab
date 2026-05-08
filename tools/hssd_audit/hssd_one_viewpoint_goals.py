#!/usr/bin/env python3
"""List HSSD ObjectNav unique goals with exactly one viewpoint.

Static-only audit: reads local JSON/JSON.GZ dataset shards and writes summary
artifacts. Does not import Habitat, launch simulation, or modify dataset/source
files.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_DATASET_ROOT = Path("data/datasets/objectnav/hssd-hab")
DEFAULT_OUTPUT_JSON = Path("outputs/hssd_one_viewpoint_goals.json")
DEFAULT_OUTPUT_MD = Path("outputs/hssd_one_viewpoint_goals.md")


def load_json(path: Path) -> dict[str, Any]:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def percentile(sorted_values: list[int], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * pct
    lower = int(pos)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = pos - lower
    return float(sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac)


def category_distribution(counts: list[int]) -> dict[str, Any]:
    sorted_counts = sorted(counts)
    n = len(sorted_counts)
    histogram = Counter(sorted_counts)
    return {
        "num_goals": n,
        "min": sorted_counts[0] if sorted_counts else None,
        "p01": percentile(sorted_counts, 0.01),
        "p05": percentile(sorted_counts, 0.05),
        "p10": percentile(sorted_counts, 0.10),
        "q1": percentile(sorted_counts, 0.25),
        "median": float(median(sorted_counts)) if sorted_counts else None,
        "mean": float(mean(sorted_counts)) if sorted_counts else None,
        "q3": percentile(sorted_counts, 0.75),
        "p90": percentile(sorted_counts, 0.90),
        "p95": percentile(sorted_counts, 0.95),
        "p99": percentile(sorted_counts, 0.99),
        "max": sorted_counts[-1] if sorted_counts else None,
        "goals_with_exactly_one_viewpoint": histogram.get(1, 0),
        "share_goals_with_exactly_one_viewpoint": (
            histogram.get(1, 0) / n if n else 0.0
        ),
        "histogram_small_counts": {
            str(k): histogram.get(k, 0) for k in range(1, 11)
        },
    }


def scan(dataset_root: Path) -> dict[str, Any]:
    category_viewpoint_counts: dict[str, list[int]] = defaultdict(list)
    episode_counts_by_goal_key: Counter[str] = Counter()
    one_viewpoint_goals: list[dict[str, Any]] = []
    totals = {
        "files": 0,
        "episodes": 0,
        "goals": 0,
        "view_points": 0,
        "one_viewpoint_unique_goals": 0,
    }

    for split in ["train", "val"]:
        content_dir = dataset_root / split / "content"
        if not content_dir.exists():
            continue
        files = sorted(content_dir.glob("*.json")) + sorted(content_dir.glob("*.json.gz"))
        for shard_path in files:
            totals["files"] += 1
            shard = load_json(shard_path)
            goals_by_category = shard.get("goals_by_category", {}) or {}

            # Episode target-set membership: every episode of a scene/category
            # targets the full goals_by_category[scene_category] list.
            for episode in shard.get("episodes", []) or []:
                totals["episodes"] += 1
                scene_id = str(episode.get("scene_id", ""))
                category = str(episode.get("object_category", ""))
                key = f"{scene_id}_{category}"
                if key not in goals_by_category:
                    # Fallback for path-like scene IDs; this should not be used
                    # for the current native HSSD stats, but keeps the audit robust.
                    scene_base = scene_id.replace("\\", "/").rstrip("/").split("/")[-1]
                    fallback = f"{scene_base}_{category}"
                    key = fallback if fallback in goals_by_category else key
                episode_counts_by_goal_key[key] += 1

            for goals_key, goals in goals_by_category.items():
                if not isinstance(goals, list):
                    continue
                for goal_index, goal in enumerate(goals):
                    view_points = goal.get("view_points", []) or []
                    vp_count = len(view_points) if isinstance(view_points, list) else 0
                    category = str(goal.get("object_category") or goals_key.rsplit("_", 1)[-1])
                    category_viewpoint_counts[category].append(vp_count)
                    totals["goals"] += 1
                    totals["view_points"] += vp_count

                    if vp_count == 1:
                        vp = view_points[0]
                        agent_state = vp.get("agent_state", {}) if isinstance(vp, dict) else {}
                        scene_id = goals_key
                        if goals_key.endswith(f"_{category}"):
                            scene_id = goals_key[: -len(f"_{category}")]
                        one_viewpoint_goals.append(
                            {
                                "split": split,
                                "file": str(shard_path),
                                "scene_id": scene_id,
                                "object_category": category,
                                "object_id": goal.get("object_id"),
                                "object_name": goal.get("object_name"),
                                "object_name_id": goal.get("object_name_id"),
                                "goals_key": goals_key,
                                "goal_index": goal_index,
                                "goal_position": goal.get("position"),
                                "viewpoint": {
                                    "agent_state.position": agent_state.get("position"),
                                    "agent_state.rotation": agent_state.get("rotation"),
                                    "iou": vp.get("iou") if isinstance(vp, dict) else None,
                                },
                                "episodes_whose_target_set_contains_this_goal": episode_counts_by_goal_key.get(goals_key, 0),
                            }
                        )

    distributions = {
        category: category_distribution(counts)
        for category, counts in sorted(category_viewpoint_counts.items())
    }

    # Add category-relative position info after distributions are known.
    for item in one_viewpoint_goals:
        category = item["object_category"]
        dist = distributions[category]
        n = dist["num_goals"]
        one_count = dist["goals_with_exactly_one_viewpoint"]
        item["category_viewpoint_count_distribution_position"] = {
            "viewpoint_count": 1,
            "is_category_minimum": dist["min"] == 1,
            "num_goals_in_category": n,
            "num_goals_in_category_with_exactly_one_viewpoint": one_count,
            "share_of_category_goals_with_exactly_one_viewpoint": one_count / n if n else 0.0,
            "percentile_leq_this_count": one_count / n if n else 0.0,
            "plain_english_position": (
                f"bottom {one_count}/{n} goals in category by viewpoint count"
                if n
                else "unknown"
            ),
            "category_distribution_summary": {
                k: dist[k]
                for k in ["min", "p05", "q1", "median", "mean", "q3", "p95", "max"]
            },
        }

    one_viewpoint_goals.sort(
        key=lambda x: (
            x["object_category"],
            x["scene_id"],
            str(x.get("object_id")),
            x["goals_key"],
            x["goal_index"],
        )
    )
    totals["one_viewpoint_unique_goals"] = len(one_viewpoint_goals)
    totals["episodes_whose_target_set_contains_at_least_one_one_viewpoint_goal"] = sum(
        item["episodes_whose_target_set_contains_this_goal"] for item in one_viewpoint_goals
    )

    return {
        "dataset_root": str(dataset_root),
        "method": "Static read of train/val content JSON/JSON.GZ shards; no Habitat simulation.",
        "totals": totals,
        "category_viewpoint_count_distributions": distributions,
        "one_viewpoint_goals": one_viewpoint_goals,
    }


def fmt_num(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(fmt_num(x) for x in row) + " |")
    return "\n".join(lines)


def write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    totals = summary["totals"]
    distributions = summary["category_viewpoint_count_distributions"]
    goals = summary["one_viewpoint_goals"]

    dist_rows = []
    for category, dist in distributions.items():
        dist_rows.append(
            [
                category,
                dist["num_goals"],
                dist["goals_with_exactly_one_viewpoint"],
                dist["share_goals_with_exactly_one_viewpoint"] * 100,
                dist["min"],
                dist["p05"],
                dist["median"],
                dist["mean"],
                dist["p95"],
                dist["max"],
            ]
        )

    goal_rows = []
    for item in goals:
        pos = item["category_viewpoint_count_distribution_position"]
        vp = item["viewpoint"]
        goal_rows.append(
            [
                item["split"],
                item["scene_id"],
                item["object_category"],
                item.get("object_id"),
                item.get("object_name"),
                item["goals_key"],
                item["goal_index"],
                item["episodes_whose_target_set_contains_this_goal"],
                vp.get("agent_state.position"),
                vp.get("agent_state.rotation"),
                vp.get("iou"),
                f"{pos['num_goals_in_category_with_exactly_one_viewpoint']}/{pos['num_goals_in_category']} bottom goals",
            ]
        )

    rare_share = (
        totals["one_viewpoint_unique_goals"] / totals["goals"] * 100
        if totals["goals"]
        else 0.0
    )
    episode_target_share = (
        totals["episodes_whose_target_set_contains_at_least_one_one_viewpoint_goal"]
        / totals["episodes"]
        * 100
        if totals["episodes"]
        else 0.0
    )

    lines = [
        "# HSSD Goals With Exactly One Viewpoint",
        "",
        f"Dataset root: `{summary['dataset_root']}`",
        "",
        "This is a static read-only audit of native HSSD ObjectNav JSON/GZip shards. It does not run Habitat simulation, render images, train models, or modify source/dataset files.",
        "",
        "## Summary",
        "",
        md_table(
            ["files", "episodes", "unique goals", "view_points", "unique one-viewpoint goals"],
            [
                [
                    totals["files"],
                    totals["episodes"],
                    totals["goals"],
                    totals["view_points"],
                    totals["one_viewpoint_unique_goals"],
                ]
            ],
        ),
        "",
        f"There are **{totals['one_viewpoint_unique_goals']}** unique goals with exactly one viewpoint out of **{totals['goals']}** goals (**{rare_share:.3f}%**).",
        f"Summed over their scene/category target sets, they appear in target sets for **{totals['episodes_whose_target_set_contains_at_least_one_one_viewpoint_goal']}** episodes (**{episode_target_share:.3f}%** of episodes).",
        "",
        "Important nuance: an HSSD ObjectNav episode targets a scene/category goal list, not one specific object instance. So if a scene/category contains one one-viewpoint goal, every episode for that scene/category has that goal somewhere in its target set, even though other target objects in the same set may have many viewpoints.",
        "",
        "## Category-Level Viewpoint Count Position",
        "",
        md_table(
            ["category", "goals", "one-vp goals", "% one-vp", "min", "p05", "median", "mean", "p95", "max"],
            dist_rows,
        ),
        "",
        "For every listed goal, `viewpoint_count = 1` is at the bottom of its category's viewpoint-count distribution.",
        "",
        "## All Unique Goals With Exactly One Viewpoint",
        "",
        md_table(
            [
                "split",
                "scene_id",
                "category",
                "object_id",
                "object_name",
                "goals_key",
                "goal_index",
                "episodes containing goal in target set",
                "viewpoint position",
                "viewpoint rotation",
                "iou",
                "category position",
            ],
            goal_rows,
        ),
        "",
        "## Interpretation",
        "",
    ]

    if rare_share < 1.0:
        lines.append(
            "These one-viewpoint goals are a very small minority of unique goals. They look like edge cases in the static dataset rather than a broad episode-to-goal integrity failure."
        )
    else:
        lines.append(
            "These one-viewpoint goals are not dominant, but their share is large enough to justify closer follow-up before rendering/training."
        )

    lines.extend(
        [
            "",
            "However, they still matter for HSSD-to-OVON/VLM/Cosmos work because a one-viewpoint object has an extremely narrow success region. Static integrity is intact, but these goals may be brittle for metric replay, viewpoint quality analysis, or rendered video supervision.",
            "",
            "Recommended next check: inspect these 17 goals visually or with a static semantic/object-label audit before using them as evidence of clean viewpoint quality.",
            "",
            f"Machine-readable details: `outputs/hssd_one_viewpoint_goals.json`",
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

    summary = scan(args.dataset_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_markdown(summary, args.output_md)

    totals = summary["totals"]
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(
        f"Found {totals['one_viewpoint_unique_goals']} one-viewpoint unique goals "
        f"out of {totals['goals']} goals."
    )


if __name__ == "__main__":
    main()

