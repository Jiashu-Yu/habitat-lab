#!/usr/bin/env python3
"""Build a curated visual QA pack from fixed-camera viewpoint selection output.

This script is intentionally static: it reads selector JSON, copies existing
debug review/overlay images into a compact folder, and writes CSV/Markdown
manifests. It does not import Habitat-Sim, render, train, or modify dataset
shards.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_OUTPUT_DIR = Path("outputs/fixed_camera_visual_qa_pack")
IMAGE_SUFFIX_PRIORITY = ("_review.png", "_overlay.png", "_rgb.png", "_mask.png")


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
    return to_float(row.get("distance_to_object"), default=999999.0)


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
    category = safe_name(row.get("category"))
    status = safe_name(row.get("selection_status"))
    scene = safe_name(row.get("scene_id"))
    instance = safe_name(row.get("instance_index"))
    candidate = safe_name(row.get("candidate_index"))
    frac = f"{vis_ratio(row):.4f}".replace(".", "p")
    source = Path(text(row.get("image_path"))).name or "image.png"
    suffix = Path(source).suffix or ".png"
    stem = (
        f"{category}_{status}_scene-{scene}_inst-{instance}_"
        f"cand-{candidate}_frac-{frac}"
    )
    return output_dir / "images" / category / status / f"{safe_name(stem)}{suffix}"


def copy_images(
    rows: Sequence[Dict[str, Any]], root: Path, output_dir: Path, include_missing: bool
) -> List[Dict[str, Any]]:
    copied_rows: List[Dict[str, Any]] = []
    missing_count = 0
    for row in rows:
        image_path = text(row.get("image_path"))
        src = resolve_path(image_path, root) if image_path else Path("")
        dst = image_target_path(row, output_dir)
        out_row = dict(row)
        out_row["source_image_abs"] = str(src) if image_path else ""
        out_row["qa_image"] = str(dst.relative_to(output_dir))
        out_row["qa_image_exists"] = False
        if image_path and src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            out_row["qa_image_exists"] = True
        else:
            missing_count += 1
            if not include_missing:
                continue
        copied_rows.append(out_row)
    for row in copied_rows:
        row["missing_image_count_for_pack"] = missing_count
    return copied_rows


def write_manifest(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    fields = [
        "qa_image",
        "qa_image_exists",
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
        "distance_to_object",
        "distance_to_bbox",
        "source_image_abs",
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


def build_summary(
    selection_json: Path,
    source_rows: Sequence[Dict[str, Any]],
    selected_rows: Sequence[Dict[str, Any]],
    pack_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    missing = sum(not row.get("qa_image_exists") for row in pack_rows)
    return {
        "selection_json": str(selection_json),
        "source_candidate_rows": len(source_rows),
        "selected_rows_requested": len(selected_rows),
        "pack_rows": len(pack_rows),
        "missing_selected_images": missing,
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
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    data = read_json(args.selection_json)
    source_rows = load_rows(data)
    selected_rows = choose_balanced_rows(source_rows, args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pack_rows = copy_images(
        selected_rows,
        root=args.path_root,
        output_dir=args.output_dir,
        include_missing=args.include_missing,
    )
    summary = build_summary(args.selection_json, source_rows, selected_rows, pack_rows)
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
