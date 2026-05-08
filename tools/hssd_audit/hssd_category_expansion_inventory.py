#!/usr/bin/env python3
"""Static HSSD category expansion inventory.

This script reads HSSD scene metadata and scene_instance JSON files without
importing Habitat or launching simulation. It builds a first-pass inventory of
semantic object categories that might be usable for expanded ObjectNav targets.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


NATIVE_HSSD_OBJECTNAV_CATEGORIES = {
    "bed",
    "chair",
    "couch",
    "potted_plant",
    "toilet",
    "tv",
}

STRUCTURAL_OR_UNSUITABLE_TERMS = {
    "wall",
    "floor",
    "ceiling",
    "roof",
    "stairs",
    "stair",
    "railing",
    "rail",
    "banister",
    "column",
    "beam",
    "baseboard",
    "molding",
    "trim",
    "window",
    "door",
    "room",
    "unknown",
    "misc",
    "other",
    "part",
    "object",
    "background",
    "surface",
    "structure",
    "architecture",
}

COMMON_HOUSEHOLD_TARGET_HINTS = {
    "bed",
    "chair",
    "seat",
    "couch",
    "sofa",
    "toilet",
    "tv",
    "television",
    "table",
    "desk",
    "cabinet",
    "nightstand",
    "wardrobe",
    "dresser",
    "shelf",
    "bookshelf",
    "rack",
    "counter",
    "sink",
    "sink_cabinet",
    "bathtub",
    "shower",
    "plant",
    "flowerpot",
    "lamp",
    "stool",
    "bench",
    "ottoman",
    "trash",
    "bin",
    "basket",
    "microwave",
    "oven",
    "refrigerator",
    "fridge",
    "washer",
    "washer_dryer",
    "washing_machine",
    "dryer",
    "dishwasher",
    "piano",
    "mirror",
    "monitor",
    "laptop",
    "box",
    "vase",
    "picture",
    "painting",
}

PRACTICAL_FIRST_EXPANSION_PRIORITY = [
    "table",
    "cabinet",
    "dresser",
    "stool",
    "sink_cabinet",
    "fridge",
    "bathtub",
    "wardrobe",
    "shower",
    "washer_dryer",
    "basket",
    "bin",
    "bench",
    "desk",
    "counter",
    "sink",
    "nightstand",
    "kitchen_lower_cabinet",
    "laundry_basket",
    "oven",
    "microwave",
    "dishwasher",
    "vase",
    "laptop",
]

NATIVE_HSSD_OBJECTNAV_EQUIVALENTS = {
    "bed": "bed",
    "seat": "chair",
    "chair": "chair",
    "couch": "couch",
    "sofa": "couch",
    "plant": "potted_plant",
    "flowerpot": "potted_plant",
    "potted_plant": "potted_plant",
    "toilet": "toilet",
    "tv": "tv",
    "led_tv": "tv",
    "television": "tv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Static HSSD semantic category inventory for ObjectNav expansion."
    )
    parser.add_argument(
        "--scene-root",
        default="data/scene_datasets/hssd-hab",
        help="Root of the HSSD scene dataset.",
    )
    parser.add_argument(
        "--scene-dir",
        default="scenes",
        help="Scene instance subdirectory to count. Defaults to cluttered scenes/.",
    )
    parser.add_argument(
        "--output-json",
        default="outputs/hssd_category_expansion_inventory.json",
        help="Path for machine-readable JSON output.",
    )
    parser.add_argument(
        "--output-md",
        default="outputs/hssd_category_expansion_inventory.md",
        help="Path for Markdown report output.",
    )
    parser.add_argument(
        "--rare-scene-threshold",
        type=int,
        default=3,
        help="Scene-count threshold below which categories are treated as rare.",
    )
    parser.add_argument(
        "--rare-instance-threshold",
        type=int,
        default=5,
        help="Instance-count threshold below which categories are treated as rare.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def norm_category(value: Any) -> str:
    text = norm_text(value).lower()
    text = text.replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def template_candidates(template_name: str) -> list[str]:
    name = norm_text(template_name)
    out = []
    if name:
        out.append(name)
    if "_part_" in name:
        out.append(name.split("_part_", 1)[0])
    if "_:" in name:
        out.append(name.split("_:", 1)[0])
    # Some metadata ids are plain hashes while instances may carry suffixes.
    if ":" in name:
        out.append(name.split(":", 1)[0])
    seen = set()
    deduped = []
    for item in out:
        if item and item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def first_present(mapping: dict[str, Any], fields: list[str]) -> str:
    for field in fields:
        if field in mapping and norm_text(mapping[field]):
            return norm_text(mapping[field])
    return ""


def parse_vec(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        vals = value
    else:
        text = norm_text(value)
        if not text:
            return None
        text = text.replace("[", "").replace("]", "")
        vals = [part.strip() for part in text.split(",")]
    parsed: list[float] = []
    for part in vals:
        try:
            parsed.append(float(part))
        except (TypeError, ValueError):
            return None
    if len(parsed) != 3 or not all(math.isfinite(x) for x in parsed):
        return None
    return parsed


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    rank = (len(xs) - 1) * pct
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - rank) + xs[hi] * (rank - lo)


def numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not clean:
        return {
            "count": 0,
            "min": None,
            "p25": None,
            "median": None,
            "mean": None,
            "p75": None,
            "max": None,
        }
    return {
        "count": len(clean),
        "min": min(clean),
        "p25": percentile(clean, 0.25),
        "median": median(clean),
        "mean": mean(clean),
        "p75": percentile(clean, 0.75),
        "max": max(clean),
    }


def top_items(counter: Counter[str], n: int = 10) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common(n)]


def discover_metadata(scene_root: Path) -> dict[str, Any]:
    metadata = {
        "scene_root": str(scene_root),
        "scene_dirs": [],
        "metadata_files": {},
    }
    for dirname in ["scenes", "scenes-uncluttered", "semantics", "metadata", "objects"]:
        path = scene_root / dirname
        metadata["scene_dirs"].append(
            {
                "path": str(path),
                "exists": path.exists(),
                "scene_instance_files": len(list(path.glob("*.scene_instance.json")))
                if path.exists()
                else 0,
            }
        )
    files = {
        "semantics_objects_csv": scene_root / "semantics" / "objects.csv",
        "semantic_lexicon_json": scene_root
        / "semantics"
        / "hssd-hab_semantic_lexicon.json",
        "condensed_semantics_csv": scene_root
        / "metadata"
        / "hssd_obj_semantics_condensed.csv",
        "object_categories_filtered_csv": scene_root
        / "metadata"
        / "object_categories_filtered.csv",
        "objects_json": scene_root / "metadata" / "objects.json",
        "fpmodels_with_decomposed_csv": scene_root
        / "metadata"
        / "fpmodels-with-decomposed.csv",
        "scene_splits_yaml": scene_root / "scene_splits.yaml",
    }
    for key, path in files.items():
        metadata["metadata_files"][key] = {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    return metadata


def load_object_metadata(scene_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = defaultdict(dict)
    source_counts: Counter[str] = Counter()

    objects_rows = read_csv(scene_root / "semantics" / "objects.csv")
    for row in objects_rows:
        obj_id = first_present(row, ["id", "Object Hash"])
        if not obj_id:
            continue
        entry = by_id[obj_id]
        entry["id"] = obj_id
        entry["name"] = first_present(row, ["name"]) or entry.get("name", "")
        entry["wnsynsetkey"] = first_present(row, ["wnsynsetkey"])
        entry["main_wnsynsetkey"] = first_present(row, ["main_wnsynsetkey"])
        entry["main_category"] = norm_category(first_present(row, ["main_category"]))
        entry["super_category"] = norm_category(first_present(row, ["super_category"]))
        entry["foundIn"] = first_present(row, ["foundIn"])
        entry["tags"] = first_present(row, ["floorplanner-category-tags"])
        dims = parse_vec(first_present(row, ["aligned.dims"])) or parse_vec(
            first_present(row, ["dims"])
        )
        if dims:
            entry["dims"] = dims
        source_counts["semantics_objects_csv"] += 1

    fp_rows = read_csv(scene_root / "metadata" / "fpmodels-with-decomposed.csv")
    for row in fp_rows:
        obj_id = first_present(row, ["id"])
        if not obj_id:
            continue
        entry = by_id[obj_id]
        entry["id"] = obj_id
        entry.setdefault("name", first_present(row, ["name"]))
        entry.setdefault("main_category", norm_category(first_present(row, ["main_category"])))
        entry.setdefault("super_category", norm_category(first_present(row, ["super_category"])))
        dims = parse_vec(first_present(row, ["aligned.dims"])) or parse_vec(
            first_present(row, ["dims"])
        )
        if dims and "dims" not in entry:
            entry["dims"] = dims
        if first_present(row, ["decomposedFrom"]):
            entry["decomposedFrom"] = first_present(row, ["decomposedFrom"])
        if first_present(row, ["decomposedInto"]):
            entry["decomposedInto"] = first_present(row, ["decomposedInto"])
        source_counts["fpmodels_with_decomposed_csv"] += 1

    condensed_rows = read_csv(scene_root / "metadata" / "hssd_obj_semantics_condensed.csv")
    condensed_field = ""
    primary_field = ""
    hash_field = ""
    pickable_field = ""
    articulated_field = ""
    if condensed_rows:
        fields = list(condensed_rows[0].keys())
        for field in fields:
            lower = field.lower()
            if "object hash" in lower:
                hash_field = field
            if "condensed" in lower and "semantic" in lower:
                condensed_field = field
            if "primary semantic category" in lower:
                primary_field = field
            if "pickable" in lower:
                pickable_field = field
            if "articulated" in lower:
                articulated_field = field
    for row in condensed_rows:
        obj_id = first_present(row, [hash_field]) if hash_field else ""
        if not obj_id:
            continue
        entry = by_id[obj_id]
        entry["id"] = obj_id
        if condensed_field:
            entry["condensed_category"] = norm_category(row.get(condensed_field, ""))
        if primary_field:
            entry["primary_semantic_category"] = norm_category(row.get(primary_field, ""))
        if pickable_field:
            entry["is_pickable"] = norm_text(row.get(pickable_field, ""))
        if articulated_field:
            entry["is_articulated_object"] = norm_text(row.get(articulated_field, ""))
        source_counts["condensed_semantics_csv"] += 1

    filtered_rows = read_csv(scene_root / "metadata" / "object_categories_filtered.csv")
    for row in filtered_rows:
        obj_id = first_present(row, ["id"])
        if not obj_id:
            continue
        entry = by_id[obj_id]
        entry["id"] = obj_id
        entry["clean_category"] = norm_category(first_present(row, ["clean_category"]))
        source_counts["object_categories_filtered_csv"] += 1

    objects_json = scene_root / "metadata" / "objects.json"
    if objects_json.exists():
        payload = load_json(objects_json)
        if isinstance(payload, dict):
            for obj_id, obj in payload.items():
                if not isinstance(obj, dict):
                    continue
                entry = by_id[obj_id]
                entry["id"] = obj_id
                entry.setdefault("name", norm_text(obj.get("name")))
                if isinstance(obj.get("scene_counts"), dict):
                    entry["scene_counts"] = obj["scene_counts"]
                if isinstance(obj.get("tags"), list):
                    entry["object_json_tags"] = obj["tags"]
                source_counts["objects_json"] += 1

    return dict(by_id), {"source_row_counts": dict(source_counts)}


def resolve_metadata(
    template_name: str, object_metadata: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any], list[str]]:
    tried = template_candidates(template_name)
    for candidate in tried:
        if candidate in object_metadata:
            return candidate, object_metadata[candidate], tried
    return tried[0] if tried else "", {}, tried


def choose_category(meta: dict[str, Any]) -> tuple[str, str]:
    category_fields = [
        ("condensed_category", meta.get("condensed_category")),
        ("primary_semantic_category", meta.get("primary_semantic_category")),
        ("main_category", meta.get("main_category")),
        ("clean_category", meta.get("clean_category")),
        ("super_category", meta.get("super_category")),
    ]
    for source, value in category_fields:
        cat = norm_category(value)
        if cat and cat not in {"na", "n_a", "none", "nan", "null"}:
            return cat, source
    return "unknown", "unresolved"


def unsuitable_reason_for_category(category: str) -> str | None:
    cat = norm_category(category)
    if not cat:
        return "empty category"
    tokens = set(cat.split("_"))
    for term in STRUCTURAL_OR_UNSUITABLE_TERMS:
        if term == cat or term in tokens:
            return f"structural_or_unsuitable_term:{term}"
    return None


def scaled_dims(dims: list[float] | None, scale: list[float] | None) -> list[float] | None:
    if not dims:
        return None
    if not scale:
        scale = [1.0, 1.0, 1.0]
    if len(scale) != 3:
        scale = [1.0, 1.0, 1.0]
    return [abs(dims[i] * scale[i]) for i in range(3)]


def category_hint_is_common_target(category: str) -> bool:
    cat = norm_category(category)
    tokens = set(cat.split("_"))
    return any(hint == cat or hint in tokens or hint in cat for hint in COMMON_HOUSEHOLD_TARGET_HINTS)


def classify_category(
    category: str,
    instance_count: int,
    scene_count: int,
    y_summary: dict[str, Any],
    height_summary: dict[str, Any],
    max_extent_summary: dict[str, Any],
    rare_scene_threshold: int,
    rare_instance_threshold: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    reject_reason = unsuitable_reason_for_category(category)
    if reject_reason:
        reasons.append(reject_reason)
        return "reject", reasons

    if instance_count < rare_instance_threshold or scene_count < rare_scene_threshold:
        reasons.append(
            f"rare: instances={instance_count}, scenes={scene_count}, "
            f"thresholds={rare_instance_threshold}/{rare_scene_threshold}"
        )

    median_height = height_summary.get("median")
    median_max_extent = max_extent_summary.get("median")
    median_y = y_summary.get("median")
    p75_y = y_summary.get("p75")

    if median_height is not None and median_height < 0.08:
        reasons.append(f"possibly_too_small_height_median={median_height:.3f}")
    if median_max_extent is not None and median_max_extent < 0.15:
        reasons.append(f"possibly_too_small_max_extent_median={median_max_extent:.3f}")
    if (
        median_y is not None
        and median_y < 0.05
        and median_height is not None
        and median_height < 0.20
        and median_max_extent is not None
        and median_max_extent < 0.40
    ):
        reasons.append(
            f"possibly_too_low_and_small:origin_y={median_y:.3f},height={median_height:.3f}"
        )
    if p75_y is not None and p75_y > 1.8:
        reasons.append(f"possibly_too_high_origin_y_p75={p75_y:.3f}")

    common_target = category_hint_is_common_target(category)
    if not common_target:
        reasons.append("not_in_common_household_target_hint_list")

    blocking_reasons = [
        r
        for r in reasons
        if r.startswith("rare:")
        or r.startswith("possibly_too_small")
        or r.startswith("possibly_too_high")
        or r.startswith("possibly_too_low_and_small")
    ]

    if category in NATIVE_HSSD_OBJECTNAV_CATEGORIES:
        if blocking_reasons:
            return "medium-confidence", reasons + ["native_exact_but_has_static_caution"]
        return "high-confidence", reasons + ["native_hssd_objectnav_category"]

    if category in NATIVE_HSSD_OBJECTNAV_EQUIVALENTS:
        if blocking_reasons:
            return (
                "medium-confidence",
                reasons
                + [
                    "native_hssd_objectnav_equivalent_with_static_caution:"
                    + NATIVE_HSSD_OBJECTNAV_EQUIVALENTS[category]
                ],
            )
        return (
            "high-confidence",
            reasons
            + [
                "native_hssd_objectnav_equivalent:"
                + NATIVE_HSSD_OBJECTNAV_EQUIVALENTS[category]
            ],
        )

    if common_target and scene_count >= 10 and instance_count >= 20 and not blocking_reasons:
        return "high-confidence", reasons + ["common_household_target_with_good_coverage"]

    if scene_count >= rare_scene_threshold and instance_count >= rare_instance_threshold:
        return "medium-confidence", reasons

    return "reject", reasons


def scan_scene_instances(
    scene_root: Path,
    scene_dir_name: str,
    object_metadata: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scene_dir = scene_root / scene_dir_name
    scene_files = sorted(scene_dir.glob("*.scene_instance.json"))

    category_records: dict[str, dict[str, Any]] = {}
    unresolved_templates: Counter[str] = Counter()
    category_source_counts: Counter[str] = Counter()
    scenes_with_parse_errors: list[dict[str, str]] = []
    sample_instances: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for scene_path in scene_files:
        scene_id = scene_path.stem.replace(".scene_instance", "")
        try:
            payload = load_json(scene_path)
        except Exception as exc:  # noqa: BLE001
            scenes_with_parse_errors.append({"path": str(scene_path), "error": repr(exc)})
            continue
        object_instances = payload.get("object_instances", [])
        if not isinstance(object_instances, list):
            continue
        for idx, inst in enumerate(object_instances):
            if not isinstance(inst, dict):
                continue
            template_name = norm_text(inst.get("template_name"))
            resolved_id, meta, tried = resolve_metadata(template_name, object_metadata)
            if not meta:
                unresolved_templates[template_name or "<empty>"] += 1
            category, category_source = choose_category(meta)
            category_source_counts[category_source] += 1

            translation = parse_vec(inst.get("translation"))
            scale = parse_vec(inst.get("non_uniform_scale"))
            dims = meta.get("dims") if isinstance(meta.get("dims"), list) else None
            sdims = scaled_dims(dims, scale)
            height = sdims[1] if sdims else None
            max_extent = max(sdims) if sdims else None
            volume = sdims[0] * sdims[1] * sdims[2] if sdims else None
            footprint_xz = sdims[0] * sdims[2] if sdims else None

            rec = category_records.setdefault(
                category,
                {
                    "category": category,
                    "instance_count": 0,
                    "scene_ids": set(),
                    "per_scene_count": Counter(),
                    "category_source_count": Counter(),
                    "metadata_id_count": Counter(),
                    "template_name_count": Counter(),
                    "object_names": Counter(),
                    "y_values": [],
                    "height_values": [],
                    "max_extent_values": [],
                    "volume_values": [],
                    "footprint_xz_values": [],
                    "missing_metadata_count": 0,
                    "missing_dims_count": 0,
                    "missing_translation_count": 0,
                },
            )
            rec["instance_count"] += 1
            rec["scene_ids"].add(scene_id)
            rec["per_scene_count"][scene_id] += 1
            rec["category_source_count"][category_source] += 1
            rec["metadata_id_count"][resolved_id or "<unresolved>"] += 1
            rec["template_name_count"][template_name or "<empty>"] += 1
            if norm_text(meta.get("name")):
                rec["object_names"][norm_text(meta.get("name"))] += 1
            if not meta:
                rec["missing_metadata_count"] += 1
            if sdims is None:
                rec["missing_dims_count"] += 1
            if translation is None:
                rec["missing_translation_count"] += 1
            if translation:
                rec["y_values"].append(translation[1])
            if height is not None:
                rec["height_values"].append(height)
            if max_extent is not None:
                rec["max_extent_values"].append(max_extent)
            if volume is not None:
                rec["volume_values"].append(volume)
            if footprint_xz is not None:
                rec["footprint_xz_values"].append(footprint_xz)

            if len(sample_instances[category]) < 5:
                sample_instances[category].append(
                    {
                        "scene_id": scene_id,
                        "instance_index": idx,
                        "template_name": template_name,
                        "resolved_metadata_id": resolved_id,
                        "category": category,
                        "category_source": category_source,
                        "object_name": norm_text(meta.get("name")),
                        "translation": translation,
                        "non_uniform_scale": scale,
                        "metadata_dims": dims,
                        "scaled_dims_static_approx": sdims,
                        "tried_metadata_keys": tried,
                    }
                )

    category_summaries: dict[str, Any] = {}
    for category, rec in category_records.items():
        per_scene_values = list(rec["per_scene_count"].values())
        y_summary = numeric_summary(rec["y_values"])
        height_summary = numeric_summary(rec["height_values"])
        max_extent_summary = numeric_summary(rec["max_extent_values"])
        volume_summary = numeric_summary(rec["volume_values"])
        footprint_summary = numeric_summary(rec["footprint_xz_values"])
        category_summaries[category] = {
            "category": category,
            "instance_count": rec["instance_count"],
            "scene_count": len(rec["scene_ids"]),
            "is_native_hssd_objectnav_category": category in NATIVE_HSSD_OBJECTNAV_CATEGORIES,
            "native_hssd_objectnav_equivalent_category": NATIVE_HSSD_OBJECTNAV_EQUIVALENTS.get(
                category
            ),
            "per_scene_count_summary": numeric_summary([float(v) for v in per_scene_values]),
            "top_scenes": top_items(rec["per_scene_count"], 10),
            "category_source_count": dict(rec["category_source_count"]),
            "top_metadata_ids": top_items(rec["metadata_id_count"], 10),
            "top_template_names": top_items(rec["template_name_count"], 10),
            "top_object_names": top_items(rec["object_names"], 10),
            "object_origin_y_distribution": y_summary,
            "bbox_height_distribution_static_approx": height_summary,
            "bbox_max_extent_distribution_static_approx": max_extent_summary,
            "bbox_volume_distribution_static_approx": volume_summary,
            "bbox_footprint_xz_distribution_static_approx": footprint_summary,
            "missing_metadata_count": rec["missing_metadata_count"],
            "missing_dims_count": rec["missing_dims_count"],
            "missing_translation_count": rec["missing_translation_count"],
            "sample_instances": sample_instances[category],
        }

    summary = {
        "scene_dir": str(scene_dir),
        "scene_instance_files": len(scene_files),
        "parse_errors": scenes_with_parse_errors,
        "total_instances": sum(v["instance_count"] for v in category_summaries.values()),
        "unique_categories": len(category_summaries),
        "category_source_counts": dict(category_source_counts),
        "unresolved_template_count": sum(unresolved_templates.values()),
        "top_unresolved_templates": top_items(unresolved_templates, 20),
    }
    return category_summaries, summary


def add_classifications(
    category_summaries: dict[str, Any], rare_scene_threshold: int, rare_instance_threshold: int
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "high-confidence": [],
        "medium-confidence": [],
        "reject": [],
    }
    for category, rec in category_summaries.items():
        classification, reasons = classify_category(
            category=category,
            instance_count=rec["instance_count"],
            scene_count=rec["scene_count"],
            y_summary=rec["object_origin_y_distribution"],
            height_summary=rec["bbox_height_distribution_static_approx"],
            max_extent_summary=rec["bbox_max_extent_distribution_static_approx"],
            rare_scene_threshold=rare_scene_threshold,
            rare_instance_threshold=rare_instance_threshold,
        )
        rec["target_candidate_class"] = classification
        rec["target_candidate_reasons"] = reasons
        buckets[classification].append(rec)

    for records in buckets.values():
        records.sort(key=lambda r: (-r["scene_count"], -r["instance_count"], r["category"]))

    return {
        "high_confidence_categories": [
            compact_category_for_listing(r) for r in buckets["high-confidence"]
        ],
        "medium_confidence_categories": [
            compact_category_for_listing(r) for r in buckets["medium-confidence"]
        ],
        "reject_categories": [compact_category_for_listing(r) for r in buckets["reject"]],
        "bucket_counts": {key: len(value) for key, value in buckets.items()},
    }


def compact_category_for_listing(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": rec["category"],
        "instance_count": rec["instance_count"],
        "scene_count": rec["scene_count"],
        "is_native_hssd_objectnav_category": rec["is_native_hssd_objectnav_category"],
        "native_hssd_objectnav_equivalent_category": rec[
            "native_hssd_objectnav_equivalent_category"
        ],
        "median_origin_y": rec["object_origin_y_distribution"]["median"],
        "median_height_static_approx": rec["bbox_height_distribution_static_approx"]["median"],
        "median_max_extent_static_approx": rec["bbox_max_extent_distribution_static_approx"][
            "median"
        ],
        "top_object_names": rec["top_object_names"][:3],
        "reasons": rec["target_candidate_reasons"][:5],
    }


def build_practical_first_expansion_shortlist(category_summaries: dict[str, Any]) -> dict[str, Any]:
    native_controls = []
    expansion = []
    caution = []

    for category in ["seat", "bed", "couch", "plant", "flowerpot", "toilet", "tv", "led_tv"]:
        if category in category_summaries:
            native_controls.append(compact_category_for_listing(category_summaries[category]))

    for category in PRACTICAL_FIRST_EXPANSION_PRIORITY:
        rec = category_summaries.get(category)
        if not rec:
            continue
        if rec.get("target_candidate_class") == "high-confidence":
            expansion.append(compact_category_for_listing(rec))
        else:
            caution.append(compact_category_for_listing(rec))

    for category in [
        "picture",
        "picture_frame",
        "mirror",
        "painting",
        "lamp",
        "shelf",
        "clock",
        "showerhead",
        "towel_rack",
        "shower_tap",
        "toilet_paper",
        "tablet",
        "tissue_box",
        "desk_clutter",
    ]:
        rec = category_summaries.get(category)
        if rec:
            item = compact_category_for_listing(rec)
            item["extra_caution"] = (
                "wall-mounted, high, small, broad, or semantically noisy category; "
                "requires fixed-camera visibility and manual spot checks before use"
            )
            caution.append(item)

    return {
        "native_or_native_equivalent_controls": native_controls,
        "recommended_non_native_first_expansion": expansion,
        "fixed_camera_or_label_caution": caution,
    }


def build_viewpoint_generation_design() -> dict[str, Any]:
    return {
        "goal": (
            "Generate target viewpoints for expanded HSSD semantic object categories "
            "that are valid under the evaluation policy's fixed camera pitch."
        ),
        "required_static_inputs": [
            "scene_id and scene_instance path",
            "object instance template_name / resolved metadata id",
            "semantic category chosen for ObjectNav target",
            "object translation, rotation, scale",
            "object dimensions or bounding box approximation when available",
            "agent embodiment: height, radius, camera height, HFOV, resolution, fixed pitch",
            "navmesh/pathfinder access for candidate navigability and geodesic distance",
            "semantic render or object-id mask for visibility scoring",
        ],
        "candidate_position_checks": [
            "sample candidate positions around object at multiple radii/yaw angles",
            "snap or reject positions using navmesh/pathfinder",
            "reject positions on a different floor/island from the object when determinable",
            "orient agent yaw toward object center; keep camera pitch fixed",
            "enforce min/max Euclidean and geodesic distance to object",
            "reject collisions using target agent radius/height",
        ],
        "fixed_camera_visibility_checks": [
            "render semantic/object-id mask from fixed-pitch camera only",
            "count visible target pixels",
            "compute target mask bounding box and image-area fraction",
            "compute IoU or coverage score using projected object mask/bbox",
            "reject viewpoints that only pass with look_up/look_down/tilt",
            "store camera assumptions with generated dataset metadata",
        ],
        "recommended_first_thresholds_to_sweep": {
            "min_visible_pixels": [100, 500, 1000],
            "min_visible_image_fraction": [0.001, 0.005, 0.01],
            "min_viewpoints_per_object": [3, 5, 10],
            "distance_to_object_meters": ["0.5-3.0 sweep, category-dependent"],
            "success_distance_meters": [0.1, 0.25, 0.5],
        },
        "outputs_per_viewpoint": [
            "agent_state.position",
            "agent_state.rotation",
            "camera_hfov/resolution/pitch used for generation",
            "visible_pixel_count",
            "visible_image_fraction",
            "iou_or_coverage_score",
            "euclidean_distance_to_object",
            "geodesic_distance_to_object_or_viewpoint when available",
            "failure reason for rejected candidates",
        ],
        "quality_gates": [
            "each accepted object should have at least the chosen min_viewpoints_per_object",
            "category-level viewpoint count distribution should not be dominated by 0-1 viewpoint objects",
            "accepted viewpoints should work without tilt actions",
            "visual spot checks should confirm object/category correctness before training",
            "episode success regions should be regenerated after category expansion",
        ],
    }


def md_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int | None = None) -> str:
    shown = rows[:limit] if limit is not None else rows
    if not shown:
        return "_None._\n"
    header = "| " + " | ".join(title for title, _ in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in shown:
        vals = []
        for _, key in columns:
            value = row.get(key)
            if isinstance(value, float):
                vals.append(f"{value:.3f}")
            elif value is None:
                vals.append("")
            elif isinstance(value, list):
                vals.append("; ".join(str(v) for v in value[:3]))
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals).replace("\n", " ") + " |")
    return "\n".join(lines) + "\n"


def reasons_text(item: dict[str, Any]) -> str:
    reasons = item.get("reasons") or []
    if not reasons:
        return ""
    return "; ".join(str(r) for r in reasons[:3])


def build_markdown(result: dict[str, Any]) -> str:
    inventory = result["inventory"]
    classification = result["classification"]
    high = classification["high_confidence_categories"]
    medium = classification["medium_confidence_categories"]
    reject = classification["reject_categories"]

    def listing_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in items:
            rows.append(
                {
                    "category": item["category"],
                    "instances": item["instance_count"],
                    "scenes": item["scene_count"],
                    "native6": "yes"
                    if item["is_native_hssd_objectnav_category"]
                    else "no",
                    "native_equiv": item["native_hssd_objectnav_equivalent_category"] or "",
                    "median_y": item["median_origin_y"],
                    "median_height": item["median_height_static_approx"],
                    "median_extent": item["median_max_extent_static_approx"],
                    "reasons": reasons_text(item),
                }
            )
        return rows

    lines = [
        "# HSSD Category Expansion Inventory",
        "",
        "This is a static, read-only inventory. It reads HSSD metadata and scene_instance JSON files only. It does not run Habitat simulation, render images, train models, or modify source/dataset files.",
        "",
        "## Inputs Inspected",
        "",
        f"- Scene root: `{result['metadata_discovery']['scene_root']}`",
        f"- Scene instance directory counted: `{inventory['scene_dir']}`",
        f"- Scene instance files: {inventory['scene_instance_files']}",
        f"- Total object instances counted: {inventory['total_instances']}",
        f"- Unique resolved categories: {inventory['unique_categories']}",
        f"- Unresolved template instances: {inventory['unresolved_template_count']}",
        "",
        "Metadata files discovered:",
    ]
    for name, info in result["metadata_discovery"]["metadata_files"].items():
        lines.append(f"- `{name}`: `{info['path']}` exists={info['exists']} size={info['size_bytes']}")
    lines.extend(
        [
            "",
            "## Classification Summary",
            "",
            f"- High-confidence categories: {classification['bucket_counts']['high-confidence']}",
            f"- Medium-confidence categories: {classification['bucket_counts']['medium-confidence']}",
            f"- Reject categories: {classification['bucket_counts']['reject']}",
            "",
            "Classification is heuristic. It uses static metadata only: category names, instance/scene coverage, object origin y, and approximate dimensions from metadata plus instance scale. It does not prove visual recognizability or navigability.",
            "",
            "## High-confidence Target Candidates",
            "",
            md_table(
                listing_rows(high),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("native6", "native6"),
                    ("native_equiv", "native_equiv"),
                    ("median_y", "median_y"),
                    ("median_height", "median_height"),
                    ("median_extent", "median_extent"),
                    ("notes", "reasons"),
                ],
                limit=80,
            ),
            "",
            "## Medium-confidence Target Candidates",
            "",
            md_table(
                listing_rows(medium),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("native6", "native6"),
                    ("native_equiv", "native_equiv"),
                    ("median_y", "median_y"),
                    ("median_height", "median_height"),
                    ("median_extent", "median_extent"),
                    ("notes", "reasons"),
                ],
                limit=120,
            ),
            "",
            "## Reject / Unsuitable Categories",
            "",
            "These are rejected by first-pass heuristics because they are structural, unknown/misc/part-like, too rare, too small/high/low by static metadata, or not plausible standalone ObjectNav targets. Some may be recoverable after manual review.",
            "",
            md_table(
                listing_rows(reject),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("native6", "native6"),
                    ("native_equiv", "native_equiv"),
                    ("median_y", "median_y"),
                    ("median_height", "median_height"),
                    ("median_extent", "median_extent"),
                    ("notes", "reasons"),
                ],
                limit=160,
            ),
            "",
            "## Category Inventory Details",
            "",
            "The JSON output contains full per-category records, including top scenes, top metadata IDs, top object names, static y/dimension distributions, and sample instances.",
            "",
            "Important static caveats:",
            "",
            "- `translation[1]` is treated as object origin height, not guaranteed physical bbox center.",
            "- Metadata dimensions are approximate and then multiplied by `non_uniform_scale`; rotations are not used for oriented bbox reconstruction.",
            "- Categories come from HSSD semantic metadata, with priority: condensed category, primary semantic category, main category, clean category, then super category.",
            "- Fixed-camera visibility cannot be proven from metadata alone; it requires rendering semantic/object-id masks with the actual evaluation camera.",
            "",
            "## Fixed-camera Viewpoint Generation Feasibility Design",
            "",
            "Because the current action space does not include look_up/look_down/tilt, expanded ObjectNav viewpoints should be generated and validated using the policy/evaluation camera pitch directly.",
            "",
            "Required fields/checks:",
        ]
    )
    design = result["viewpoint_generation_design"]
    for item in design["required_static_inputs"]:
        lines.append(f"- Required input: {item}")
    for item in design["candidate_position_checks"]:
        lines.append(f"- Candidate position check: {item}")
    for item in design["fixed_camera_visibility_checks"]:
        lines.append(f"- Fixed-camera visibility check: {item}")
    lines.extend(["", "Suggested first threshold sweep:"])
    for key, value in design["recommended_first_thresholds_to_sweep"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "Outputs to store per accepted viewpoint:"])
    for item in design["outputs_per_viewpoint"]:
        lines.append(f"- {item}")
    lines.extend(["", "Quality gates:"])
    for item in design["quality_gates"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## Practical First Expansion Set",
            "",
            "A conservative first pass should start from high-confidence, high-coverage household objects and then manually spot-check rendered examples before any training. Native six categories and native-equivalent metadata categories remain useful controls; non-native candidates are candidates for expansion, not benchmark-ready labels.",
            "",
            "Native/native-equivalent controls:",
            "",
            md_table(
                listing_rows(result["practical_first_expansion_shortlist"]["native_or_native_equivalent_controls"]),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("native6", "native6"),
                    ("native_equiv", "native_equiv"),
                    ("median_height", "median_height"),
                    ("notes", "reasons"),
                ],
                limit=30,
            ),
            "",
            "Recommended non-native first expansion candidates:",
            "",
            md_table(
                listing_rows(result["practical_first_expansion_shortlist"]["recommended_non_native_first_expansion"]),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("median_height", "median_height"),
                    ("median_extent", "median_extent"),
                    ("notes", "reasons"),
                ],
                limit=40,
            ),
            "",
            "Fixed-camera or label-caution categories:",
            "",
            md_table(
                listing_rows(result["practical_first_expansion_shortlist"]["fixed_camera_or_label_caution"]),
                [
                    ("category", "category"),
                    ("instances", "instances"),
                    ("scenes", "scenes"),
                    ("median_y", "median_y"),
                    ("median_height", "median_height"),
                    ("notes", "reasons"),
                ],
                limit=40,
            ),
            "",
            "Categories marked reject should not be used until manually reviewed or relabeled.",
            "",
            "## Output Files",
            "",
            f"- JSON: `{result['output_json']}`",
            f"- Markdown: `{result['output_md']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    scene_root = Path(args.scene_root)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)

    discovery = discover_metadata(scene_root)
    object_metadata, metadata_load_summary = load_object_metadata(scene_root)
    category_summaries, inventory_summary = scan_scene_instances(
        scene_root=scene_root,
        scene_dir_name=args.scene_dir,
        object_metadata=object_metadata,
    )
    classification = add_classifications(
        category_summaries,
        rare_scene_threshold=args.rare_scene_threshold,
        rare_instance_threshold=args.rare_instance_threshold,
    )

    # Convert category summary values to JSON-serializable structures.
    serializable_categories = {
        category: rec for category, rec in sorted(category_summaries.items())
    }

    result = {
        "script": str(Path(__file__)),
        "native_hssd_objectnav_categories": sorted(NATIVE_HSSD_OBJECTNAV_CATEGORIES),
        "thresholds": {
            "rare_scene_threshold": args.rare_scene_threshold,
            "rare_instance_threshold": args.rare_instance_threshold,
            "small_height_median_m": 0.08,
            "small_max_extent_median_m": 0.15,
            "low_and_small_origin_y_m": 0.05,
            "low_and_small_height_m": 0.20,
            "low_and_small_max_extent_m": 0.40,
            "high_origin_y_p75_m": 1.8,
        },
        "metadata_discovery": discovery,
        "metadata_load_summary": metadata_load_summary,
        "object_metadata_entries": len(object_metadata),
        "inventory": inventory_summary,
        "classification": classification,
        "categories": serializable_categories,
        "practical_first_expansion_shortlist": build_practical_first_expansion_shortlist(
            category_summaries
        ),
        "viewpoint_generation_design": build_viewpoint_generation_design(),
        "output_json": str(output_json),
        "output_md": str(output_md),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    output_md.write_text(build_markdown(result), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    print(
        "Categories: "
        f"{inventory_summary['unique_categories']} total, "
        f"{classification['bucket_counts']['high-confidence']} high-confidence, "
        f"{classification['bucket_counts']['medium-confidence']} medium-confidence, "
        f"{classification['bucket_counts']['reject']} reject"
    )


if __name__ == "__main__":
    main()

