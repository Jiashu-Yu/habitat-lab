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
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_OUTPUT_DIR = Path("outputs/fixed_camera_visual_qa_pack")
IMAGE_SUFFIX_PRIORITY = ("_review.png", "_overlay.png", "_rgb.png", "_mask.png")
BBOX_IMAGE_SUFFIX_PRIORITY = ("_overlay.png", "_rgb.png")
FLOAT_TOLERANCE = 1e-6
BEV_STATUS_STYLES = {
    "accepted": ("accepted", (24, 135, 68)),
    "review": ("review", (230, 145, 25)),
}
BEV_REJECT_REASON_ORDER = [
    "zero_visible",
    "too_small",
    "few_pixels",
    "distance",
    "mask_large",
    "tiny_mask",
    "invalid",
    "other_reject",
]
BEV_REJECT_REASON_STYLES = {
    "zero_visible": ("reject: zero visible", (72, 72, 72)),
    "too_small": ("reject: visual too small", (210, 72, 38)),
    "few_pixels": ("reject: few pixels", (219, 139, 45)),
    "distance": ("reject: distance", (120, 86, 190)),
    "mask_large": ("reject: full/large mask", (38, 145, 180)),
    "tiny_mask": ("reject: tiny mask", (198, 66, 135)),
    "invalid": ("reject: invalid snap/error", (145, 98, 45)),
    "other_reject": ("reject: other", (155, 50, 50)),
}


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
    if len(selected_rows) <= args.max_total_images:
        return selected_rows

    # Keep the hard cap category-balanced. Large runs can add many
    # failing-object diagnostics from alphabetically early categories; a plain
    # sorted slice would starve later categories even though they are present.
    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in selected_rows:
        by_category[text(row.get("category")) or "unknown"].append(row)
    capped: List[Dict[str, Any]] = []
    categories = sorted(by_category)
    while len(capped) < args.max_total_images:
        added_this_round = False
        for category in categories:
            bucket = by_category[category]
            if not bucket:
                continue
            capped.append(bucket.pop(0))
            added_this_round = True
            if len(capped) >= args.max_total_images:
                break
        if not added_this_round:
            break
    return capped


def row_has_existing_image(row: Dict[str, Any], root: Path) -> bool:
    image_path = text(row.get("image_path"))
    if not image_path:
        return False
    return resolve_path(image_path, root).exists()


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


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(value)
            except Exception:
                pass
        return None
    return value


def row_selection_reasons(row: Dict[str, Any]) -> List[str]:
    raw = row.get("selection_reasons")
    parsed = parse_jsonish(raw)
    if isinstance(parsed, (list, tuple)):
        return [text(reason) for reason in parsed if reason is not None]
    if isinstance(parsed, str):
        parts = [part.strip() for part in parsed.split(";")]
        return [part for part in parts if part]
    reasons_text = text(row.get("selection_reasons_text"))
    if reasons_text:
        return [part.strip() for part in reasons_text.split(";") if part.strip()]
    return []


def bev_reason_bucket(row: Dict[str, Any]) -> Tuple[str, str, Tuple[int, int, int]]:
    status = text(row.get("selection_status"))
    if status in BEV_STATUS_STYLES:
        label, color = BEV_STATUS_STYLES[status]
        return status, label, color

    reasons = row_selection_reasons(row)
    reason_text = ";".join(reasons)
    if any(
        flag in reason_text
        for flag in ("full_frame_sentinel_mask", "near_full_frame_bbox")
    ):
        bucket = "mask_large"
    elif "tiny_sentinel_mask" in reason_text:
        bucket = "tiny_mask"
    elif any(
        flag in reason_text
        for flag in ("snap_point_nan", "candidate_error", "nan")
    ):
        bucket = "invalid"
    elif "zero_visible_pixels" in reason_text:
        bucket = "zero_visible"
    elif any(
        marker in reason_text
        for marker in (
            "distance_to_bbox>",
            "distance_to_object>",
            "bbox_distance>",
            "object_distance>",
        )
    ):
        bucket = "distance"
    elif "image_fraction<" in reason_text or "bbox_fraction<" in reason_text:
        bucket = "too_small"
    elif "visible_pixels<" in reason_text:
        bucket = "few_pixels"
    else:
        bucket = "other_reject"
    label, color = BEV_REJECT_REASON_STYLES[bucket]
    return bucket, label, color


def parse_vec3(value: Any) -> Optional[List[float]]:
    parsed = parse_jsonish(value)
    if not isinstance(parsed, (list, tuple)) or len(parsed) < 3:
        return None
    try:
        vals = [float(parsed[i]) for i in range(3)]
    except Exception:
        return None
    if not all(math.isfinite(v) for v in vals):
        return None
    return vals


def row_position(row: Dict[str, Any]) -> Optional[List[float]]:
    agent_state = parse_jsonish(row.get("agent_state"))
    if isinstance(agent_state, dict):
        pos = parse_vec3(agent_state.get("position"))
        if pos is not None:
            return pos
    return parse_vec3(row.get("navigable_position"))


def row_object_bbox(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bbox = parse_jsonish(row.get("object_bbox_static_approx"))
    return bbox if isinstance(bbox, dict) else None


def row_max_distance(row: Dict[str, Any], default: float = 1.0) -> float:
    value = row.get("candidate_max_distance")
    return to_float(value, default=default)


def bbox_frame_xz(
    bbox: Optional[Dict[str, Any]]
) -> Optional[Tuple[List[float], float, float, float]]:
    if not bbox:
        return None
    center = parse_vec3(bbox.get("center"))
    sizes = parse_jsonish(bbox.get("sizes"))
    yaw = bbox.get("yaw_rad")
    if center is not None and isinstance(sizes, (list, tuple)) and len(sizes) >= 3:
        try:
            hx = abs(float(sizes[0])) * 0.5
            hz = abs(float(sizes[2])) * 0.5
            angle = float(yaw) if yaw is not None else 0.0
        except Exception:
            hx = hz = None  # type: ignore[assignment]
        if hx is not None and hz is not None:
            return center, hx, hz, angle
    bmin = parse_vec3(bbox.get("min"))
    bmax = parse_vec3(bbox.get("max"))
    if bmin is None or bmax is None:
        return None
    center = [
        (bmin[0] + bmax[0]) * 0.5,
        (bmin[1] + bmax[1]) * 0.5,
        (bmin[2] + bmax[2]) * 0.5,
    ]
    return center, abs(bmax[0] - bmin[0]) * 0.5, abs(bmax[2] - bmin[2]) * 0.5, 0.0


def bbox_local_to_world_xz(
    center: List[float], yaw: float, local_x: float, local_z: float
) -> Tuple[float, float]:
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    world_x = center[0] + cos_yaw * local_x + sin_yaw * local_z
    world_z = center[2] - sin_yaw * local_x + cos_yaw * local_z
    return world_x, world_z


def bbox_corners_xz(bbox: Optional[Dict[str, Any]]) -> List[Tuple[float, float]]:
    frame = bbox_frame_xz(bbox)
    if frame is None:
        return []
    center, hx, hz, yaw = frame
    return [
        bbox_local_to_world_xz(center, yaw, local_x, local_z)
        for local_x, local_z in [(-hx, -hz), (hx, -hz), (hx, hz), (-hx, hz)]
    ]


def bbox_distance_contour_xz(
    bbox: Optional[Dict[str, Any]], distance: float, segments_per_corner: int = 12
) -> List[Tuple[float, float]]:
    frame = bbox_frame_xz(bbox)
    if frame is None:
        return []
    center, hx, hz, yaw = frame
    radius = max(0.0, distance)
    if radius <= 1e-9:
        return bbox_corners_xz(bbox)

    points: List[Tuple[float, float]] = []
    corners = [
        (hx, hz, 0.0, math.pi * 0.5),
        (-hx, hz, math.pi * 0.5, math.pi),
        (-hx, -hz, math.pi, math.pi * 1.5),
        (hx, -hz, math.pi * 1.5, math.pi * 2.0),
    ]
    for corner_x, corner_z, start, end in corners:
        for idx in range(segments_per_corner + 1):
            angle = start + (end - start) * idx / segments_per_corner
            local_x = corner_x + radius * math.cos(angle)
            local_z = corner_z + radius * math.sin(angle)
            points.append(bbox_local_to_world_xz(center, yaw, local_x, local_z))
    return points


def draw_polyline(draw: Any, points: List[Tuple[float, float]], fill: Any, width: int) -> None:
    if len(points) < 2:
        return
    draw.line(points + [points[0]], fill=fill, width=width)


def draw_bev_images(
    rows: Sequence[Dict[str, Any]], output_dir: Path
) -> List[Dict[str, Any]]:
    try:
        from PIL import Image, ImageDraw  # noqa: PLC0415
    except Exception:
        return []

    by_object: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_object[object_key(row)].append(row)

    out_dir = output_dir / "bev"
    out_dir.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    draw_order = BEV_REJECT_REASON_ORDER + ["review", "accepted"]

    for key, group in sorted(by_object.items()):
        positions = [(row, row_position(row)) for row in group]
        positions = [(row, pos) for row, pos in positions if pos is not None]
        bbox = None
        for row in group:
            bbox = row_object_bbox(row)
            if bbox:
                break
        max_dist = max((row_max_distance(row) for row in group), default=1.0)
        bbox_points = bbox_corners_xz(bbox)
        expanded_bbox_points = bbox_distance_contour_xz(bbox, max_dist)

        xs = [pos[0] for _row, pos in positions]
        zs = [pos[2] for _row, pos in positions]
        xs.extend(point[0] for point in bbox_points + expanded_bbox_points)
        zs.extend(point[1] for point in bbox_points + expanded_bbox_points)
        if not xs or not zs:
            continue

        pad_world = max(0.25, max_dist * 0.35)
        min_x, max_x = min(xs) - pad_world, max(xs) + pad_world
        min_z, max_z = min(zs) - pad_world, max(zs) + pad_world
        if abs(max_x - min_x) < 1e-6:
            min_x -= 0.5
            max_x += 0.5
        if abs(max_z - min_z) < 1e-6:
            min_z -= 0.5
            max_z += 0.5

        width, height, margin = 900, 900, 70
        scale = min(
            (width - 2 * margin) / (max_x - min_x),
            (height - 2 * margin) / (max_z - min_z),
        )

        def project(x: float, z: float) -> Tuple[float, float]:
            px = margin + (x - min_x) * scale
            py = height - margin - (z - min_z) * scale
            return px, py

        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        for gx in range(math.floor(min_x), math.ceil(max_x) + 1):
            x0, y0 = project(float(gx), min_z)
            x1, y1 = project(float(gx), max_z)
            draw.line((x0, y0, x1, y1), fill=(235, 235, 235), width=1)
        for gz in range(math.floor(min_z), math.ceil(max_z) + 1):
            x0, y0 = project(min_x, float(gz))
            x1, y1 = project(max_x, float(gz))
            draw.line((x0, y0, x1, y1), fill=(235, 235, 235), width=1)

        draw_polyline(
            draw,
            [project(x, z) for x, z in expanded_bbox_points],
            fill=(150, 150, 150),
            width=2,
        )
        draw_polyline(
            draw,
            [project(x, z) for x, z in bbox_points],
            fill=(20, 20, 20),
            width=4,
        )

        reason_counts: Counter[str] = Counter()
        rows_by_bucket: Dict[str, List[Tuple[Dict[str, Any], List[float]]]] = defaultdict(list)
        for row, pos in positions:
            bucket, _label, _color = bev_reason_bucket(row)
            reason_counts[bucket] += 1
            rows_by_bucket[bucket].append((row, pos))

        for bucket in draw_order:
            for row, pos in rows_by_bucket.get(bucket, []):
                _bucket, _label, color = bev_reason_bucket(row)
                status = text(row.get("selection_status"))
                px, py = project(pos[0], pos[2])
                radius = 7 if status in {"accepted", "review"} else 5
                draw.ellipse(
                    (px - radius, py - radius, px + radius, py + radius),
                    fill=color,
                    outline=(255, 255, 255),
                    width=1,
                )

        first = group[0]
        counts = Counter(text(row.get("selection_status")) for row in group)
        title = (
            f"{first.get('category')} scene={first.get('scene_id')} "
            f"inst={first.get('instance_index')} cand={len(group)} "
            f"acc={counts.get('accepted', 0)} rev={counts.get('review', 0)} "
            f"rej={counts.get('rejected', 0)} maxdist={max_dist:.2f}m"
        )
        draw.rectangle((0, 0, width, 58), fill=(255, 255, 255))
        draw.text((16, 12), title, fill=(0, 0, 0))
        legend_items: List[Tuple[str, Tuple[int, int, int], int]] = []
        for bucket in ("accepted", "review"):
            if reason_counts.get(bucket):
                label, color = BEV_STATUS_STYLES[bucket]
                legend_items.append((label, color, reason_counts[bucket]))
        for bucket in BEV_REJECT_REASON_ORDER:
            if reason_counts.get(bucket):
                label, color = BEV_REJECT_REASON_STYLES[bucket]
                legend_items.append((label, color, reason_counts[bucket]))
        legend_items.extend(
            [
                ("bbox", (20, 20, 20), 0),
                ("bbox+maxdist", (150, 150, 150), 0),
            ]
        )

        draw.rectangle((0, height - 124, width, height), fill=(255, 255, 255))
        legend_x, legend_y = 16, height - 108
        for label, color, count in legend_items:
            shown_label = f"{label} ({count})" if count else label
            try:
                label_width = int(draw.textlength(shown_label))
            except Exception:
                label_width = len(shown_label) * 7
            item_width = label_width + 48
            if legend_x + item_width > width - 16:
                legend_x = 16
                legend_y += 24
            draw.rectangle(
                (legend_x, legend_y + 2, legend_x + 16, legend_y + 18),
                fill=color,
            )
            draw.text((legend_x + 22, legend_y), shown_label, fill=(0, 0, 0))
            legend_x += item_width

        stem = safe_name(
            f"{first.get('category')}_scene-{first.get('scene_id')}_"
            f"inst-{first.get('instance_index')}_bev",
            max_len=120,
        )
        path = out_dir / f"{stem}.png"
        image.save(path)
        records.append(
            {
                "object_key": key,
                "category": first.get("category"),
                "scene_id": first.get("scene_id"),
                "instance_index": first.get("instance_index"),
                "bev_image": str(path.relative_to(output_dir)),
                "accepted": counts.get("accepted", 0),
                "review": counts.get("review", 0),
                "rejected": counts.get("rejected", 0),
                "bev_reason_counts": dict(reason_counts),
                "has_object_bbox": bool(bbox_points),
            }
        )
    return records


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
        f"- BEV object maps: {summary['bev_map_count']}",
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

    if summary.get("bev_maps"):
        lines.extend(["", "## BEV Candidate Maps", ""])
        for bev in summary["bev_maps"]:
            title = (
                f"{bev.get('category')} scene={bev.get('scene_id')} "
                f"inst={bev.get('instance_index')} "
                f"accepted={bev.get('accepted')} review={bev.get('review')} "
                f"rejected={bev.get('rejected')}"
            )
            if not bev.get("has_object_bbox"):
                title += " (missing object bbox)"
            lines.extend([f"### {title}", "", md_image(text(bev.get("bev_image"))), ""])

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
    bev_maps: Sequence[Dict[str, Any]],
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
        "bev_map_count": len(bev_maps),
        "bev_maps": list(bev_maps),
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
    image_available_rows = [
        row for row in source_rows if row_has_existing_image(row, args.path_root)
    ]
    sampling_rows = (
        source_rows
        if args.include_missing or not image_available_rows
        else image_available_rows
    )
    selected_rows = choose_balanced_rows(sampling_rows, args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pack_rows = copy_images(
        selected_rows,
        root=args.path_root,
        output_dir=args.output_dir,
        include_missing=args.include_missing,
    )
    bev_maps = draw_bev_images(source_rows, args.output_dir)
    summary = build_summary(
        args.selection_json,
        selection_summary,
        source_rows,
        selected_rows,
        pack_rows,
        bev_maps,
    )
    summary["source_rows_with_existing_images"] = len(image_available_rows)
    summary["categories_with_existing_images"] = dict(
        Counter(text(row.get("category")) for row in image_available_rows).most_common()
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
                "bev_map_count": summary["bev_map_count"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
