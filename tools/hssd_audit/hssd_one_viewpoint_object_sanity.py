#!/usr/bin/env python3
"""Static object/label sanity check for HSSD one-viewpoint goals.

Inputs:
  - outputs/hssd_one_viewpoint_goals.json
  - native HSSD ObjectNav JSON/JSON.GZ shards referenced by that file

This script does not import Habitat, render, launch simulation, or modify
dataset/source files.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_INPUT = Path("outputs/hssd_one_viewpoint_goals.json")
DEFAULT_OUTPUT_JSON = Path("outputs/hssd_one_viewpoint_object_sanity.json")
DEFAULT_OUTPUT_MD = Path("outputs/hssd_one_viewpoint_object_sanity.md")

METADATA_CANDIDATE_FIELDS = [
    "object_semantic_id",
    "semantic_id",
    "object_template",
    "object_template_handle",
    "object_handle",
    "handle",
    "template_handle",
    "object_type",
    "category",
    "bbox",
    "bounding_box",
    "aabb",
    "dimensions",
    "size",
    "extent",
]

BBOX_FIELDS = ["bbox", "bounding_box", "aabb"]
DIMENSION_FIELDS = ["dimensions", "size", "extent"]


def load_json(path: Path) -> dict[str, Any]:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile_rank(values: list[float], x: float | None) -> float | None:
    if x is None or not values:
        return None
    leq = sum(1 for v in values if v <= x)
    return leq / len(values)


def summarize_numbers(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "median": float(median(values)),
        "mean": float(mean(values)),
        "max": max(values),
    }


def extract_present_metadata(goal: dict[str, Any]) -> dict[str, Any]:
    return {k: goal.get(k) for k in METADATA_CANDIDATE_FIELDS if k in goal}


def first_present(goal: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in goal:
            return goal.get(key)
    return None


def detect_name_semantic_hint(object_name: Any) -> str | None:
    if not isinstance(object_name, str):
        return None
    # HSSD object_name values in these shards are usually hash-like asset
    # handles, e.g. "<hex>_:0000" or "<hex>_part_3_:0000". Do not treat
    # accidental substrings such as "bed" inside a hex digest as semantic text.
    handle = object_name.split(":", 1)[0].lower()
    normalized = handle
    for token in ["_part_0", "_part_1", "_part_2", "_part_3", "_part_4", "_part_5", "_part_6", "_part_7", "_part_8", "_part_9"]:
        normalized = normalized.replace(token, "")
    normalized = normalized.replace("_", "")
    if len(normalized) >= 16 and all(ch in "0123456789abcdef" for ch in normalized):
        return None
    low = object_name.lower()
    hints = [
        "bed",
        "chair",
        "couch",
        "sofa",
        "plant",
        "potted",
        "toilet",
        "tv",
        "television",
    ]
    found = [h for h in hints if h in low]
    return ",".join(found) if found else None


def assess_goal(
    *,
    goal_record: dict[str, Any],
    raw_goal: dict[str, Any],
    raw_viewpoint: dict[str, Any],
    category_y_values: dict[str, list[float]],
) -> dict[str, Any]:
    object_category = raw_goal.get("object_category")
    expected_category = goal_record.get("object_category")
    goals_key = goal_record.get("goals_key")
    issues: list[str] = []
    notes: list[str] = []

    if object_category != expected_category:
        issues.append("goal.object_category differs from one-viewpoint record category")
    if isinstance(goals_key, str) and expected_category and not goals_key.endswith(f"_{expected_category}"):
        issues.append("goals_key does not end with expected object_category")

    object_name = raw_goal.get("object_name")
    semantic_hint = detect_name_semantic_hint(object_name)
    if semantic_hint:
        notes.append(f"object_name contains readable semantic hint(s): {semantic_hint}")
        if expected_category == "potted_plant" and "plant" not in semantic_hint and "potted" not in semantic_hint:
            issues.append("object_name contains a readable hint that does not look plant-related")
    else:
        notes.append("object_name has no human-readable category hint; semantic label cannot be validated from name alone")

    bbox_value = first_present(raw_goal, BBOX_FIELDS)
    dimensions_value = first_present(raw_goal, DIMENSION_FIELDS)
    if bbox_value is None and dimensions_value is None:
        notes.append("no bbox/dimensions fields in goal schema")

    position = raw_goal.get("position")
    pos_y = None
    if isinstance(position, list) and len(position) >= 2:
        pos_y = safe_float(position[1])
    else:
        issues.append("goal position missing or malformed")

    y_values = category_y_values.get(str(expected_category), [])
    y_rank = percentile_rank(y_values, pos_y)

    agent_state = raw_viewpoint.get("agent_state", {}) if isinstance(raw_viewpoint, dict) else {}
    viewpoint_position = agent_state.get("position")
    viewpoint_rotation = agent_state.get("rotation")
    viewpoint_y = None
    if isinstance(viewpoint_position, list) and len(viewpoint_position) >= 2:
        viewpoint_y = safe_float(viewpoint_position[1])

    return {
        "scene_id": goal_record.get("scene_id"),
        "split": goal_record.get("split"),
        "file": goal_record.get("file"),
        "goals_key": goals_key,
        "goal_index": goal_record.get("goal_index"),
        "object_category": expected_category,
        "raw_goal_object_category": object_category,
        "object_id": raw_goal.get("object_id"),
        "object_name": object_name,
        "object_name_id": raw_goal.get("object_name_id"),
        "object_semantic_id": raw_goal.get("object_semantic_id", raw_goal.get("semantic_id")),
        "object_template": raw_goal.get("object_template", raw_goal.get("object_template_handle")),
        "object_handle": raw_goal.get("object_handle", raw_goal.get("handle")),
        "object_metadata_present": extract_present_metadata(raw_goal),
        "object_metadata_missing_from_goal_schema": [
            k for k in METADATA_CANDIDATE_FIELDS if k not in raw_goal
        ],
        "object_position": position,
        "object_position_y": pos_y,
        "object_position_y_percentile_within_category": y_rank,
        "object_bounding_box": bbox_value,
        "object_dimensions": dimensions_value,
        "single_viewpoint_position": viewpoint_position,
        "single_viewpoint_rotation": viewpoint_rotation,
        "single_viewpoint_iou": raw_viewpoint.get("iou") if isinstance(raw_viewpoint, dict) else None,
        "single_viewpoint_agent_state_full": agent_state,
        "single_viewpoint_full_record": raw_viewpoint,
        "episode_count_referencing_this_goal": goal_record.get(
            "episodes_whose_target_set_contains_this_goal"
        ),
        "sanity_issues": issues,
        "sanity_notes": notes,
        "raw_goal_fields": sorted(raw_goal.keys()),
    }


def scan(input_path: Path) -> dict[str, Any]:
    one_vp_summary = load_json(input_path)
    records = one_vp_summary.get("one_viewpoint_goals", [])

    shard_cache: dict[str, dict[str, Any]] = {}

    # First pass: collect all goal object-position y values per category from
    # the original files referenced by one-viewpoint records. This is enough to
    # contextualize the 17 cases within their categories in the scanned files.
    # If the input summary was produced from the whole dataset, referenced files
    # are a targeted subset, so we also expose this scope explicitly.
    category_y_values_targeted_files: dict[str, list[float]] = defaultdict(list)
    for record in records:
        file_path = str(record["file"])
        if file_path not in shard_cache:
            shard_cache[file_path] = load_json(Path(file_path))
        shard = shard_cache[file_path]
        for goals in (shard.get("goals_by_category", {}) or {}).values():
            if not isinstance(goals, list):
                continue
            for goal in goals:
                category = str(goal.get("object_category"))
                position = goal.get("position")
                if isinstance(position, list) and len(position) >= 2:
                    y = safe_float(position[1])
                    if y is not None:
                        category_y_values_targeted_files[category].append(y)

    detailed_goals: list[dict[str, Any]] = []
    category_counter = Counter()
    scene_counter = Counter()
    potted_scene_counter = Counter()
    potted_object_y_values: list[float] = []
    potted_viewpoint_y_values: list[float] = []
    potted_iou_values: list[float] = []

    for record in records:
        file_path = str(record["file"])
        shard = shard_cache[file_path]
        goals_key = record["goals_key"]
        goal_index = int(record["goal_index"])
        raw_goal = shard["goals_by_category"][goals_key][goal_index]
        view_points = raw_goal.get("view_points", []) or []
        raw_viewpoint = view_points[0] if view_points else {}

        item = assess_goal(
            goal_record=record,
            raw_goal=raw_goal,
            raw_viewpoint=raw_viewpoint,
            category_y_values=category_y_values_targeted_files,
        )
        detailed_goals.append(item)

        category = str(item["object_category"])
        category_counter[category] += 1
        scene_counter[str(item["scene_id"])] += 1
        if category == "potted_plant":
            potted_scene_counter[str(item["scene_id"])] += 1
            if item["object_position_y"] is not None:
                potted_object_y_values.append(item["object_position_y"])
            vp_pos = item["single_viewpoint_position"]
            if isinstance(vp_pos, list) and len(vp_pos) >= 2:
                y = safe_float(vp_pos[1])
                if y is not None:
                    potted_viewpoint_y_values.append(y)
            iou = safe_float(item.get("single_viewpoint_iou"))
            if iou is not None:
                potted_iou_values.append(iou)

    potted_cases = [g for g in detailed_goals if g["object_category"] == "potted_plant"]
    all_issue_counts = Counter(issue for g in detailed_goals for issue in g["sanity_issues"])
    potted_issue_counts = Counter(issue for g in potted_cases for issue in g["sanity_issues"])

    potted_missing_bbox = sum(
        1 for g in potted_cases if g["object_bounding_box"] is None
    )
    potted_missing_dimensions = sum(
        1 for g in potted_cases if g["object_dimensions"] is None
    )
    potted_missing_position = sum(
        1 for g in potted_cases if g["object_position"] is None
    )

    return {
        "input": str(input_path),
        "method": "Static read of one-viewpoint-goal summary and original HSSD JSON/GZip shards; no Habitat simulation or rendering.",
        "totals": {
            "one_viewpoint_goals": len(detailed_goals),
            "potted_plant_one_viewpoint_goals": len(potted_cases),
            "categories": dict(sorted(category_counter.items())),
            "scenes_with_one_viewpoint_goals": len(scene_counter),
            "potted_plant_scenes": len(potted_scene_counter),
            "sanity_issue_counts_all": dict(sorted(all_issue_counts.items())),
            "sanity_issue_counts_potted_plant": dict(sorted(potted_issue_counts.items())),
        },
        "potted_plant_pattern_summary": {
            "scene_counts": dict(sorted(potted_scene_counter.items())),
            "object_position_y": summarize_numbers(potted_object_y_values),
            "viewpoint_position_y": summarize_numbers(potted_viewpoint_y_values),
            "single_viewpoint_iou": summarize_numbers(potted_iou_values),
            "missing_bbox_count": potted_missing_bbox,
            "missing_dimensions_count": potted_missing_dimensions,
            "missing_position_count": potted_missing_position,
            "metadata_scope_note": "Native goal records expose object_id/object_name/object_category/position/view_points, but do not expose semantic-readable template, bbox, or dimensions in these cases.",
        },
        "detailed_goals": detailed_goals,
    }


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, dict)):
        return "`" + json.dumps(value, ensure_ascii=False) + "`"
    if value is None:
        return ""
    return str(value)


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(fmt(x) for x in row) + " |")
    return "\n".join(lines)


def write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    totals = summary["totals"]
    potted = summary["potted_plant_pattern_summary"]
    details = summary["detailed_goals"]

    rows = []
    for g in details:
        rows.append(
            [
                g["split"],
                g["scene_id"],
                g["object_category"],
                g["object_id"],
                g["object_name"],
                g["object_position"],
                g["single_viewpoint_position"],
                g["single_viewpoint_rotation"],
                g["single_viewpoint_iou"],
                g["episode_count_referencing_this_goal"],
                "; ".join(g["sanity_issues"]) if g["sanity_issues"] else "none",
            ]
        )

    potted_rows = []
    for g in details:
        if g["object_category"] != "potted_plant":
            continue
        potted_rows.append(
            [
                g["scene_id"],
                g["object_id"],
                g["object_name"],
                g["object_position"],
                g["object_position_y"],
                g["single_viewpoint_position"],
                g["single_viewpoint_iou"],
                g["episode_count_referencing_this_goal"],
                "yes" if g["object_bounding_box"] is None else "no",
                "yes" if g["object_dimensions"] is None else "no",
                "; ".join(g["sanity_notes"]),
            ]
        )

    lines = [
        "# HSSD One-Viewpoint Goal Object/Label Sanity Check",
        "",
        f"Input: `{summary['input']}`",
        "",
        "This is a static read-only audit. It reopens the original HSSD ObjectNav dataset files for the 17 exactly-one-viewpoint goals and inspects the goal records. It does not run Habitat simulation, render images, or modify dataset/source files.",
        "",
        "## Summary",
        "",
        md_table(
            ["one-vp goals", "potted_plant goals", "scenes", "potted scenes"],
            [
                [
                    totals["one_viewpoint_goals"],
                    totals["potted_plant_one_viewpoint_goals"],
                    totals["scenes_with_one_viewpoint_goals"],
                    totals["potted_plant_scenes"],
                ]
            ],
        ),
        "",
        "Category counts:",
        "",
        md_table(
            ["category", "one-vp goals"],
            [[k, v] for k, v in totals["categories"].items()],
        ),
        "",
        "## What Metadata Exists in These Goal Records",
        "",
        "For these 17 native HSSD goal records, the useful static fields are mostly `object_id`, `object_name`, `object_category`, `position`, and `view_points`. The inspected records do **not** expose human-readable object templates, object handles, semantic IDs, bounding boxes, or dimensions in the goal schema.",
        "",
        "That means this audit can catch obvious internal inconsistencies, such as category mismatches or missing positions, but it cannot prove that a hash-like `object_name` is truly a potted plant without scene metadata or visualization.",
        "",
        "## All 17 Goals",
        "",
        md_table(
            [
                "split",
                "scene_id",
                "category",
                "object_id",
                "object_name",
                "object position",
                "viewpoint position",
                "viewpoint rotation",
                "iou",
                "episode count",
                "sanity issues",
            ],
            rows,
        ),
        "",
        "## Potted Plant Focus",
        "",
        md_table(
            ["scene_id", "count"],
            [[k, v] for k, v in potted["scene_counts"].items()],
        ),
        "",
        "Potted plant numeric summary:",
        "",
        md_table(
            ["field", "count", "min", "median", "mean", "max"],
            [
                [
                    "object_position_y",
                    potted["object_position_y"]["count"],
                    potted["object_position_y"]["min"],
                    potted["object_position_y"]["median"],
                    potted["object_position_y"]["mean"],
                    potted["object_position_y"]["max"],
                ],
                [
                    "viewpoint_position_y",
                    potted["viewpoint_position_y"]["count"],
                    potted["viewpoint_position_y"]["min"],
                    potted["viewpoint_position_y"]["median"],
                    potted["viewpoint_position_y"]["mean"],
                    potted["viewpoint_position_y"]["max"],
                ],
                [
                    "single_viewpoint_iou",
                    potted["single_viewpoint_iou"]["count"],
                    potted["single_viewpoint_iou"]["min"],
                    potted["single_viewpoint_iou"]["median"],
                    potted["single_viewpoint_iou"]["mean"],
                    potted["single_viewpoint_iou"]["max"],
                ],
            ],
        ),
        "",
        f"Potted plant records missing bbox: **{potted['missing_bbox_count']} / {totals['potted_plant_one_viewpoint_goals']}**.",
        f"Potted plant records missing dimensions: **{potted['missing_dimensions_count']} / {totals['potted_plant_one_viewpoint_goals']}**.",
        f"Potted plant records missing object position: **{potted['missing_position_count']} / {totals['potted_plant_one_viewpoint_goals']}**.",
        "",
        md_table(
            [
                "scene_id",
                "object_id",
                "object_name",
                "object position",
                "object y",
                "viewpoint position",
                "iou",
                "episode count",
                "missing bbox",
                "missing dimensions",
                "notes",
            ],
            potted_rows,
        ),
        "",
        "## Static Sanity Interpretation",
        "",
    ]

    if not totals["sanity_issue_counts_all"]:
        lines.append(
            "No obvious internal category/metadata inconsistency was detected from the fields available in the native goal records."
        )
    else:
        lines.append(
            "Static sanity issues were detected: "
            + json.dumps(totals["sanity_issue_counts_all"], ensure_ascii=False)
        )

    lines.extend(
        [
            "",
            "The potted_plant one-viewpoint cases are spread across several scenes rather than concentrated in one scene. A few scenes have two potted_plant one-viewpoint goals, but there is no single-scene collapse pattern.",
            "",
            "The available goal schema does not include bbox/dimensions, so this static audit cannot determine whether these are physically tiny objects. The `object_position_y` values are present and not obviously missing; some are low and some are around typical tabletop/object heights, but without floor/object geometry this is not enough to call them abnormal.",
            "",
            "Many `object_name` values are hash-like asset handles with no readable category word. Therefore, no obvious label mismatch is visible from goal metadata alone, but semantic correctness remains unverified.",
            "",
            "## Conclusion",
            "",
            "These one-viewpoint goals look most like rare, hard or brittle target cases in the static ObjectNav metadata. They do **not** currently look like an obvious label/object metadata bug from the JSON fields alone. However, because bbox/dimensions and human-readable object templates are absent, this cannot settle whether the potted_plant labels are visually correct. The right next step is visualization or a separate scene-metadata lookup, not training.",
            "",
            f"Machine-readable details: `outputs/hssd_one_viewpoint_object_sanity.json`",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    summary = scan(args.input)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown(summary, args.output_md)

    totals = summary["totals"]
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(
        "Checked "
        f"{totals['one_viewpoint_goals']} one-viewpoint goals; "
        f"{totals['potted_plant_one_viewpoint_goals']} are potted_plant."
    )


if __name__ == "__main__":
    main()

