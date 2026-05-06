#!/usr/bin/env python3
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

DEFAULT_BLOCKLIST = {
    "unknown",
    "wall",
    "ceiling",
    "floor",
    "stairs",
    "stair",
    "railing",
    "beam",
    "pillar",
    "column",
    "roof",
    "fence",
    "curb",
    "switch",
    "socket",
    "outlet",
    "light_switch",
    "door_handle",
    "window_frame",
    "wall_plug",
}


def load_stats(mapping_csv: Path) -> Dict[str, Dict[str, object]]:
    stats: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "occurrences": 0,
            "template_ids": set(),
            "goal_templates": 0,
            "id_families": set(),
            "categories_source_rows": 0,
        }
    )

    with mapping_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = (row.get("condensed_category") or "").strip().lower()
            if not cat:
                continue
            occ = int(row.get("occurrences") or 0)
            template_id = (row.get("canonical_object_id") or "").strip().lower()
            goal_flag = int(row.get("appears_in_goals") or 0)
            id_family = (row.get("id_family") or "").strip().lower()

            s = stats[cat]
            s["occurrences"] += occ
            if template_id:
                s["template_ids"].add(template_id)
            s["goal_templates"] += goal_flag
            if id_family:
                s["id_families"].add(id_family)
            s["categories_source_rows"] += 1

    return stats


def build_rows(stats: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    rows = []
    for cat, s in stats.items():
        rows.append(
            {
                "category": cat,
                "occurrences": int(s["occurrences"]),
                "template_count": len(s["template_ids"]),
                "goal_template_count": int(s["goal_templates"]),
                "id_families": ";".join(sorted(s["id_families"])),
                "source_rows": int(s["categories_source_rows"]),
            }
        )
    rows.sort(key=lambda x: (x["occurrences"], x["template_count"]), reverse=True)
    return rows


def select_whitelist(
    rows: List[Dict[str, object]],
    target_size: int,
    min_occurrences: int,
    min_templates: int,
    blocklist: Set[str],
) -> Dict[str, object]:
    selected: List[Dict[str, object]] = []
    excluded: List[Dict[str, object]] = []
    strict_pool: List[Dict[str, object]] = []

    for row in rows:
        cat = str(row["category"])
        occ = int(row["occurrences"])
        templates = int(row["template_count"])

        if cat in blocklist:
            excluded.append({**row, "reason": "blocked_by_semantic_blocklist"})
            continue
        if occ < min_occurrences:
            excluded.append({**row, "reason": "below_min_occurrences"})
            continue
        if templates < min_templates:
            excluded.append({**row, "reason": "below_min_templates"})
            continue

        strict_pool.append({**row, "selection_reason": "strict_threshold"})

    selected = strict_pool

    if len(selected) > target_size:
        overflow = selected[target_size:]
        selected = selected[:target_size]
        excluded.extend([{**r, "reason": "trimmed_by_target_size"} for r in overflow])

    if len(selected) < target_size:
        selected_names = {str(r["category"]) for r in selected}
        relaxed_min_occ = max(20, min_occurrences // 2)
        relaxed_min_templates = max(3, min_templates // 2)
        backfill_candidates = [
            {**r, "selection_reason": "relaxed_backfill"}
            for r in rows
            if str(r["category"]) not in selected_names
            and str(r["category"]) not in blocklist
            and int(r["occurrences"]) >= relaxed_min_occ
            and int(r["template_count"]) >= relaxed_min_templates
        ]
        for r in backfill_candidates:
            if len(selected) >= target_size:
                break
            if r in selected:
                continue
            selected.append(r)

    mapping = {
        row["category"]: idx for idx, row in enumerate(selected)
    }

    return {
        "selected": selected,
        "excluded": excluded,
        "category_to_task_category_id": mapping,
    }


def write_rows_csv(rows: List[Dict[str, object]], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "category",
        "occurrences",
        "template_count",
        "goal_template_count",
        "id_families",
        "source_rows",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build phase-3 condensed category whitelist proposal.")
    parser.add_argument(
        "--mapping-csv",
        default="data/scene_datasets/hssd-hab/metadata/id_mapping_phase2/object_id_mapping.csv",
        help="Phase-2 object id mapping csv.",
    )
    parser.add_argument(
        "--target-size",
        type=int,
        default=100,
        help="Target whitelist category count.",
    )
    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=50,
        help="Minimum object-instance occurrences per category.",
    )
    parser.add_argument(
        "--min-templates",
        type=int,
        default=5,
        help="Minimum distinct template count per category.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/scene_datasets/hssd-hab/metadata/category_whitelist_phase3",
        help="Output directory for whitelist artifacts.",
    )
    args = parser.parse_args()

    mapping_csv = Path(args.mapping_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = load_stats(mapping_csv)
    rows = build_rows(stats)

    write_rows_csv(rows, out_dir / "condensed_category_stats.csv")

    result = select_whitelist(
        rows,
        target_size=args.target_size,
        min_occurrences=args.min_occurrences,
        min_templates=args.min_templates,
        blocklist=DEFAULT_BLOCKLIST,
    )

    selected = result["selected"]
    excluded = result["excluded"]

    payload = {
        "target_size": args.target_size,
        "min_occurrences": args.min_occurrences,
        "min_templates": args.min_templates,
        "selected_count": len(selected),
        "strict_selected_count": sum(
            1 for row in selected if row.get("selection_reason") == "strict_threshold"
        ),
        "relaxed_selected_count": sum(
            1 for row in selected if row.get("selection_reason") == "relaxed_backfill"
        ),
        "selected_categories": [row["category"] for row in selected],
        "category_to_task_category_id": result["category_to_task_category_id"],
        "notes": [
            "This is a phase-3 proposal generated from condensed semantic categories.",
            "Selection prioritizes scene frequency and template diversity.",
            "Blocked categories are structural/ambiguous classes and should not be nav targets.",
        ],
    }

    with (out_dir / "category_whitelist_v1.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)

    with (out_dir / "category_excluded_v1.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "category",
            "occurrences",
            "template_count",
            "goal_template_count",
            "id_families",
            "source_rows",
            "reason",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(excluded)

    with (out_dir / "category_selected_v1.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "category",
            "occurrences",
            "template_count",
            "goal_template_count",
            "id_families",
            "source_rows",
            "selection_reason",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)

    print(json.dumps(
        {
            "selected_count": len(selected),
            "top10_selected": [row["category"] for row in selected[:10]],
            "output_dir": str(out_dir),
        },
        indent=2,
        ensure_ascii=True,
    ))


if __name__ == "__main__":
    main()
