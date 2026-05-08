#!/usr/bin/env python3
"""Search the workspace for ObjectNav visibility/evaluation-related code."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_OUT = Path("outputs/code_search_report.md")

TERM_GROUPS: Dict[str, List[str]] = {
    "visibility": ["visibility", "visible", "oracle", "actual_visibility", "iou", "IoU"],
    "objectnav_metrics": [
        "success_distance",
        "DistanceToGoal",
        "OVONDistanceToGoal",
        "distance_to_goal",
        "VIEW_POINTS",
    ],
    "navila_vlm": ["NaVILA", "navila", "VLM", "vlm", "vision-language", "vision_language"],
    "sam_clip_reprojection": ["SAM", "sam", "CLIP", "clip", "SigLIP", "siglip", "reprojection", "project"],
    "episode_generation": ["goals_by_category", "view_points", "viewpoints", "ObjectGoal", "episode"],
}

TEXT_SUFFIXES = {
    ".py",
    ".yaml",
    ".yml",
    ".md",
    ".json",
    ".toml",
    ".sh",
    ".txt",
    ".cfg",
    ".ini",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "data",
    "outputs",
    "papers",
    "checkpoints",
    "tb",
    "tensorboard",
    "video_dir",
}


def should_skip(path: Path, root: Path, max_bytes: int) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in SKIP_DIRS for part in rel_parts):
        return True
    if path.suffix not in TEXT_SUFFIXES:
        return True
    try:
        return path.stat().st_size > max_bytes
    except OSError:
        return True


def iter_files(root: Path, max_bytes: int) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            if path.is_file() and not should_skip(path, root, max_bytes):
                yield path


def scan_file(path: Path, root: Path) -> List[Dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    rel = path.relative_to(root).as_posix()
    for line_no, line in enumerate(text.splitlines(), start=1):
        for group, terms in TERM_GROUPS.items():
            matched = [term for term in terms if term in line]
            if matched:
                hits.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "group": group,
                        "terms": matched,
                        "text": line.strip()[:240],
                    }
                )
    return hits


def summarize_hits(hits: List[Dict[str, object]]) -> Tuple[Counter, Counter, Counter]:
    by_group = Counter(hit["group"] for hit in hits)
    by_file = Counter(hit["path"] for hit in hits)
    by_term = Counter()
    for hit in hits:
        for term in hit["terms"]:
            by_term[str(term)] += 1
    return by_group, by_file, by_term


def write_report(root: Path, out_path: Path, hits: List[Dict[str, object]], scanned_count: int) -> None:
    by_group, by_file, by_term = summarize_hits(hits)
    grouped_paths: Dict[str, Counter] = defaultdict(Counter)
    for hit in hits:
        grouped_paths[str(hit["group"])][str(hit["path"])] += 1

    lines: List[str] = []
    lines.append("# Code Search Report")
    lines.append("")
    lines.append(f"- Generated UTC: `{datetime.now(timezone.utc).isoformat()}`")
    lines.append(f"- Root: `{root}`")
    lines.append(f"- Files scanned: `{scanned_count}`")
    lines.append(f"- Total line hits: `{len(hits)}`")
    lines.append("")
    lines.append("## Search Groups")
    lines.append("")
    for group, terms in TERM_GROUPS.items():
        lines.append(f"- `{group}`: {', '.join(f'`{term}`' for term in terms)}")
    lines.append("")
    lines.append("## Hit Counts by Group")
    lines.append("")
    for group, count in by_group.most_common():
        lines.append(f"- `{group}`: {count}")
    if not by_group:
        lines.append("- No hits.")
    lines.append("")
    lines.append("## Top Files")
    lines.append("")
    for path, count in by_file.most_common(50):
        lines.append(f"- `{path}`: {count}")
    if not by_file:
        lines.append("- No hit files.")
    lines.append("")
    lines.append("## Top Terms")
    lines.append("")
    for term, count in by_term.most_common(50):
        lines.append(f"- `{term}`: {count}")
    if not by_term:
        lines.append("- No hit terms.")
    lines.append("")
    lines.append("## Candidate Files by Group")
    lines.append("")
    for group in TERM_GROUPS:
        lines.append(f"### {group}")
        lines.append("")
        for path, count in grouped_paths[group].most_common(25):
            lines.append(f"- `{path}`: {count}")
        if not grouped_paths[group]:
            lines.append("- No candidates found.")
        lines.append("")
    lines.append("## Line Hits")
    lines.append("")
    lines.append("| File | Line | Group | Terms | Text |")
    lines.append("|---|---:|---|---|---|")
    for hit in hits[:500]:
        text = str(hit["text"]).replace("|", "\\|")
        terms = ", ".join(f"`{term}`" for term in hit["terms"])
        lines.append(f"| `{hit['path']}` | {hit['line']} | `{hit['group']}` | {terms} | {text} |")
    if len(hits) > 500:
        lines.append("")
        lines.append(f"Report truncated to first 500 line hits out of {len(hits)}.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    json_path = out_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "root": str(root),
                "files_scanned": scanned_count,
                "total_hits": len(hits),
                "by_group": dict(by_group),
                "by_file": dict(by_file),
                "by_term": dict(by_term),
                "hits": hits[:1000],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Find visibility/evaluation-related code.")
    parser.add_argument("--root", default=".", help="Workspace root to scan.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Markdown report path.")
    parser.add_argument("--max-bytes", type=int, default=2_000_000, help="Skip text files larger than this.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    hits: List[Dict[str, object]] = []
    scanned_count = 0
    for path in iter_files(root, args.max_bytes):
        scanned_count += 1
        hits.extend(scan_file(path, root))

    out_path = Path(args.out)
    write_report(root, out_path, hits, scanned_count)
    print(json.dumps({"files_scanned": scanned_count, "total_hits": len(hits), "out": str(out_path)}, indent=2))


if __name__ == "__main__":
    main()

