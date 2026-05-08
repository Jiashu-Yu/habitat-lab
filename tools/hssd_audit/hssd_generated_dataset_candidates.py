#!/usr/bin/env python3
"""Discover generated/modified HSSD ObjectNav dataset candidates.

Static-only: scans local JSON/JSON.GZ files for Habitat-style ObjectNav fields.
Does not import Habitat, render, train, or modify source/dataset files.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path(".")
DEFAULT_NATIVE_ROOT = Path("data/datasets/objectnav/hssd-hab")
DEFAULT_OUTPUT_JSON = Path("outputs/hssd_generated_dataset_candidates.json")
DEFAULT_OUTPUT_MD = Path("outputs/hssd_generated_dataset_candidates.md")
VALID_HSSD_CATEGORIES = {"bed", "chair", "couch", "potted_plant", "toilet", "tv"}
MAX_SAMPLES_PER_GROUP = 8

PRUNE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
}

PRUNE_REL_PREFIXES = {
    "outputs",
}

GENERATED_PATH_HINTS = [
    "generated",
    "modified",
    "train_3x",
    "val_3x",
    "regen",
    "regenerated",
    "viewpoint",
    "viewpoints",
    "tilt",
    "corrected",
    "filtered",
    "hssd_mp4",
    "objectnav_render",
]


def norm_rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def is_pruned(path: Path) -> bool:
    rel = norm_rel(path)
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in PRUNE_REL_PREFIXES)


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                obj = json.load(f)
        else:
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def shard_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".json.gz"):
        return name[: -len(".json.gz")]
    if name.endswith(".json"):
        return name[: -len(".json")]
    return path.stem


def candidate_root_for_file(path: Path) -> Path:
    parent = path.parent
    if parent.name == "content" and parent.parent.name:
        return parent.parent.parent
    return parent


def split_for_file(path: Path) -> str | None:
    if path.parent.name == "content":
        return path.parent.parent.name
    return None


def iter_json_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        path = Path(dirpath)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in PRUNE_DIR_NAMES and not is_pruned(path / d)
        ]
        if is_pruned(path):
            continue
        for name in filenames:
            if name.endswith(".json") or name.endswith(".json.gz"):
                yield path / name


def inspect_dataset_like_file(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if data is None:
        return None

    has_episodes = isinstance(data.get("episodes"), list)
    has_goals_by_category = isinstance(data.get("goals_by_category"), dict)
    has_category_map = "category_to_task_category_id" in data or "category_to_scene_annotation_category_id" in data

    if not has_episodes and not has_goals_by_category:
        return None

    episodes = data.get("episodes", []) if has_episodes else []
    goals_by_category = data.get("goals_by_category", {}) if has_goals_by_category else {}
    categories = Counter()
    malformed_like_categories = []
    for ep in episodes[:1000]:
        cat = ep.get("object_category")
        if cat is not None:
            categories[str(cat)] += 1
            if isinstance(cat, str) and any(ch.isdigit() for ch in cat) and "_" in cat:
                malformed_like_categories.append(cat)

    goal_categories = Counter()
    goal_count = 0
    vp_count = 0
    for key, goals in list(goals_by_category.items()):
        if not isinstance(goals, list):
            continue
        goal_count += len(goals)
        for goal in goals:
            cat = goal.get("object_category")
            if cat is not None:
                goal_categories[str(cat)] += 1
            view_points = goal.get("view_points", []) or []
            if isinstance(view_points, list):
                vp_count += len(view_points)

    all_cats = set(categories) | set(goal_categories)
    hssd_cat_overlap = sorted(all_cats & VALID_HSSD_CATEGORIES)
    hssd_like = (
        has_episodes
        and has_goals_by_category
        and (has_category_map or bool(hssd_cat_overlap))
        and (not all_cats or bool(hssd_cat_overlap))
    )
    objectnav_like = has_episodes and has_goals_by_category

    return {
        "file": str(path),
        "split": split_for_file(path),
        "has_episodes": has_episodes,
        "has_goals_by_category": has_goals_by_category,
        "has_category_map": has_category_map,
        "episodes_count": len(episodes),
        "goals_count": goal_count,
        "viewpoints_count": vp_count,
        "episode_categories_sampled": dict(sorted(categories.items())),
        "goal_categories": dict(sorted(goal_categories.items())),
        "hssd_category_overlap": hssd_cat_overlap,
        "objectnav_like": objectnav_like,
        "hssd_objectnav_like": hssd_like,
        "malformed_like_categories_sample": sorted(set(malformed_like_categories))[:10],
        "top_level_keys": sorted(data.keys()),
    }


def aggregate_candidates(root: Path, native_root: Path) -> dict[str, Any]:
    native_resolved = native_root.resolve()
    groups: dict[str, dict[str, Any]] = {}

    scanned_json_files = 0
    dataset_like_files = 0
    for path in iter_json_files(root):
        scanned_json_files += 1
        info = inspect_dataset_like_file(path)
        if info is None:
            continue
        dataset_like_files += 1
        candidate_root = candidate_root_for_file(path)
        key = str(candidate_root)
        if key not in groups:
            resolved = candidate_root.resolve()
            rel = norm_rel(candidate_root)
            lower = rel.lower()
            groups[key] = {
                "path": str(candidate_root),
                "resolved_path": str(resolved),
                "files": 0,
                "splits": Counter(),
                "contains_episodes": False,
                "contains_goals_by_category": False,
                "contains_category_map": False,
                "files_with_episodes": 0,
                "files_with_goals_by_category": 0,
                "episodes_count": 0,
                "goals_count": 0,
                "viewpoints_count": 0,
                "episode_categories": Counter(),
                "goal_categories": Counter(),
                "hssd_category_overlap": set(),
                "objectnav_like_files": 0,
                "hssd_objectnav_like_files": 0,
                "malformed_like_categories": set(),
                "sample_files": [],
                "path_hints": [hint for hint in GENERATED_PATH_HINTS if hint in lower],
                "is_native_hssd_path": resolved == native_resolved,
                "differs_from_native_hssd_path": resolved != native_resolved,
            }

        group = groups[key]
        group["files"] += 1
        if info.get("split"):
            group["splits"][info["split"]] += 1
        group["contains_episodes"] = group["contains_episodes"] or info["has_episodes"]
        group["contains_goals_by_category"] = group["contains_goals_by_category"] or info["has_goals_by_category"]
        group["contains_category_map"] = group["contains_category_map"] or info["has_category_map"]
        group["files_with_episodes"] += int(info["has_episodes"])
        group["files_with_goals_by_category"] += int(info["has_goals_by_category"])
        group["episodes_count"] += info["episodes_count"]
        group["goals_count"] += info["goals_count"]
        group["viewpoints_count"] += info["viewpoints_count"]
        group["episode_categories"].update(info["episode_categories_sampled"])
        group["goal_categories"].update(info["goal_categories"])
        group["hssd_category_overlap"].update(info["hssd_category_overlap"])
        group["objectnav_like_files"] += int(info["objectnav_like"])
        group["hssd_objectnav_like_files"] += int(info["hssd_objectnav_like"])
        group["malformed_like_categories"].update(info["malformed_like_categories_sample"])
        if len(group["sample_files"]) < MAX_SAMPLES_PER_GROUP:
            group["sample_files"].append(info)

    candidates = []
    for group in groups.values():
        looks_like_hssd_objectnav = (
            group["contains_episodes"]
            and group["contains_goals_by_category"]
            and group["hssd_objectnav_like_files"] > 0
        )
        generated_or_modified_hint = bool(group["path_hints"]) and group["differs_from_native_hssd_path"]
        group["looks_like_hssd_objectnav_dataset"] = looks_like_hssd_objectnav
        group["looks_generated_or_modified_by_path_hint"] = generated_or_modified_hint
        group["splits"] = dict(sorted(group["splits"].items()))
        group["episode_categories"] = dict(sorted(group["episode_categories"].items()))
        group["goal_categories"] = dict(sorted(group["goal_categories"].items()))
        group["hssd_category_overlap"] = sorted(group["hssd_category_overlap"])
        group["malformed_like_categories"] = sorted(group["malformed_like_categories"])
        candidates.append(group)

    candidates.sort(
        key=lambda g: (
            not g["looks_like_hssd_objectnav_dataset"],
            g["is_native_hssd_path"],
            g["path"],
        )
    )

    non_native_hssd = [
        c
        for c in candidates
        if c["looks_like_hssd_objectnav_dataset"]
        and c["differs_from_native_hssd_path"]
    ]
    non_native_generated_hint = [
        c for c in non_native_hssd if c["looks_generated_or_modified_by_path_hint"]
    ]
    clear_generated_dataset = None
    decision = ""
    if len(non_native_generated_hint) == 1:
        clear_generated_dataset = non_native_generated_hint[0]["path"]
        decision = "Exactly one non-native HSSD/ObjectNav-like candidate has a generated/modified path hint."
    elif len(non_native_hssd) == 1:
        clear_generated_dataset = non_native_hssd[0]["path"]
        decision = "Exactly one non-native HSSD/ObjectNav-like candidate was found, but it has no strong generated/modified path hint."
    elif len(non_native_hssd) == 0:
        decision = "No non-native HSSD/ObjectNav-like generated dataset candidate found."
    else:
        decision = "Multiple non-native HSSD/ObjectNav-like candidates found; do not auto-audit all."

    return {
        "scan_root": str(root),
        "native_hssd_root": str(native_root),
        "method": "Static scan of JSON/JSON.GZ files for episodes/goals_by_category; audit outputs pruned.",
        "scanned_json_files": scanned_json_files,
        "dataset_like_files": dataset_like_files,
        "candidates": candidates,
        "non_native_hssd_objectnav_candidate_count": len(non_native_hssd),
        "clear_generated_dataset": clear_generated_dataset,
        "decision": decision,
    }


def fmt(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return "`" + json.dumps(value, ensure_ascii=False) + "`"
    if value is None:
        return ""
    return str(value)


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(fmt(x) for x in row) + " |")
    return "\n".join(lines)


def write_markdown(summary: dict[str, Any], output_path: Path) -> None:
    rows = []
    for c in summary["candidates"]:
        rows.append(
            [
                c["path"],
                c["files"],
                c["contains_episodes"],
                c["contains_goals_by_category"],
                c["looks_like_hssd_objectnav_dataset"],
                c["differs_from_native_hssd_path"],
                c["splits"],
                c["episodes_count"],
                c["goals_count"],
                c["viewpoints_count"],
                c["hssd_category_overlap"],
                c["path_hints"],
                c["malformed_like_categories"],
            ]
        )

    lines = [
        "# Generated/Modified HSSD Dataset Candidate Discovery",
        "",
        f"Scan root: `{summary['scan_root']}`",
        f"Native HSSD root: `{summary['native_hssd_root']}`",
        "",
        "This is a static discovery pass. It only reads local JSON/JSON.GZ files and looks for Habitat ObjectNav-like `episodes` and `goals_by_category` structures. It does not run Habitat simulation, render, train, or modify dataset/source files.",
        "",
        f"Scanned JSON/JSON.GZ files: **{summary['scanned_json_files']}**",
        f"Dataset-like files found: **{summary['dataset_like_files']}**",
        "",
        "## Decision",
        "",
        f"- Clear generated dataset: `{summary['clear_generated_dataset']}`",
        f"- Decision: {summary['decision']}",
        "",
        "If multiple non-native candidates are present, this script intentionally stops at discovery so a human can choose the intended dataset.",
        "",
        "## Candidates",
        "",
        md_table(
            [
                "path",
                "files",
                "has episodes",
                "has goals_by_category",
                "looks HSSD/ObjectNav",
                "differs native",
                "splits",
                "episodes",
                "goals",
                "viewpoints",
                "HSSD categories",
                "path hints",
                "malformed-like categories",
            ],
            rows,
        ),
        "",
        "Machine-readable details: `outputs/hssd_generated_dataset_candidates.json`",
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--native-root", type=Path, default=DEFAULT_NATIVE_ROOT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    summary = aggregate_candidates(args.root, args.native_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown(summary, args.output_md)

    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(summary["decision"])
    if summary["clear_generated_dataset"]:
        print(f"clear_generated_dataset={summary['clear_generated_dataset']}")


if __name__ == "__main__":
    main()

