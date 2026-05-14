#!/usr/bin/env python3
"""Build a curated visual QA pack from fixed-camera viewpoint selection output.

This script is intentionally static: it reads selector JSON, copies existing
debug review/overlay images into a compact folder, and writes CSV/Markdown
manifests. It does not import Habitat-Sim, render, train, or modify dataset
shards.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_OUTPUT_DIR = Path("outputs/fixed_camera_visual_qa_pack")
IMAGE_SUFFIX_PRIORITY = ("_review.png", "_overlay.png", "_rgb.png", "_mask.png")
BBOX_IMAGE_SUFFIX_PRIORITY = ("_overlay.png", "_rgb.png")
FLOAT_TOLERANCE = 1e-6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a curated image review pack from fixed-camera selection JSON."
    )
    parser.add_argument(
        "--selection-json",
        type=Path,
        required=True,
        help="Path to fixed_camera_viewpoint_selection.json.",
    )
    parser.add_argument(
        "--path-root",
        type=Path,
        default=Path("."),
        help="Base directory used to resolve relative debug image paths.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for copied images and review manifests.",
    )
    parser.add_argument(
        "--max-per-category-status",
        type=int,
        default=6,
        help="Maximum accepted/review/rejected examples copied per category/status.",
    )
    parser.add_argument(
        "--max-per-failing-object",
        type=int,
        default=4,
        help="Maximum best rejected/accepted rows copied for each failing object.",
    )
    parser.add_argument(
        "--max-taxonomy-examples",
        type=int,
        default=80,
        help="Maximum category/canonical mismatch rows copied for taxonomy QA.",
    )
    parser.add_argument(
        "--max-total-images",
        type=int,
        default=260,
        help="Hard cap on copied image rows.",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include selected rows even when the referenced image is missing.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, tuple):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value: Any) -> str:
    return "" if value is None else str(value)


def safe_name(value: Any, max_len: int = 90) -> str:
    raw = text(value)
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw)
    cleaned = cleaned.strip("_")
    return (cleaned[:max_len] or "item").strip("_") or "item"


def first_image_path(row: Dict[str, Any]) -> str:
    paths: List[str] = []
    paths.extend(as_list(row.get("debug_review_images")))
    paths.extend(as_list(row.get("debug_overlay_images")))
    paths.extend(as_list(row.get("debug_images")))
    paths = list(dict.fromkeys(paths))
    for suffix in IMAGE_SUFFIX_PRIORITY:
        for path in paths:
            if path.endswith(suffix):
                return path
    return paths[0] if paths else ""


def bbox_source_image_path(row: Dict[str, Any]) -> str:
    paths: List[str] = []
    paths.extend(as_list(row.get("debug_overlay_images")))
    paths.extend(as_list(row.get("debug_images")))
    paths = list(dict.fromkeys(paths))
    for suffix in BBOX_IMAGE_SUFFIX_PRIORITY:
        for path in paths:
            if path.endswith(suffix):
                return path
    return ""


def resolve_path(path: str, root: Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    return p


def object_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            text(row.get("category")),
            text(row.get("scene_id")),
            text(row.get("instance_index")),
            text(row.get("object_uid")),
        ]
    )


def vis_ratio(row: Dict[str, Any]) -> float:
    return to_float(row.get("vis_ratio", row.get("image_fraction")))


def bbox_frac(row: Dict[str, Any]) -> float:
    return to_float(row.get("bbox_frac", row.get("bbox_fraction")))


def distance(row: Dict[str, Any]) -> float:
    return to_float(
        row.get(
            "selection_distance",
            row.get("distance_to_bbox", row.get("distance_to_object")),
        ),
        default=999999.0,
    )


def row_label(row: Dict[str, Any]) -> str:
    name = row.get("object_name") or row.get("objects_json_name") or row.get("template_name")
    return (
        f"{row.get('category')} scene={row.get('scene_id')} "
        f"inst={row.get('instance_index')} cand={row.get('candidate_index')} "
        f"name={name or ''}"
    )


def taxonomy_mismatch(row: Dict[str, Any]) -> bool:
    category = text(row.get("category"))
    canonical = text(row.get("canonical_category"))
    primary = text(row.get("primary_semantic_category"))
    main = text(row.get("main_category"))
    if canonical and category and canonical != category:
        return True
    if primary and category and primary != category:
        return True
    if main and category and main != category:
        return True
    return False


def selection_reason_text(row: Dict[str, Any]) -> str:
    return ";".join(as_list(row.get("selection_reasons")))


def sort_key_quality(row: Dict[str, Any]) -> Tuple[float, float, float, str]:
    return (
        -vis_ratio(row),
        -bbox_frac(row),
        distance(row),
        text(row.get("candidate_index")),
    )


def load_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = data.get("candidate_rows") or []
    if not isinstance(rows, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        copied = dict(row)
        copied["image_path"] = first_image_path(copied)
        copied["selection_reasons_text"] = selection_reason_text(copied)
        copied["taxonomy_mismatch"] = taxonomy_mismatch(copied)
        normalized.append(copied)
    return normalized


def choose_balanced_rows(
    rows: Sequence[Dict[str, Any]], args: argparse.Namespace
) -> List[Dict[str, Any]]:
    selected: Dict[str, Dict[str, Any]] = {}

    def add(row: Dict[str, Any], reason: str) -> None:
        key = "|".join(
            [
                text(row.get("category")),
                text(row.get("scene_id")),
                text(row.get("instance_index")),
                text(row.get("candidate_index")),
            ]
        )
        if key not in selected:
            copied = dict(row)
            copied["qa_pick_reasons"] = [reason]
            selected[key] = copied
        else:
            selected[key].setdefault("qa_pick_reasons", []).append(reason)

    by_category_status: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_object: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        category = text(row.get("category")) or "unknown"
        status = text(row.get("selection_status")) or "unknown"
        by_category_status[(category, status)].append(row)
        by_object[object_key(row)].append(row)

    for (category, status), group in sorted(by_category_status.items()):
        sorted_group = sorted(group, key=sort_key_quality)
        if status == "accepted":
            if sorted_group:
                add(sorted_group[0], f"best_accepted_for_category:{category}")
                add(sorted_group[len(sorted_group) // 2], f"mid_accepted_for_category:{category}")
                add(sorted_group[-1], f"lowest_accepted_for_category:{category}")
            for row in sorted_group[: args.max_per_category_status]:
                add(row, f"accepted_category_sample:{category}")
        elif status == "review":
            for row in sorted_group[: args.max_per_category_status]:
                add(row, f"review_category_sample:{category}")
        elif status == "rejected":
            near_threshold = [
                row
                for row in sorted_group
                if "image_fraction<" in text(row.get("selection_reasons_text"))
            ]
            for row in near_threshold[: args.max_per_category_status]:
                add(row, f"near_threshold_rejected:{category}")

    for key, group in sorted(by_object.items()):
        accepted = [row for row in group if row.get("selection_status") == "accepted"]
        review = [row for row in group if row.get("selection_status") == "review"]
        rejected = [row for row in group if row.get("selection_status") == "rejected"]
        if len(accepted) + len(review) >= 3:
            continue
        for row in sorted(accepted + review, key=sort_key_quality)[
            : args.max_per_failing_object
        ]:
            add(row, f"failing_object_existing_candidate:{key}")
        for row in sorted(rejected, key=sort_key_quality)[: args.max_per_failing_object]:
            add(row, f"failing_object_best_rejected:{key}")

    taxonomy_rows = [row for row in rows if row.get("taxonomy_mismatch")]
    for row in sorted(taxonomy_rows, key=sort_key_quality)[: args.max_taxonomy_examples]:
        add(row, "taxonomy_mismatch")

    selected_rows = list(selected.values())
    selected_rows.sort(
        key=lambda row: (
            text(row.get("category")),
            text(row.get("selection_status")),
            -vis_ratio(row),
            text(row.get("scene_id")),
            text(row.get("instance_index")),
            text(row.get("candidate_index")),
        )
    )
    return selected_rows[: args.max_total_images]


def image_target_path(row: Dict[str, Any], output_dir: Path) -> Path:
    return output_dir / "images" / text(row_image_subpath(row))


def bbox_image_target_path(row: Dict[str, Any], output_dir: Path) -> Path:
    category = safe_name(row.get("category"))
    status = safe_name(row.get("selection_status"))
    return (
        output_dir
        / "images"
        / category
        / status
        / f"{row_image_stem(row)}_bbox.png"
    )


def row_image_stem(row: Dict[str, Any]) -> str:
    category = safe_name(row.get("category"))
    status = safe_name(row.get("selection_status"))
    scene = safe_name(row.get("scene_id"))
    instance = safe_name(row.get("instance_index"))
    candidate = safe_name(row.get("candidate_index"))
    frac = f"{vis_ratio(row):.4f}".replace(".", "p")
    bbox = f"{bbox_frac(row):.4f}".replace(".", "p")
    sel_dist = f"{distance(row):.3f}".replace(".", "p")
    dist_src = safe_name(row.get("selection_distance_source"), max_len=30)
    stem = (
        f"{category}_{status}_scene-{scene}_inst-{instance}_"
        f"cand-{candidate}_frac-{frac}_bbox-{bbox}_seldist-{sel_dist}_{dist_src}"
    )
    return safe_name(stem, max_len=180)


def image_kind_from_path(path: Any) -> str:
    name = Path(text(path)).name
    for suffix, kind in [
        ("_review.png", "review"),
        ("_overlay.png", "overlay"),
        ("_rgb.png", "rgb"),
        ("_mask.png", "mask"),
    ]:
        if name.endswith(suffix):
            return kind
    return "source"


def row_image_subpath(row: Dict[str, Any]) -> Path:
    category = safe_name(row.get("category"))
    status = safe_name(row.get("selection_status"))
    kind = image_kind_from_path(row.get("image_path"))
    return Path(category) / status / f"{row_image_stem(row)}_{kind}.png"


def parse_bbox(value: Any) -> Optional[Dict[str, int]]:
    if value in (None, ""):
        return None
    parsed = value
    if isinstance(value, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(value)
                break
            except Exception:
                parsed = None
        if parsed is None:
            return None
    if not isinstance(parsed, dict):
        return None
    try:
        return {
            "x0": int(parsed["x0"]),
            "y0": int(parsed["y0"]),
            "x1": int(parsed["x1"]),
            "y1": int(parsed["y1"]),
            "area": int(parsed.get("area", 0) or 0),
        }
    except Exception:
        return None


def draw_bbox_image(row: Dict[str, Any], root: Path, output_dir: Path) -> Tuple[bool, str]:
    bbox = parse_bbox(row.get("sentinel_bbox"))
    source = bbox_source_image_path(row)
    if bbox is None or not source:
        return False, source

    src = resolve_path(source, root)
    if not src.exists():
        return False, source

    dst = bbox_image_target_path(row, output_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415

        image = Image.open(src).convert("RGB")
        draw = ImageDraw.Draw(image)
        w, h = image.size
        x0 = max(0, min(w - 1, bbox["x0"]))
        y0 = max(0, min(h - 1, bbox["y0"]))
        x1 = max(0, min(w - 1, bbox["x1"]))
        y1 = max(0, min(h - 1, bbox["y1"]))
        line_width = max(2, min(w, h) // 160)
        draw.rectangle((x0, y0, x1, y1), outline=(255, 230, 0), width=line_width)
        label = (
            f"bbox=({x0},{y0})-({x1},{y1}) "
            f"bbox_frac={bbox_frac(row):.4f} sel_dist={distance(row):.3f}"
        )
        text_bbox = draw.textbbox((0, 0), label)
        label_h = text_bbox[3] - text_bbox[1] + 8
        label_w = min(w, text_bbox[2] - text_bbox[0] + 10)
        label_y = max(0, y0 - label_h)
        draw.rectangle((x0, label_y, min(w - 1, x0 + label_w), label_y + label_h), fill=(0, 0, 0))
        draw.text((x0 + 5, label_y + 4), label, fill=(255, 230, 0))
        image.save(dst)
        return True, source
    except Exception:
        return False, source


def copy_images(
    rows: Sequence[Dict[str, Any]], root: Path, output_dir: Path, include_missing: bool
) -> List[Dict[str, Any]]:
    copied_rows: List[Dict[str, Any]] = []
    missing_count = 0
    for row in rows:
        image_path = text(row.get("image_path"))
        src = resolve_path(image_path, root) if image_path else Path("")
        dst = image_target_path(row, output_dir)
        bbox_dst = bbox_image_target_path(row, output_dir)
        out_row = dict(row)
        out_row["source_image_abs"] = str(src) if image_path else ""
        out_row["qa_image_type"] = image_kind_from_path(image_path)
        out_row["qa_image"] = str(dst.relative_to(output_dir))
        out_row["qa_image_exists"] = False
        out_row["bbox_source_image_abs"] = ""
        out_row["qa_bbox_image"] = str(bbox_dst.relative_to(output_dir))
        out_row["qa_bbox_image_exists"] = False
        if image_path and src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            out_row["qa_image_exists"] = True
        else:
            missing_count += 1
            if not include_missing:
                continue
        bbox_created, bbox_source = draw_bbox_image(row, root, output_dir)
        if bbox_source:
            out_row["bbox_source_image_abs"] = str(resolve_path(bbox_source, root))
        out_row["qa_bbox_image_exists"] = bbox_created
        copied_rows.append(out_row)
    for row in copied_rows:
        row["missing_image_count_for_pack"] = missing_count
    return copied_rows


def write_manifest(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    fields = [
        "qa_image",
        "qa_image_exists",
        "qa_image_type",
        "qa_pick_reasons",
        "selection_status",
        "selection_reasons",
        "category",
        "category_source",
        "canonical_category",
        "canonical_category_source",
        "condensed_category",
        "primary_semantic_category",
        "main_category",
        "super_category",
        "region_label",
        "region_name",
        "scene_id",
        "instance_index",
        "candidate_index",
        "object_name",
        "objects_json_name",
        "template_name",
        "resolved_metadata_id",
        "wnsynsetkey",
        "main_wnsynsetkey",
        "has_multiple_objects",
        "is_articulatable",
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
        "source_image_abs",
        "bbox_source_image_abs",
        "qa_bbox_image",
        "qa_bbox_image_exists",
        "sentinel_bbox",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: ";".join(as_list(row.get(field)))
                    if field in {"qa_pick_reasons", "selection_reasons"}
                    else row.get(field)
                    for field in fields
                }
            )


def md_image(path: str) -> str:
    return f"![review]({path.replace('|', '%7C')})" if path else ""


def row_markdown(row: Dict[str, Any]) -> List[str]:
    label = row_label(row).replace("|", "\\|")
    reasons = ",".join(as_list(row.get("selection_reasons"))).replace("|", "\\|")
    qa_reasons = ",".join(as_list(row.get("qa_pick_reasons"))).replace("|", "\\|")
    category_note = (
        f"{row.get('canonical_category') or ''}; "
        f"{row.get('primary_semantic_category') or ''}/"
        f"{row.get('main_category') or ''}"
    ).replace("|", "\\|")
    return [
        "| "
        + " | ".join(
            [
                text(row.get("selection_status")),
                text(row.get("category")),
                category_note,
                label,
                f"{vis_ratio(row):.4f}",
                f"{bbox_frac(row):.4f}",
                f"{distance(row):.3f}",
                reasons,
                qa_reasons,
                text(row.get("qa_image")),
            ]
        )
        + " |",
        "",
        md_image(text(row.get("qa_image"))),
        "",
        md_image(text(row.get("qa_bbox_image")) if row.get("qa_bbox_image_exists") else ""),
        "",
    ]


def write_markdown(path: Path, rows: Sequence[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Fixed-Camera Visual QA Pack",
        "",
        "This pack is built from existing fixed-camera debug images. It is for manual visual QA only.",
        "",
        "## Summary",
        "",
        f"- selection JSON: `{summary['selection_json']}`",
        f"- candidate rows in source: {summary['source_candidate_rows']}",
        f"- selected rows requested: {summary['selected_rows_requested']}",
        f"- copied/image rows in pack: {summary['pack_rows']}",
        f"- missing selected images: {summary['missing_selected_images']}",
        f"- missing bbox visualizations: {summary['missing_bbox_visualizations']}",
        f"- accepted distance violations: {summary['accepted_audit']['distance_violations']}",
        f"- accepted visual-gate violations: {summary['accepted_audit']['visual_gate_violations']}",
        f"- accepted visible-pixel violations: {summary['accepted_audit']['visible_pixel_violations']}",
        f"- accepted rows using distance fallback: {summary['accepted_audit']['distance_fallback_rows']}",
        "",
        "## Counts",
        "",
        "| field | value | count |",
        "|---|---|---:|",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"| status | {status} | {count} |")
    for category, count in summary["category_counts"].items():
        lines.append(f"| category | {category} | {count} |")

    by_reason: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reason = as_list(row.get("qa_pick_reasons"))[0] if row.get("qa_pick_reasons") else "sample"
        by_reason[reason].append(row)

    table_header = [
        "| status | category | canonical; primary/main | candidate | vis | bbox | dist | selection reasons | qa reasons | image path |",
        "|---|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for reason, group in sorted(by_reason.items()):
        lines.extend(["", f"## {reason}", ""])
        lines.extend(table_header)
        for row in group:
            lines.extend(row_markdown(row))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def threshold_value(
    row: Dict[str, Any],
    selection_summary: Dict[str, Any],
    row_key: str,
    summary_key: str,
    default: float,
) -> float:
    value = row.get(row_key)
    if value is None:
        value = (selection_summary.get("selection_thresholds") or {}).get(summary_key)
    return to_float(value, default=default)


def accepted_audit(
    rows: Sequence[Dict[str, Any]],
    selection_summary: Dict[str, Any],
) -> Dict[str, Any]:
    accepted = [row for row in rows if text(row.get("selection_status")) == "accepted"]
    examples: List[Dict[str, Any]] = []
    counts = Counter()

    for row in accepted:
        min_visible = threshold_value(
            row,
            selection_summary,
            "candidate_min_visible_pixels",
            "min_visible_pixels",
            300,
        )
        min_image = threshold_value(
            row,
            selection_summary,
            "candidate_min_image_fraction",
            "min_image_fraction",
            0.10,
        )
        min_bbox = threshold_value(
            row,
            selection_summary,
            "candidate_min_bbox_fraction",
            "min_bbox_fraction",
            0.10,
        )
        max_distance = threshold_value(
            row,
            selection_summary,
            "candidate_max_distance",
            "max_distance",
            1.0,
        )

        row_violations: List[str] = []
        if to_int(row.get("visible_pixels")) < min_visible:
            counts["visible_pixel_violations"] += 1
            row_violations.append("visible_pixels")
        if vis_ratio(row) < min_image - FLOAT_TOLERANCE and bbox_frac(row) < min_bbox - FLOAT_TOLERANCE:
            counts["visual_gate_violations"] += 1
            row_violations.append("visual_gate")
        if distance(row) > max_distance + FLOAT_TOLERANCE:
            counts["distance_violations"] += 1
            row_violations.append("distance")
        if text(row.get("selection_distance_source")) != "distance_to_bbox":
            counts["distance_fallback_rows"] += 1

        if row_violations and len(examples) < 20:
            examples.append(
                {
                    "violations": row_violations,
                    "category": row.get("category"),
                    "scene_id": row.get("scene_id"),
                    "instance_index": row.get("instance_index"),
                    "candidate_index": row.get("candidate_index"),
                    "vis_ratio": vis_ratio(row),
                    "bbox_frac": bbox_frac(row),
                    "selection_distance": distance(row),
                    "selection_distance_source": row.get("selection_distance_source"),
                    "threshold_profile": row.get("threshold_profile"),
                    "candidate_min_image_fraction": min_image,
                    "candidate_min_bbox_fraction": min_bbox,
                    "candidate_max_distance": max_distance,
                    "image_path": row.get("image_path"),
                }
            )

    return {
        "accepted_rows": len(accepted),
        "distance_violations": counts["distance_violations"],
        "visual_gate_violations": counts["visual_gate_violations"],
        "visible_pixel_violations": counts["visible_pixel_violations"],
        "distance_fallback_rows": counts["distance_fallback_rows"],
        "violation_examples": examples,
    }


def build_summary(
    selection_json: Path,
    selection_summary: Dict[str, Any],
    source_rows: Sequence[Dict[str, Any]],
    selected_rows: Sequence[Dict[str, Any]],
    pack_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    missing = sum(not row.get("qa_image_exists") for row in pack_rows)
    bbox_missing = sum(not row.get("qa_bbox_image_exists") for row in pack_rows)
    return {
        "selection_json": str(selection_json),
        "source_candidate_rows": len(source_rows),
        "selected_rows_requested": len(selected_rows),
        "pack_rows": len(pack_rows),
        "missing_selected_images": missing,
        "missing_bbox_visualizations": bbox_missing,
        "status_counts": dict(
            Counter(text(row.get("selection_status")) for row in pack_rows).most_common()
        ),
        "category_counts": dict(
            Counter(text(row.get("category")) for row in pack_rows).most_common()
        ),
        "qa_pick_reason_counts": dict(
            Counter(
                reason
                for row in pack_rows
                for reason in as_list(row.get("qa_pick_reasons"))
            ).most_common()
        ),
        "accepted_audit": accepted_audit(source_rows, selection_summary),
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    data = read_json(args.selection_json)
    selection_summary = data.get("summary") or {}
    source_rows = load_rows(data)
    selected_rows = choose_balanced_rows(source_rows, args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pack_rows = copy_images(
        selected_rows,
        root=args.path_root,
        output_dir=args.output_dir,
        include_missing=args.include_missing,
    )
    summary = build_summary(
        args.selection_json,
        selection_summary,
        source_rows,
        selected_rows,
        pack_rows,
    )
    write_manifest(args.output_dir / "fixed_camera_visual_qa_manifest.csv", pack_rows)
    write_markdown(
        args.output_dir / "fixed_camera_visual_qa.md",
        pack_rows,
        summary,
    )
    (args.output_dir / "fixed_camera_visual_qa_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    summary = run(args)
    print(
        json.dumps(
            {
                "source_candidate_rows": summary["source_candidate_rows"],
                "pack_rows": summary["pack_rows"],
                "missing_selected_images": summary["missing_selected_images"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
