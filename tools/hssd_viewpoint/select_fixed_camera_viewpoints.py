#!/usr/bin/env python3
"""Select high-quality fixed-camera HSSD viewpoint candidates.

This script is intentionally static: it reads the prototype JSON output and
does not import Habitat-Sim, render, train, or modify any dataset shard.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_INPUT = Path(
    "outputs/hssd_fixed_camera_viewpoint_prototype/"
    "hssd_fixed_camera_viewpoint_prototype.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/hssd_fixed_camera_viewpoint_selection")

DEFAULT_REJECT_FLAGS = (
    "full_frame_sentinel_mask",
    "near_full_frame_bbox",
    "tiny_sentinel_mask",
)
DEFAULT_REVIEW_FLAGS = ("very_large_sentinel_mask",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Classify fixed-camera viewpoint candidates as accepted, review, "
            "or rejected using sentinel visibility and mask-quality flags."
        )
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=DEFAULT_INPUT,
        help="Prototype JSON output to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for selection JSON/CSV/Markdown outputs.",
    )
    parser.add_argument("--min-visible-pixels", type=int, default=1000)
    parser.add_argument("--min-image-fraction", type=float, default=0.005)
    parser.add_argument("--max-distance", type=float, default=3.0)
    parser.add_argument(
        "--max-accepted-image-fraction",
        type=float,
        default=0.50,
        help=(
            "Candidates at or above this fraction are kept for review rather "
            "than accepted by default."
        ),
    )
    parser.add_argument("--min-viewpoints-per-object", type=int, default=3)
    parser.add_argument(
        "--reject-flags",
        nargs="*",
        default=list(DEFAULT_REJECT_FLAGS),
        help="sentinel_mask_quality_flags that hard-reject a candidate.",
    )
    parser.add_argument(
        "--review-flags",
        nargs="*",
        default=list(DEFAULT_REVIEW_FLAGS),
        help="sentinel_mask_quality_flags that require manual review.",
    )
    parser.add_argument(
        "--include-review-in-prototype-viewpoints",
        action="store_true",
        help=(
            "Include review candidates in the exported prototype viewpoint "
            "records. By default only accepted candidates are exported."
        ),
    )
    parser.add_argument("--top-k", type=int, default=80)
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_rows(data: Dict[str, Any]) -> Iterable[Tuple[Dict[str, Any], Dict[str, Any]]]:
    for obj_result in data.get("object_results") or []:
        obj = obj_result.get("object") or {}
        for candidate in obj_result.get("candidate_results") or []:
            yield obj, candidate


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def object_key(obj: Dict[str, Any]) -> str:
    return (
        f"{obj.get('scene_id')}|{obj.get('instance_index')}|"
        f"{obj.get('category')}|{obj.get('template_name')}"
    )


def classify_candidate(
    candidate: Dict[str, Any],
    args: argparse.Namespace,
) -> Tuple[str, List[str]]:
    reasons: List[str] = []

    if candidate.get("candidate_error"):
        reasons.append("candidate_error")
        return "rejected", reasons
    if candidate.get("rejected"):
        reasons.append(str(candidate.get("rejection_reason") or "candidate_rejected"))
        return "rejected", reasons

    visible_pixels = to_int(
        candidate.get("visible_pixels", candidate.get("visible_pixel_count", 0))
    )
    image_fraction = to_float(
        candidate.get("image_fraction", candidate.get("sentinel_image_fraction", 0.0))
    )
    distance = to_float(candidate.get("distance_to_object"), default=999999.0)
    flags = set(str(f) for f in (candidate.get("sentinel_mask_quality_flags") or []))
    reject_flags = set(args.reject_flags)
    review_flags = set(args.review_flags)

    hard_flags = sorted(flags & reject_flags)
    if hard_flags:
        reasons.extend([f"reject_flag:{flag}" for flag in hard_flags])
        return "rejected", reasons
    if visible_pixels <= 0:
        reasons.append("zero_visible_pixels")
        return "rejected", reasons
    if visible_pixels < args.min_visible_pixels:
        reasons.append(f"visible_pixels<{args.min_visible_pixels}")
        return "rejected", reasons
    if image_fraction < args.min_image_fraction:
        reasons.append(f"image_fraction<{args.min_image_fraction}")
        return "rejected", reasons
    if distance > args.max_distance:
        reasons.append(f"distance>{args.max_distance}")
        return "rejected", reasons

    soft_flags = sorted(flags & review_flags)
    if soft_flags:
        reasons.extend([f"review_flag:{flag}" for flag in soft_flags])
        return "review", reasons
    if image_fraction >= args.max_accepted_image_fraction:
        reasons.append(f"image_fraction>={args.max_accepted_image_fraction}")
        return "review", reasons

    reasons.append("passes_quality_filters")
    return "accepted", reasons


def debug_paths(candidate: Dict[str, Any], suffix: str) -> List[str]:
    return [
        str(path)
        for path in candidate.get("debug_images") or []
        if str(path).endswith(suffix)
    ]


def flatten_candidate(
    obj: Dict[str, Any],
    candidate: Dict[str, Any],
    status: str,
    reasons: List[str],
) -> Dict[str, Any]:
    visible_pixels = to_int(
        candidate.get("visible_pixels", candidate.get("visible_pixel_count", 0))
    )
    image_fraction = to_float(
        candidate.get("image_fraction", candidate.get("sentinel_image_fraction", 0.0))
    )
    return {
        "selection_status": status,
        "selection_reasons": reasons,
        "category": obj.get("category"),
        "scene_id": obj.get("scene_id"),
        "instance_index": obj.get("instance_index"),
        "object_name": obj.get("object_name"),
        "template_name": obj.get("template_name"),
        "object_uid": obj.get("object_uid"),
        "candidate_index": candidate.get("candidate_index"),
        "visible_pixels": visible_pixels,
        "image_fraction": image_fraction,
        "distance_to_object": candidate.get("distance_to_object"),
        "planar_distance_to_object_xz": candidate.get("planar_distance_to_object_xz"),
        "sentinel_bbox": candidate.get("sentinel_bbox"),
        "sentinel_bbox_area_fraction": candidate.get("sentinel_bbox_area_fraction"),
        "sentinel_mask_quality_flags": candidate.get("sentinel_mask_quality_flags")
        or [],
        "semantic_mapping_status": candidate.get("semantic_mapping_status"),
        "rigid_object_handle": candidate.get("rigid_object_handle"),
        "agent_state": candidate.get("agent_state"),
        "navigable_position": candidate.get("navigable_position"),
        "debug_review_images": debug_paths(candidate, "_review.png"),
        "debug_overlay_images": debug_paths(candidate, "_overlay.png"),
        "debug_images": candidate.get("debug_images") or [],
    }


def prototype_viewpoint(row: Dict[str, Any]) -> Dict[str, Any]:
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
            "distance_to_object": row.get("distance_to_object"),
            "selection_status": row.get("selection_status"),
            "selection_reasons": row.get("selection_reasons"),
            "rigid_object_handle": row.get("rigid_object_handle"),
        },
    }


def aggregate(
    data: Dict[str, Any],
    rows: List[Dict[str, Any]],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    object_records: Dict[str, Dict[str, Any]] = {}
    category_summary: Dict[str, Counter[str]] = defaultdict(Counter)
    candidate_status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for row in rows:
        candidate_status_counts[row["selection_status"]] += 1
        for reason in row["selection_reasons"]:
            reason_counts[reason] += 1

        key = str(row["object_uid"])
        if key not in object_records:
            object_records[key] = {
                "object_uid": row["object_uid"],
                "category": row["category"],
                "scene_id": row["scene_id"],
                "instance_index": row["instance_index"],
                "object_name": row["object_name"],
                "template_name": row["template_name"],
                "accepted_count": 0,
                "review_count": 0,
                "rejected_count": 0,
                "candidate_count": 0,
                "status": "unknown",
                "accepted_viewpoints": [],
                "review_viewpoints": [],
            }
        record = object_records[key]
        record["candidate_count"] += 1
        record[f"{row['selection_status']}_count"] += 1
        if row["selection_status"] == "accepted":
            record["accepted_viewpoints"].append(row)
        elif row["selection_status"] == "review":
            record["review_viewpoints"].append(row)

    for record in object_records.values():
        if record["accepted_count"] >= args.min_viewpoints_per_object:
            record["status"] = "pass"
        elif (
            record["accepted_count"] + record["review_count"]
            >= args.min_viewpoints_per_object
        ):
            record["status"] = "review_needed"
        else:
            record["status"] = "fail"

        cat = str(record["category"])
        category_summary[cat]["objects"] += 1
        category_summary[cat][record["status"]] += 1
        category_summary[cat]["accepted_viewpoints"] += int(record["accepted_count"])
        category_summary[cat]["review_viewpoints"] += int(record["review_count"])
        category_summary[cat]["rejected_candidates"] += int(record["rejected_count"])

    prototype_records: Dict[str, Any] = {}
    for key, record in object_records.items():
        selected_rows = list(record["accepted_viewpoints"])
        if args.include_review_in_prototype_viewpoints:
            selected_rows += list(record["review_viewpoints"])
        prototype_records[key] = {
            "object": {
                "object_uid": record["object_uid"],
                "category": record["category"],
                "scene_id": record["scene_id"],
                "instance_index": record["instance_index"],
                "object_name": record["object_name"],
                "template_name": record["template_name"],
            },
            "object_status": record["status"],
            "view_points": [prototype_viewpoint(row) for row in selected_rows],
        }

    return {
        "input_summary": data.get("summary", {}),
        "selection_thresholds": {
            "min_visible_pixels": args.min_visible_pixels,
            "min_image_fraction": args.min_image_fraction,
            "max_distance": args.max_distance,
            "max_accepted_image_fraction": args.max_accepted_image_fraction,
            "min_viewpoints_per_object": args.min_viewpoints_per_object,
            "reject_flags": args.reject_flags,
            "review_flags": args.review_flags,
            "include_review_in_prototype_viewpoints": (
                args.include_review_in_prototype_viewpoints
            ),
        },
        "candidate_status_counts": dict(candidate_status_counts),
        "selection_reason_counts": dict(reason_counts),
        "object_status_counts": dict(
            Counter(record["status"] for record in object_records.values())
        ),
        "category_summary": {
            cat: dict(counter) for cat, counter in sorted(category_summary.items())
        },
        "object_records": list(object_records.values()),
        "prototype_viewpoints_by_object": prototype_records,
    }


def write_candidate_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fields = [
        "selection_status",
        "selection_reasons",
        "category",
        "scene_id",
        "instance_index",
        "candidate_index",
        "visible_pixels",
        "image_fraction",
        "distance_to_object",
        "sentinel_mask_quality_flags",
        "debug_review_images",
        "debug_overlay_images",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row.get(key), ensure_ascii=False)
                    if isinstance(row.get(key), (list, dict))
                    else row.get(key)
                    for key in fields
                }
            )


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


def format_float(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def candidate_table(rows: List[Dict[str, Any]], top_k: int) -> List[str]:
    lines = [
        "| status | candidate | visible | frac | dist | reasons | review image |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows[:top_k]:
        label = (
            f"{row.get('category')} scene={row.get('scene_id')} "
            f"inst={row.get('instance_index')} cand={row.get('candidate_index')}"
        )
        review = "; ".join(row.get("debug_review_images") or row.get("debug_overlay_images") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("selection_status")),
                    label,
                    str(row.get("visible_pixels")),
                    format_float(row.get("image_fraction")),
                    format_float(row.get("distance_to_object")),
                    ", ".join(row.get("selection_reasons") or []),
                    review,
                ]
            )
            + " |"
        )
    return lines


def build_markdown(
    summary: Dict[str, Any],
    rows: List[Dict[str, Any]],
    top_k: int,
) -> str:
    accepted = sorted(
        [row for row in rows if row["selection_status"] == "accepted"],
        key=lambda row: (str(row.get("category")), str(row.get("scene_id")), to_int(row.get("candidate_index"))),
    )
    review = sorted(
        [row for row in rows if row["selection_status"] == "review"],
        key=lambda row: to_float(row.get("image_fraction")),
        reverse=True,
    )
    rejected = sorted(
        [row for row in rows if row["selection_status"] == "rejected"],
        key=lambda row: to_float(row.get("image_fraction")),
        reverse=True,
    )
    lines = [
        "# Fixed-camera Viewpoint Selection",
        "",
        "This is a static selection pass over prototype output JSON. It does not modify HSSD dataset shards.",
        "",
        "## Summary",
        "",
        f"- candidate status counts: {summary['candidate_status_counts']}",
        f"- object status counts: {summary['object_status_counts']}",
        f"- selection reason counts: {summary['selection_reason_counts']}",
        f"- thresholds: {summary['selection_thresholds']}",
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

    lines.extend(["", f"## Top {top_k} Review Candidates", ""])
    lines.extend(candidate_table(review, top_k))
    lines.extend(["", f"## Top {top_k} Rejected Candidates", ""])
    lines.extend(candidate_table(rejected, top_k))
    lines.extend(["", f"## First {top_k} Accepted Candidates", ""])
    lines.extend(candidate_table(accepted, top_k))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `pass`: object has at least the requested number of accepted fixed-camera viewpoints.",
            "- `review_needed`: accepted + review candidates may be enough, but human review or threshold adjustment is needed.",
            "- `fail`: object does not yet have enough usable viewpoints under these thresholds.",
            "- Full-frame and tiny masks are rejected by default based on manual review feedback.",
            "- Very-large masks are review-only by default because they can be close but still visually meaningful.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    data = load_json(args.input_json)
    rows: List[Dict[str, Any]] = []
    for obj, candidate in iter_rows(data):
        status, reasons = classify_candidate(candidate, args)
        rows.append(flatten_candidate(obj, candidate, status, reasons))

    summary = aggregate(data, rows, args)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "fixed_camera_viewpoint_selection.json"
    candidate_csv = args.output_dir / "fixed_camera_viewpoint_selection_candidates.csv"
    category_csv = args.output_dir / "fixed_camera_viewpoint_selection_categories.csv"
    md_path = args.output_dir / "fixed_camera_viewpoint_selection.md"

    json_path.write_text(
        json.dumps(
            {
                "input_json": str(args.input_json),
                "summary": summary,
                "candidate_rows": rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_candidate_csv(candidate_csv, rows)
    write_category_csv(category_csv, summary)
    md_path.write_text(build_markdown(summary, rows, args.top_k), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {candidate_csv}")
    print(f"Wrote {category_csv}")
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
