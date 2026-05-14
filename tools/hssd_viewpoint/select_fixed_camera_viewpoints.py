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
DEFAULT_REVIEW_FLAGS: Tuple[str, ...] = ()
VISIBLE_PIXEL_KEYS = (
    "visible_pixels",
    "visible_pixel_count",
    "sentinel_visible_pixels",
    "target_visible_pixels",
)
VIS_RATIO_KEYS = (
    "vis_ratio",
    "visibility_ratio",
    "image_fraction",
    "sentinel_image_fraction",
    "target_image_fraction",
)
BBOX_FRAC_KEYS = (
    "bbox_frac",
    "bbox_fraction",
    "sentinel_bbox_area_fraction",
    "target_bbox_area_fraction",
)
DISTANCE_KEYS = (
    "distance_to_bbox",
    "distance_to_object",
    "bbox_distance",
    "object_distance",
)
OBJECT_METADATA_FIELDS = [
    "category_source",
    "canonical_category",
    "canonical_category_source",
    "category_aliases",
    "category_field_values",
    "matched_category_fields",
    "condensed_category",
    "primary_semantic_category",
    "main_category",
    "clean_category",
    "super_category",
    "region_label",
    "region_name",
    "resolved_metadata_id",
    "objects_json_name",
    "object_type",
    "object_tags",
    "wnsynsetkey",
    "main_wnsynsetkey",
    "found_in",
    "has_multiple_objects",
    "support",
    "floorplanner_category_tags",
    "is_articulatable",
    "metadata_dims",
    "scaled_dims_static_approx",
]


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
    parser.add_argument("--min-visible-pixels", type=int, default=300)
    parser.add_argument("--min-image-fraction", type=float, default=0.10)
    parser.add_argument(
        "--min-bbox-fraction",
        type=float,
        default=0.10,
        help=(
            "Minimum target-mask bbox fraction used as a second visual-size "
            "signal. A candidate passes the visual-size gate if either image "
            "fraction or bbox fraction reaches its threshold."
        ),
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=1.0,
        help=(
            "Maximum selection distance. New prototype JSON uses planar "
            "distance_to_bbox first; older JSON falls back to distance_to_object."
        ),
    )
    parser.add_argument(
        "--max-accepted-image-fraction",
        type=float,
        default=0.90,
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


def first_present(data: Dict[str, Any], keys: Tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def visible_pixels_of(candidate: Dict[str, Any]) -> int:
    return to_int(first_present(candidate, VISIBLE_PIXEL_KEYS, 0))


def vis_ratio_of(candidate: Dict[str, Any]) -> float:
    return to_float(first_present(candidate, VIS_RATIO_KEYS, 0.0))


def bbox_frac_of(candidate: Dict[str, Any]) -> float:
    return to_float(first_present(candidate, BBOX_FRAC_KEYS, 0.0))


def distance_value_and_key(
    candidate: Dict[str, Any], default: float = 999999.0
) -> Tuple[float, str]:
    for key in DISTANCE_KEYS:
        value = candidate.get(key)
        if value is not None:
            return to_float(value, default=default), key
    return default, "default"


def distance_of(candidate: Dict[str, Any], default: float = 999999.0) -> float:
    value, _key = distance_value_and_key(candidate, default=default)
    return value


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

    visible_pixels = visible_pixels_of(candidate)
    image_fraction = vis_ratio_of(candidate)
    distance, distance_key = distance_value_and_key(candidate)
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
    bbox_fraction = bbox_frac_of(candidate)
    if (
        image_fraction < args.min_image_fraction
        and bbox_fraction < args.min_bbox_fraction
    ):
        reasons.append(
            f"image_fraction<{args.min_image_fraction}"
            f"_and_bbox_fraction<{args.min_bbox_fraction}"
        )
        return "rejected", reasons
    if distance > args.max_distance:
        reasons.append(f"{distance_key}>{args.max_distance}")
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
    visible_pixels = visible_pixels_of(candidate)
    image_fraction = vis_ratio_of(candidate)
    bbox_fraction = bbox_frac_of(candidate)
    distance, distance_key = distance_value_and_key(candidate, default=0.0)
    row = {
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
        "vis_ratio": image_fraction,
        "bbox_fraction": bbox_fraction,
        "bbox_frac": bbox_fraction,
        "selection_distance": distance,
        "selection_distance_source": distance_key,
        "distance_to_object": candidate.get("distance_to_object"),
        "distance_to_bbox": first_present(candidate, ("distance_to_bbox",)),
        "planar_distance_to_object_xz": candidate.get("planar_distance_to_object_xz"),
        "planar_distance_to_bbox_xz": candidate.get("planar_distance_to_bbox_xz"),
        "sentinel_bbox": candidate.get("sentinel_bbox"),
        "sentinel_bbox_area_fraction": first_present(candidate, BBOX_FRAC_KEYS),
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
    for field in OBJECT_METADATA_FIELDS:
        row[field] = obj.get(field)
    return row


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
            "vis_ratio": row.get("vis_ratio"),
            "bbox_frac": row.get("bbox_frac"),
            "selection_distance": row.get("selection_distance"),
            "selection_distance_source": row.get("selection_distance_source"),
            "distance_to_object": row.get("distance_to_object"),
            "distance_to_bbox": row.get("distance_to_bbox"),
            "selection_status": row.get("selection_status"),
            "selection_reasons": row.get("selection_reasons"),
            "rigid_object_handle": row.get("rigid_object_handle"),
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
            "object_name": row.get("object_name"),
            "objects_json_name": row.get("objects_json_name"),
            "wnsynsetkey": row.get("wnsynsetkey"),
            "main_wnsynsetkey": row.get("main_wnsynsetkey"),
            "has_multiple_objects": row.get("has_multiple_objects"),
            "is_articulatable": row.get("is_articulatable"),
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
            for field in OBJECT_METADATA_FIELDS:
                object_records[key][field] = row.get(field)
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
                **{
                    field: record.get(field)
                    for field in OBJECT_METADATA_FIELDS
                    if record.get(field) is not None
                },
            },
            "object_status": record["status"],
            "view_points": [prototype_viewpoint(row) for row in selected_rows],
        }

    return {
        "input_summary": data.get("summary", {}),
        "selection_thresholds": {
            "min_visible_pixels": args.min_visible_pixels,
            "min_image_fraction": args.min_image_fraction,
            "min_vis_ratio": args.min_image_fraction,
            "min_bbox_fraction": args.min_bbox_fraction,
            "max_distance": args.max_distance,
            "max_accepted_image_fraction": args.max_accepted_image_fraction,
            "min_viewpoints_per_object": args.min_viewpoints_per_object,
            "distance_metric": (
                "first available of distance_to_bbox, distance_to_object, "
                "bbox_distance, object_distance"
            ),
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
        "category_source",
        "canonical_category",
        "canonical_category_source",
        "condensed_category",
        "primary_semantic_category",
        "main_category",
        "clean_category",
        "super_category",
        "region_label",
        "region_name",
        "scene_id",
        "instance_index",
        "object_uid",
        "candidate_index",
        "object_name",
        "objects_json_name",
        "template_name",
        "resolved_metadata_id",
        "wnsynsetkey",
        "main_wnsynsetkey",
        "has_multiple_objects",
        "is_articulatable",
        "floorplanner_category_tags",
        "visible_pixels",
        "image_fraction",
        "vis_ratio",
        "bbox_fraction",
        "bbox_frac",
        "selection_distance",
        "selection_distance_source",
        "distance_to_object",
        "distance_to_bbox",
        "planar_distance_to_object_xz",
        "planar_distance_to_bbox_xz",
        "sentinel_bbox_area_fraction",
        "sentinel_mask_quality_flags",
        "category_aliases",
        "category_field_values",
        "matched_category_fields",
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


def write_object_csv(path: Path, summary: Dict[str, Any]) -> None:
    fields = [
        "status",
        "category",
        "category_source",
        "canonical_category",
        "canonical_category_source",
        "condensed_category",
        "primary_semantic_category",
        "main_category",
        "clean_category",
        "super_category",
        "region_label",
        "region_name",
        "scene_id",
        "instance_index",
        "object_name",
        "objects_json_name",
        "template_name",
        "resolved_metadata_id",
        "wnsynsetkey",
        "main_wnsynsetkey",
        "has_multiple_objects",
        "is_articulatable",
        "floorplanner_category_tags",
        "candidate_count",
        "accepted_count",
        "review_count",
        "rejected_count",
        "accepted_candidate_indices",
        "review_candidate_indices",
        "review_images",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in summary["object_records"]:
            accepted = record.get("accepted_viewpoints") or []
            review = record.get("review_viewpoints") or []
            review_images: List[str] = []
            for row in review:
                review_images.extend(row.get("debug_review_images") or [])
            writer.writerow(
                {
                    "status": record.get("status"),
                    "category": record.get("category"),
                    "category_source": record.get("category_source"),
                    "canonical_category": record.get("canonical_category"),
                    "canonical_category_source": record.get(
                        "canonical_category_source"
                    ),
                    "condensed_category": record.get("condensed_category"),
                    "primary_semantic_category": record.get(
                        "primary_semantic_category"
                    ),
                    "main_category": record.get("main_category"),
                    "clean_category": record.get("clean_category"),
                    "super_category": record.get("super_category"),
                    "scene_id": record.get("scene_id"),
                    "instance_index": record.get("instance_index"),
                    "object_name": record.get("object_name"),
                    "objects_json_name": record.get("objects_json_name"),
                    "template_name": record.get("template_name"),
                    "resolved_metadata_id": record.get("resolved_metadata_id"),
                    "wnsynsetkey": record.get("wnsynsetkey"),
                    "main_wnsynsetkey": record.get("main_wnsynsetkey"),
                    "has_multiple_objects": record.get("has_multiple_objects"),
                    "is_articulatable": record.get("is_articulatable"),
                    "floorplanner_category_tags": record.get(
                        "floorplanner_category_tags"
                    ),
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
                    "review_images": json.dumps(review_images, ensure_ascii=False),
                }
            )


def format_float(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def candidate_table(rows: List[Dict[str, Any]], top_k: int) -> List[str]:
    lines = [
        "| status | candidate | visible | vis ratio | bbox frac | sel dist | reasons | review image |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in rows[:top_k]:
        label = (
            f"{row.get('category')} scene={row.get('scene_id')} "
            f"inst={row.get('instance_index')} cand={row.get('candidate_index')} "
            f"name={row.get('object_name') or row.get('objects_json_name') or ''}"
        )
        if row.get("canonical_category") and row.get("canonical_category") != row.get(
            "category"
        ):
            label += f" canonical={row.get('canonical_category')}"
        review = "; ".join(row.get("debug_review_images") or row.get("debug_overlay_images") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("selection_status")),
                    label,
                    str(row.get("visible_pixels")),
                    format_float(row.get("vis_ratio", row.get("image_fraction"))),
                    format_float(row.get("bbox_frac", row.get("bbox_fraction"))),
                    format_float(row.get("selection_distance")),
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
    failing_objects = [
        record for record in summary["object_records"] if record.get("status") == "fail"
    ]
    review_needed_objects = [
        record
        for record in summary["object_records"]
        if record.get("status") == "review_needed"
    ]
    lines.extend(["", "## Failing Objects", ""])
    lines.extend(object_table(failing_objects))
    lines.extend(["", "## Review-needed Objects", ""])
    lines.extend(object_table(review_needed_objects))
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


def object_table(records: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "| status | category | canonical | primary/main | scene | instance | object name | accepted | review | rejected | review candidates |",
        "|---|---|---|---|---|---:|---|---:|---:|---:|---|",
    ]
    if not records:
        lines.append("| none |  |  |  |  |  |  |  |  |  |  |")
        return lines
    for record in sorted(
        records,
        key=lambda r: (str(r.get("category")), str(r.get("scene_id")), int(r.get("instance_index") or -1)),
    ):
        review_rows = record.get("review_viewpoints") or []
        review_labels = [
            f"cand={row.get('candidate_index')} frac={format_float(row.get('image_fraction'))}"
            for row in review_rows
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(record.get("status")),
                    str(record.get("category")),
                    str(record.get("canonical_category") or ""),
                    (
                        f"{record.get('primary_semantic_category') or ''}/"
                        f"{record.get('main_category') or ''}"
                    ),
                    str(record.get("scene_id")),
                    str(record.get("instance_index")),
                    str(record.get("object_name") or record.get("objects_json_name") or ""),
                    str(record.get("accepted_count")),
                    str(record.get("review_count")),
                    str(record.get("rejected_count")),
                    "; ".join(review_labels),
                ]
            )
            + " |"
        )
    return lines


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
    object_csv = args.output_dir / "fixed_camera_viewpoint_selection_objects.csv"
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
    write_object_csv(object_csv, summary)
    md_path.write_text(build_markdown(summary, rows, args.top_k), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {candidate_csv}")
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
