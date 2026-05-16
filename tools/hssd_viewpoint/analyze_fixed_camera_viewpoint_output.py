#!/usr/bin/env python3
"""Summarize fixed-camera viewpoint prototype JSON outputs.

This is a static analysis helper. It reads the prototype JSON only; it does not
import Habitat-Sim, render scenes, or modify datasets.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


DEFAULT_INPUT = Path(
    "outputs/hssd_fixed_camera_viewpoint_prototype/"
    "hssd_fixed_camera_viewpoint_prototype.json"
)
DEFAULT_OUTPUT_DIR = Path("outputs/hssd_fixed_camera_viewpoint_analysis")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze hssd_fixed_camera_viewpoint_prototype.json and list "
            "sentinel-positive, heuristic-positive, and quality-flagged "
            "candidates."
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
        help="Directory for analysis JSON/CSV/Markdown outputs.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=50,
        help="Number of largest positive candidates to include in Markdown.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def first_present(data: Dict[str, Any], keys: Tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def iter_object_candidate_rows(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield flattened object/candidate rows.

    The current schema is object_results[*].object and
    object_results[*].candidate_results. A small fallback supports older local
    drafts that used objects[*].candidates.
    """

    if data.get("object_results"):
        object_results = data.get("object_results") or []
        for obj_result in object_results:
            obj = obj_result.get("object") or {}
            for candidate in obj_result.get("candidate_results") or []:
                yield flatten_row(obj, obj_result, candidate)
        return

    for obj in data.get("objects") or []:
        obj_result = {"semantic_mapping_status": obj.get("semantic_mapping_status")}
        for candidate in obj.get("candidates") or []:
            yield flatten_row(obj, obj_result, candidate)


def flatten_row(
    obj: Dict[str, Any],
    obj_result: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    debug_images = candidate.get("debug_images") or []
    overlay_images = [
        p for p in debug_images if "_overlay" in str(p) or str(p).endswith("overlay.png")
    ]
    review_images = [
        p for p in debug_images if "_review" in str(p) or str(p).endswith("review.png")
    ]
    flags = [str(f) for f in (candidate.get("sentinel_mask_quality_flags") or [])]
    visible_pixels = to_int(first_present(candidate, VISIBLE_PIXEL_KEYS, 0))
    heuristic_visible_pixels = int(candidate.get("heuristic_visible_pixels") or 0)
    image_fraction = first_present(candidate, VIS_RATIO_KEYS)
    bbox_fraction = first_present(candidate, BBOX_FRAC_KEYS)
    return {
        "category": obj.get("category"),
        "scene_id": str(obj.get("scene_id")),
        "instance_index": obj.get("instance_index"),
        "object_uid": obj.get("object_uid"),
        "template_name": obj.get("template_name"),
        "candidate_index": candidate.get("candidate_index"),
        "visible_pixels": visible_pixels,
        "image_fraction": image_fraction,
        "vis_ratio": image_fraction,
        "sentinel_semantic_id": candidate.get("sentinel_semantic_id"),
        "sentinel_status": candidate.get("sentinel_status"),
        "sentinel_bbox": candidate.get("sentinel_bbox"),
        "sentinel_bbox_area_fraction": bbox_fraction,
        "bbox_frac": bbox_fraction,
        "sentinel_mask_quality_flags": flags,
        "heuristic_visible_pixels": heuristic_visible_pixels,
        "heuristic_best_semantic_id": candidate.get("heuristic_best_semantic_id"),
        "semantic_mapping_status": candidate.get(
            "semantic_mapping_status", obj_result.get("semantic_mapping_status")
        ),
        "rigid_object_handle": candidate.get("rigid_object_handle"),
        "candidate_error": candidate.get("candidate_error"),
        "debug_images": debug_images,
        "overlay_images": overlay_images,
        "review_images": review_images,
    }


def summarize(data: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    flag_counter: Counter[str] = Counter()
    mapping_counter: Counter[str] = Counter()
    sentinel_status_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    positive_by_category: Counter[str] = Counter()
    flagged_by_category: Counter[str] = Counter()

    for row in rows:
        category = str(row.get("category"))
        category_counter[category] += 1
        if row.get("semantic_mapping_status"):
            mapping_counter[str(row["semantic_mapping_status"])] += 1
        if row.get("sentinel_status"):
            sentinel_status_counter[str(row["sentinel_status"])] += 1
        if row["visible_pixels"] > 0:
            positive_by_category[category] += 1
        if row["sentinel_mask_quality_flags"]:
            flagged_by_category[category] += 1
        for flag in row["sentinel_mask_quality_flags"]:
            flag_counter[flag] += 1

    debug_image_count = sum(len(row["debug_images"]) for row in rows)
    overlay_image_count = sum(len(row["overlay_images"]) for row in rows)
    review_image_count = sum(len(row["review_images"]) for row in rows)
    positive_rows = [row for row in rows if row["visible_pixels"] > 0]
    heuristic_positive_rows = [
        row for row in rows if row["heuristic_visible_pixels"] > 0
    ]
    heuristic_only_rows = [
        row
        for row in rows
        if row["heuristic_visible_pixels"] > 0 and row["visible_pixels"] <= 0
    ]
    flagged_rows = [row for row in rows if row["sentinel_mask_quality_flags"]]
    full_frame_rows = [
        row
        for row in rows
        if "full_frame_sentinel_mask" in row["sentinel_mask_quality_flags"]
    ]
    return {
        "input_summary": data.get("summary", {}),
        "candidate_rows": len(rows),
        "sentinel_positive_candidates": len(positive_rows),
        "heuristic_positive_candidates": len(heuristic_positive_rows),
        "heuristic_only_positive_candidates": len(heuristic_only_rows),
        "quality_flagged_candidates": len(flagged_rows),
        "full_frame_sentinel_candidates": len(full_frame_rows),
        "debug_image_paths_in_json": debug_image_count,
        "overlay_image_paths_in_json": overlay_image_count,
        "review_image_paths_in_json": review_image_count,
        "flag_counts": dict(flag_counter),
        "mapping_status_counts_from_candidates": dict(mapping_counter),
        "sentinel_status_counts_from_candidates": dict(sentinel_status_counter),
        "candidate_rows_by_category": dict(category_counter),
        "sentinel_positive_by_category": dict(positive_by_category),
        "quality_flagged_by_category": dict(flagged_by_category),
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "category",
        "scene_id",
        "instance_index",
        "candidate_index",
        "visible_pixels",
        "image_fraction",
        "vis_ratio",
        "sentinel_bbox_area_fraction",
        "bbox_frac",
        "sentinel_mask_quality_flags",
        "heuristic_visible_pixels",
        "heuristic_best_semantic_id",
        "semantic_mapping_status",
        "sentinel_status",
        "rigid_object_handle",
        "review_images",
        "overlay_images",
        "debug_images",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(row.get(key), ensure_ascii=False)
                    if isinstance(row.get(key), (list, dict))
                    else row.get(key)
                    for key in fieldnames
                }
            )


def row_label(row: Dict[str, Any]) -> str:
    return (
        f"{row.get('category')} scene={row.get('scene_id')} "
        f"instance={row.get('instance_index')} "
        f"candidate={row.get('candidate_index')}"
    )


def markdown_table(rows: List[Dict[str, Any]], limit: int) -> List[str]:
    lines = [
        "| candidate | visible | image frac | bbox frac | flags | heuristic | review/overlay |",
        "|---|---:|---:|---:|---|---:|---|",
    ]
    for row in rows[:limit]:
        review = "; ".join(str(p) for p in row.get("review_images") or [])
        overlay = review or "; ".join(str(p) for p in row.get("overlay_images") or [])
        lines.append(
            "| "
            + " | ".join(
                [
                    row_label(row),
                    str(row.get("visible_pixels")),
                    format_float(row.get("image_fraction")),
                    format_float(row.get("sentinel_bbox_area_fraction")),
                    ", ".join(row.get("sentinel_mask_quality_flags") or []),
                    str(row.get("heuristic_visible_pixels")),
                    overlay,
                ]
            )
            + " |"
        )
    return lines


def format_float(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


def build_markdown(
    input_json: Path,
    summary: Dict[str, Any],
    positive_rows: List[Dict[str, Any]],
    flagged_rows: List[Dict[str, Any]],
    heuristic_only_rows: List[Dict[str, Any]],
    top_k: int,
) -> str:
    lines = [
        "# Fixed-camera Viewpoint Output Analysis",
        "",
        f"Input JSON: `{input_json}`",
        "",
        "This is a static JSON analysis. It does not import Habitat-Sim, render, train, or modify datasets.",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- `{key}`: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Current prototype schema is `object_results[*].object` plus `object_results[*].candidate_results`.",
            "- `objects[*].candidates` was an older draft shape; scripts using it will report empty candidate rows on current outputs.",
            "- `heuristic_only_positive_candidates` are cases where non-sentinel semantic heuristics see pixels but the target sentinel mask does not.",
            "- `sentinel_mask_quality_flags` are review flags, not automatic rejection decisions.",
            "",
            f"## Top {top_k} Sentinel-positive Candidates",
            "",
        ]
    )
    lines.extend(markdown_table(positive_rows, top_k))
    lines.extend(["", f"## Top {top_k} Quality-flagged Candidates", ""])
    lines.extend(markdown_table(flagged_rows, top_k))
    lines.extend(["", f"## Top {top_k} Heuristic-only Positives", ""])
    lines.extend(markdown_table(heuristic_only_rows, top_k))
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    data = load_json(args.input_json)
    rows = list(iter_object_candidate_rows(data))

    positive_rows = sorted(
        [row for row in rows if row["visible_pixels"] > 0],
        key=lambda row: int(row["visible_pixels"]),
        reverse=True,
    )
    flagged_rows = sorted(
        [row for row in rows if row["sentinel_mask_quality_flags"]],
        key=lambda row: int(row["visible_pixels"]),
        reverse=True,
    )
    heuristic_only_rows = sorted(
        [
            row
            for row in rows
            if row["heuristic_visible_pixels"] > 0 and row["visible_pixels"] <= 0
        ],
        key=lambda row: int(row["heuristic_visible_pixels"]),
        reverse=True,
    )

    summary = summarize(data, rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "fixed_camera_viewpoint_analysis.json"
    csv_path = args.output_dir / "fixed_camera_viewpoint_candidates.csv"
    md_path = args.output_dir / "fixed_camera_viewpoint_analysis.md"

    json_path.write_text(
        json.dumps(
            {
                "input_json": str(args.input_json),
                "summary": summary,
                "positive_candidates": positive_rows,
                "quality_flagged_candidates": flagged_rows,
                "heuristic_only_positive_candidates": heuristic_only_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_csv(csv_path, rows)
    md_path.write_text(
        build_markdown(
            args.input_json,
            summary,
            positive_rows,
            flagged_rows,
            heuristic_only_rows,
            args.top_k,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
