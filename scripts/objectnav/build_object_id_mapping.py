#!/usr/bin/env python3
import argparse
import csv
import gzip
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

HASH40_RE = re.compile(r"^[0-9a-f]{40}$")
NUMERIC_COMPOUND_RE = re.compile(r"^[0-9]+(?:-[0-9]+)+$")


def classify_base_id(base_id: str) -> str:
    if HASH40_RE.fullmatch(base_id):
        return "hash40"
    if base_id.startswith("xxxx"):
        return "xxxx_guid"
    if NUMERIC_COMPOUND_RE.fullmatch(base_id):
        return "numeric_compound"
    if base_id and base_id[0].isalpha():
        return "named"
    return "other"


def canonicalize(raw_template_name: str) -> Tuple[str, bool, str]:
    raw = raw_template_name.strip()
    if "_part_" in raw:
        parent = raw.split("_part_", 1)[0].strip().lower()
        return parent, True, parent
    canonical = raw.lower()
    return canonical, False, ""


def iter_condensed_rows(condensed_csv: Path) -> Iterable[Tuple[str, str]]:
    with condensed_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            object_id = row[0].strip().lower()
            if (
                not object_id
                or object_id.startswith("object hash")
                or object_id.startswith("all empty")
                or object_id.startswith("e.g.")
            ):
                continue
            if len(row) < 4:
                continue
            condensed_category = row[3].strip().lower()
            yield object_id, condensed_category


def read_filtered_rows(filtered_csv: Path) -> Iterable[Tuple[str, str]]:
    with filtered_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            object_id = (row.get("id") or "").strip().lower()
            clean_category = (row.get("clean_category") or "").strip().lower()
            if not object_id:
                continue
            yield object_id, clean_category


def collect_object_config_ids(objects_root: Path) -> set:
    ids = set()
    for cfg in objects_root.rglob("*.object_config.json"):
        object_id = cfg.name.replace(".object_config.json", "").strip().lower()
        if object_id:
            ids.add(object_id)
    return ids


def collect_scene_template_counts(scenes_root: Path) -> Counter:
    counts = Counter()
    scene_files = sorted(scenes_root.glob("*.scene_instance.json"))
    for scene_fp in scene_files:
        with scene_fp.open(encoding="utf-8") as f:
            data = json.load(f)
        for inst in data.get("object_instances", []):
            template_name = (inst.get("template_name") or "").strip()
            if template_name:
                counts[template_name] += 1
    return counts


def build_rows(
    template_counts: Counter,
    condensed_map: Dict[str, str],
    filtered_map: Dict[str, str],
    object_config_ids: set,
    goal_object_ids: set,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for raw_template_name, occ in template_counts.most_common():
        canonical_id, is_part, parent_id = canonicalize(raw_template_name)
        id_family = classify_base_id(canonical_id)

        in_condensed = canonical_id in condensed_map
        in_filtered = canonical_id in filtered_map
        has_object_config = canonical_id in object_config_ids
        appears_in_goals = canonical_id in goal_object_ids

        condensed_category = condensed_map.get(canonical_id, "")
        filtered_category = filtered_map.get(canonical_id, "")

        rows.append(
            {
                "raw_template_name": raw_template_name,
                "occurrences": occ,
                "id_family": id_family,
                "is_part": int(is_part),
                "parent_object_id": parent_id,
                "canonical_object_id": canonical_id,
                "in_condensed": int(in_condensed),
                "in_filtered": int(in_filtered),
                "has_object_config": int(has_object_config),
                "appears_in_goals": int(appears_in_goals),
                "condensed_category": condensed_category,
                "filtered_category": filtered_category,
            }
        )
    return rows


def collect_goal_object_ids(dataset_root: Path) -> set:
    ids = set()
    for split in ["train", "val"]:
        content_dir = dataset_root / split / "content"
        if not content_dir.exists():
            continue
        for fp in sorted(content_dir.glob("*.json.gz")):
            with gzip.open(fp, "rt", encoding="utf-8") as f:
                data = json.load(f)
            for goals in data.get("goals_by_category", {}).values():
                for goal in goals:
                    object_name = str(goal.get("object_name", "")).strip().lower()
                    if not object_name:
                        continue
                    # object_name format example: <template_or_handle>_:0000
                    name_prefix = object_name.split("_:", 1)[0].strip()
                    if name_prefix:
                        canonical_id, _, _ = canonicalize(name_prefix)
                        ids.add(canonical_id)
    return ids


def write_csv(rows: List[Dict[str, object]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "raw_template_name",
        "occurrences",
        "id_family",
        "is_part",
        "parent_object_id",
        "canonical_object_id",
        "in_condensed",
        "in_filtered",
        "has_object_config",
        "appears_in_goals",
        "condensed_category",
        "filtered_category",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: List[Dict[str, object]]) -> Dict[str, object]:
    family_counts = Counter(row["id_family"] for row in rows)

    unresolved = [
        row
        for row in rows
        if not row["in_condensed"] and not row["in_filtered"] and not row["has_object_config"]
    ]

    unresolved_in_goals = [row for row in unresolved if row["appears_in_goals"]]
    unresolved_not_in_goals = [row for row in unresolved if not row["appears_in_goals"]]

    summary = {
        "unique_template_names": len(rows),
        "total_object_instances": int(sum(int(row["occurrences"]) for row in rows)),
        "id_family_counts": dict(family_counts),
        "in_condensed_unique": int(sum(int(row["in_condensed"]) for row in rows)),
        "in_filtered_unique": int(sum(int(row["in_filtered"]) for row in rows)),
        "has_object_config_unique": int(sum(int(row["has_object_config"]) for row in rows)),
        "appears_in_goals_unique": int(sum(int(row["appears_in_goals"]) for row in rows)),
        "unresolved_unique": len(unresolved),
        "unresolved_in_goals_unique": len(unresolved_in_goals),
        "unresolved_not_in_goals_unique": len(unresolved_not_in_goals),
        "top_unresolved": [
            {
                "raw_template_name": row["raw_template_name"],
                "occurrences": int(row["occurrences"]),
                "canonical_object_id": row["canonical_object_id"],
                "appears_in_goals": int(row["appears_in_goals"]),
            }
            for row in unresolved[:20]
        ],
        "unresolved_non_goal_allowlist": [
            str(row["canonical_object_id"]) for row in unresolved_not_in_goals
        ],
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical object-id mapping audit for HSSD scenes.")
    parser.add_argument(
        "--scenes-root",
        default="data/scene_datasets/hssd-hab/scenes",
        help="Directory containing scene_instance json files.",
    )
    parser.add_argument(
        "--objects-root",
        default="data/scene_datasets/hssd-hab/objects",
        help="Directory containing object assets and object_config files.",
    )
    parser.add_argument(
        "--condensed-csv",
        default="data/scene_datasets/hssd-hab/metadata/hssd_obj_semantics_condensed.csv",
        help="Path to condensed semantics csv.",
    )
    parser.add_argument(
        "--filtered-csv",
        default="data/scene_datasets/hssd-hab/metadata/object_categories_filtered.csv",
        help="Path to filtered object categories csv.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/scene_datasets/hssd-hab/metadata/id_mapping_phase2",
        help="Output directory for mapping csv and summary json.",
    )
    parser.add_argument(
        "--objectnav-root",
        default="data/datasets/objectnav/hssd-hab",
        help="Path to ObjectNav dataset root containing train/val content shards.",
    )
    args = parser.parse_args()

    scenes_root = Path(args.scenes_root)
    objects_root = Path(args.objects_root)
    condensed_csv = Path(args.condensed_csv)
    filtered_csv = Path(args.filtered_csv)
    out_dir = Path(args.out_dir)
    objectnav_root = Path(args.objectnav_root)

    condensed_map = dict(iter_condensed_rows(condensed_csv))
    filtered_map = dict(read_filtered_rows(filtered_csv))
    object_config_ids = collect_object_config_ids(objects_root)
    goal_object_ids = collect_goal_object_ids(objectnav_root)
    template_counts = collect_scene_template_counts(scenes_root)

    rows = build_rows(
        template_counts,
        condensed_map,
        filtered_map,
        object_config_ids,
        goal_object_ids,
    )

    out_csv = out_dir / "object_id_mapping.csv"
    out_summary = out_dir / "object_id_mapping_summary.json"
    out_allowlist = out_dir / "unresolved_non_goal_allowlist.json"

    write_csv(rows, out_csv)
    summary = summarize(rows)
    out_summary.parent.mkdir(parents=True, exist_ok=True)
    with out_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=True)

    allowlist_payload = {
        "description": "Unresolved template IDs that do not appear in ObjectNav goals and can be ignored in goal-target mapping.",
        "allowlist": summary.get("unresolved_non_goal_allowlist", []),
    }
    with out_allowlist.open("w", encoding="utf-8") as f:
        json.dump(allowlist_payload, f, indent=2, ensure_ascii=True)

    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"Wrote mapping table: {out_csv}")
    print(f"Wrote summary: {out_summary}")
    print(f"Wrote unresolved non-goal allowlist: {out_allowlist}")


if __name__ == "__main__":
    main()
