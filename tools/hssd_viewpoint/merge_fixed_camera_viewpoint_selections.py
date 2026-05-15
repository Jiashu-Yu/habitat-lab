#!/usr/bin/env python3
"""Merge fixed-camera viewpoint selection outputs.

Use this after a broad small/full run plus targeted retry runs. Later inputs
override earlier inputs for the same object_uid, so a targeted retry can replace
an earlier failing object record.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_OUTPUT_DIR = Path("outputs/hssd_fixed_camera_viewpoint_merged_selection")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge fixed_camera_viewpoint_selection.json files, preferring "
            "later files for duplicate object_uid records."
        )
    )
    parser.add_argument(
        "selection_jsons",
        nargs="+",
        type=Path,
        help=(
            "Selection JSON files. Put the broad/base run first and targeted "
            "retry selections later."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for merged JSON/CSV/Markdown outputs.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def object_uid_from_record(record: Dict[str, Any]) -> str:
    return str(record.get("object_uid") or "")


def object_uid_from_candidate(row: Dict[str, Any]) -> str:
    return str(row.get("object_uid") or "")


def recompute_summary(
    object_records_by_uid: Dict[str, Dict[str, Any]],
    candidate_rows_by_uid: Dict[str, List[Dict[str, Any]]],
    prototype_records_by_uid: Dict[str, Dict[str, Any]],
    sources: List[str],
) -> Dict[str, Any]:
    candidate_status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    object_status_counts: Counter[str] = Counter()
    category_summary: Dict[str, Counter[str]] = defaultdict(Counter)

    for rows in candidate_rows_by_uid.values():
        for row in rows:
            status = str(row.get("selection_status") or "unknown")
            candidate_status_counts[status] += 1
            for reason in row.get("selection_reasons") or []:
                reason_counts[str(reason)] += 1

    for record in object_records_by_uid.values():
        status = str(record.get("status") or "unknown")
        category = str(record.get("category") or "unknown")
        object_status_counts[status] += 1
        category_summary[category]["objects"] += 1
        category_summary[category][status] += 1
        category_summary[category]["accepted_viewpoints"] += int(
            record.get("accepted_count") or 0
        )
        category_summary[category]["review_viewpoints"] += int(
            record.get("review_count") or 0
        )
        category_summary[category]["rejected_candidates"] += int(
            record.get("rejected_count") or 0
        )

    return {
        "sources": sources,
        "merge_policy": "later selection_jsons override earlier records with the same object_uid",
        "candidate_status_counts": dict(candidate_status_counts),
        "selection_reason_counts": dict(reason_counts),
        "object_status_counts": dict(object_status_counts),
        "category_summary": {
            cat: dict(counter) for cat, counter in sorted(category_summary.items())
        },
        "object_records": sorted(
            object_records_by_uid.values(),
            key=lambda r: (
                str(r.get("category")),
                str(r.get("scene_id")),
                int(r.get("instance_index") or -1),
            ),
        ),
        "prototype_viewpoints_by_object": {
            uid: prototype_records_by_uid[uid]
            for uid in sorted(prototype_records_by_uid)
            if uid in object_records_by_uid
        },
    }


def prototype_viewpoint_from_candidate(row: Dict[str, Any]) -> Dict[str, Any]:
    agent_state = row.get("agent_state") or {}
    return {
        "agent_state": {
            "position": agent_state.get("position") or row.get("navigable_position"),
            "rotation": agent_state.get("rotation"),
        },
        "iou": None,
        "metadata": {
            "source": "hssd_fixed_camera_viewpoint_prototype",
            "category": row.get("category"),
            "scene_id": row.get("scene_id"),
            "instance_index": row.get("instance_index"),
            "candidate_index": row.get("candidate_index"),
            "visible_pixels": row.get("visible_pixels"),
            "image_fraction": row.get("image_fraction"),
            "vis_ratio": row.get("vis_ratio"),
            "bbox_frac": row.get("bbox_frac"),
            "threshold_profile": row.get("threshold_profile"),
            "threshold_label": row.get("threshold_label"),
            "candidate_min_image_fraction": row.get("candidate_min_image_fraction"),
            "candidate_min_bbox_fraction": row.get("candidate_min_bbox_fraction"),
            "selection_distance": row.get("selection_distance"),
            "selection_distance_source": row.get("selection_distance_source"),
            "distance_to_object": row.get("distance_to_object"),
            "distance_to_bbox": row.get("distance_to_bbox"),
            "selection_status": row.get("selection_status"),
            "selection_reasons": row.get("selection_reasons"),
            "rigid_object_handle": row.get("rigid_object_handle"),
            "navigable_island_radius": row.get("navigable_island_radius"),
            "navigable_island_id": row.get("navigable_island_id"),
            "navigable_island_error": row.get("navigable_island_error"),
            "min_navigable_island_radius": row.get(
                "min_navigable_island_radius"
            ),
            "snapped_inside_target_bbox_xz": row.get(
                "snapped_inside_target_bbox_xz"
            ),
            "reject_inside_target_bbox_xz": row.get(
                "reject_inside_target_bbox_xz"
            ),
            "category_source": row.get("category_source"),
            "canonical_category": row.get("canonical_category"),
            "canonical_category_source": row.get("canonical_category_source"),
            "condensed_category": row.get("condensed_category"),
            "primary_semantic_category": row.get("primary_semantic_category"),
            "main_category": row.get("main_category"),
            "clean_category": row.get("clean_category"),
            "super_category": row.get("super_category"),
            "region_label": row.get("region_label"),
            "region_name": row.get("region_name"),
            "translation": row.get("translation"),
            "object_center_static_approx": row.get("object_center_static_approx"),
            "object_bbox_static_approx": row.get("object_bbox_static_approx"),
            "object_name": row.get("object_name"),
            "objects_json_name": row.get("objects_json_name"),
            "wnsynsetkey": row.get("wnsynsetkey"),
            "main_wnsynsetkey": row.get("main_wnsynsetkey"),
            "has_multiple_objects": row.get("has_multiple_objects"),
            "is_articulatable": row.get("is_articulatable"),
        },
    }


def object_metadata_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {
        "status",
        "accepted_count",
        "review_count",
        "rejected_count",
        "candidate_count",
        "accepted_viewpoints",
        "review_viewpoints",
    }
    return {key: value for key, value in record.items() if key not in excluded}


def reconstruct_prototype_record(
    record: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    accepted_rows = [
        row for row in rows if row.get("selection_status") == "accepted"
    ]
    return {
        "object": object_metadata_from_record(record),
        "object_status": record.get("status"),
        "view_points": [
            prototype_viewpoint_from_candidate(row) for row in accepted_rows
        ],
    }


def write_category_csv(path: Path, summary: Dict[str, Any]) -> None:
    fields = [
        "category",
        "objects",
        "pass",
        "review_needed",
        "fail",
        "accepted_viewpoints",
        "review_viewpoints",
        "rejected_candidates",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for category, stats in summary["category_summary"].items():
            row = {"category": category}
            row.update({field: stats.get(field, 0) for field in fields if field != "category"})
            writer.writerow(row)


def write_object_csv(path: Path, summary: Dict[str, Any]) -> None:
    fields = [
        "status",
        "category",
        "scene_id",
        "instance_index",
        "object_name",
        "template_name",
        "candidate_count",
        "accepted_count",
        "review_count",
        "rejected_count",
        "accepted_candidate_indices",
        "review_candidate_indices",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in summary["object_records"]:
            accepted = record.get("accepted_viewpoints") or []
            review = record.get("review_viewpoints") or []
            writer.writerow(
                {
                    "status": record.get("status"),
                    "category": record.get("category"),
                    "scene_id": record.get("scene_id"),
                    "instance_index": record.get("instance_index"),
                    "object_name": record.get("object_name"),
                    "template_name": record.get("template_name"),
                    "candidate_count": record.get("candidate_count"),
                    "accepted_count": record.get("accepted_count"),
                    "review_count": record.get("review_count"),
                    "rejected_count": record.get("rejected_count"),
                    "accepted_candidate_indices": json.dumps(
                        [row.get("candidate_index") for row in accepted],
                        ensure_ascii=False,
                    ),
                    "review_candidate_indices": json.dumps(
                        [row.get("candidate_index") for row in review],
                        ensure_ascii=False,
                    ),
                }
            )


def build_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# Merged Fixed-camera Viewpoint Selection",
        "",
        "This merges selection outputs from broad and targeted runs. It does not modify HSSD dataset shards.",
        "",
        "## Summary",
        "",
        f"- sources: {summary['sources']}",
        f"- merge policy: {summary['merge_policy']}",
        f"- candidate status counts: {summary['candidate_status_counts']}",
        f"- object status counts: {summary['object_status_counts']}",
        f"- selection reason counts: {summary['selection_reason_counts']}",
        "",
        "## Category Summary",
        "",
        "| category | objects | pass | review_needed | fail | accepted viewpoints | review viewpoints |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category, stats in summary["category_summary"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    category,
                    str(stats.get("objects", 0)),
                    str(stats.get("pass", 0)),
                    str(stats.get("review_needed", 0)),
                    str(stats.get("fail", 0)),
                    str(stats.get("accepted_viewpoints", 0)),
                    str(stats.get("review_viewpoints", 0)),
                ]
            )
            + " |"
        )

    failing = [r for r in summary["object_records"] if r.get("status") == "fail"]
    review_needed = [
        r for r in summary["object_records"] if r.get("status") == "review_needed"
    ]

    lines.extend(["", "## Remaining Failing Objects", ""])
    lines.extend(object_table(failing))
    lines.extend(["", "## Remaining Review-needed Objects", ""])
    lines.extend(object_table(review_needed))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- If all objects are `pass`, the sampled expanded categories have at least the requested number of accepted fixed-camera, sentinel-verified viewpoints.",
            "- `review_viewpoints` are retained as diagnostics and are not counted as accepted unless explicitly selected upstream.",
            "- This merged report is a feasibility artifact; it is not yet a rewritten Habitat ObjectNav dataset.",
        ]
    )
    return "\n".join(lines) + "\n"


def object_table(records: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "| status | category | scene | instance | object name | accepted | review | rejected |",
        "|---|---|---|---:|---|---:|---:|---:|",
    ]
    if not records:
        lines.append("| none |  |  |  |  |  |  |  |")
        return lines
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(record.get("status")),
                    str(record.get("category")),
                    str(record.get("scene_id")),
                    str(record.get("instance_index")),
                    str(record.get("object_name")),
                    str(record.get("accepted_count")),
                    str(record.get("review_count")),
                    str(record.get("rejected_count")),
                ]
            )
            + " |"
        )
    return lines


def main() -> None:
    args = parse_args()
    object_records_by_uid: Dict[str, Dict[str, Any]] = {}
    candidate_rows_by_uid: Dict[str, List[Dict[str, Any]]] = {}
    prototype_records_by_uid: Dict[str, Dict[str, Any]] = {}
    sources: List[str] = []

    for path in args.selection_jsons:
        data = load_json(path)
        sources.append(str(path))
        summary = data.get("summary") or {}
        prototypes = summary.get("prototype_viewpoints_by_object") or {}
        for record in summary.get("object_records") or []:
            uid = object_uid_from_record(record)
            if not uid:
                continue
            object_records_by_uid[uid] = record
            prototype_records_by_uid.pop(uid, None)
        grouped_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in data.get("candidate_rows") or []:
            uid = object_uid_from_candidate(row)
            if uid:
                grouped_rows[uid].append(row)
        for uid, rows in grouped_rows.items():
            candidate_rows_by_uid[uid] = rows
        for uid, prototype_record in prototypes.items():
            uid = str(uid)
            if uid in object_records_by_uid:
                prototype_records_by_uid[uid] = prototype_record

    for uid, record in object_records_by_uid.items():
        if uid in prototype_records_by_uid:
            continue
        prototype_records_by_uid[uid] = reconstruct_prototype_record(
            record,
            candidate_rows_by_uid.get(uid, []),
        )

    summary = recompute_summary(
        object_records_by_uid,
        candidate_rows_by_uid,
        prototype_records_by_uid,
        sources,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "fixed_camera_viewpoint_merged_selection.json"
    category_csv = args.output_dir / "fixed_camera_viewpoint_merged_categories.csv"
    object_csv = args.output_dir / "fixed_camera_viewpoint_merged_objects.csv"
    md_path = args.output_dir / "fixed_camera_viewpoint_merged_selection.md"

    merged_rows: List[Dict[str, Any]] = []
    for rows in candidate_rows_by_uid.values():
        merged_rows.extend(rows)

    json_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "candidate_rows": merged_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_category_csv(category_csv, summary)
    write_object_csv(object_csv, summary)
    md_path.write_text(build_markdown(summary), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {category_csv}")
    print(f"Wrote {object_csv}")
    print(f"Wrote {md_path}")
    print(
        json.dumps(
            {
                "candidate_status_counts": summary["candidate_status_counts"],
                "object_status_counts": summary["object_status_counts"],
                "category_summary": summary["category_summary"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
