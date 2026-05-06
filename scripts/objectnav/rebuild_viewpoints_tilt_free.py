#!/usr/bin/env python3
import argparse
import gzip
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

try:
    import habitat_sim
    from habitat_sim.utils.common import quat_from_two_vectors, quat_to_coeffs
except ImportError:  # pragma: no cover
    habitat_sim = None
    quat_from_two_vectors = None
    quat_to_coeffs = None


def euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def planar_xz(a: List[float], b: List[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2)


def load_whitelist_categories(whitelist_json: Optional[Path]) -> Optional[Set[str]]:
    if whitelist_json is None:
        return None

    with whitelist_json.open(encoding="utf-8") as f:
        data = json.load(f)

    categories: List[str] = []
    if isinstance(data, dict):
        if isinstance(data.get("selected_categories"), list):
            categories = data["selected_categories"]
        elif isinstance(data.get("categories"), list):
            categories = data["categories"]
    elif isinstance(data, list):
        categories = data

    return {str(c).strip().lower() for c in categories if str(c).strip()}


def resolve_scene_path(scene_id: str, scenes_root: Path) -> Optional[Path]:
    if not scene_id:
        return None

    scene_path = Path(scene_id)
    if scene_path.exists():
        return scene_path

    fallback = scenes_root / scene_path.name
    if fallback.exists():
        return fallback

    # Some datasets store scene_id as bare numeric token, e.g. "102343992".
    if scene_path.suffix == "":
        fallback_with_suffix = scenes_root / f"{scene_path.name}.scene_instance.json"
        if fallback_with_suffix.exists():
            return fallback_with_suffix

    return None


def build_simulator(
    scene_dataset_config: Path,
    scene_file: Path,
    gpu_device_id: int,
    navmesh_agent_height: float,
    navmesh_agent_radius: float,
):
    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_dataset_config_file = str(scene_dataset_config)
    sim_cfg.scene_id = str(scene_file)
    sim_cfg.enable_physics = False
    sim_cfg.gpu_device_id = gpu_device_id

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = []

    sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_cfg]))

    nav_settings = habitat_sim.NavMeshSettings()
    nav_settings.set_defaults()
    nav_settings.agent_height = navmesh_agent_height
    nav_settings.agent_radius = navmesh_agent_radius
    nav_settings.include_static_objects = True
    sim.recompute_navmesh(sim.pathfinder, nav_settings)

    return sim


def lookup_semantic_object(sem_scene, goal_object_id: object):
    object_id_str = str(goal_object_id)
    try:
        idx = int(object_id_str)
    except ValueError:
        idx = -1

    if 0 <= idx < len(sem_scene.objects):
        obj = sem_scene.objects[idx]
        if obj is not None:
            return obj

    for obj in sem_scene.objects:
        if obj is None:
            continue
        obj_id = str(obj.id)
        if obj_id == object_id_str or obj_id.split("_")[-1] == object_id_str:
            return obj

    return None


def down_and_snap(
    pathfinder,
    point: np.ndarray,
    max_drop: float,
    drop_step: float,
) -> Optional[np.ndarray]:
    if not pathfinder.is_loaded:
        return None

    probe = point.astype(np.float32).copy()
    steps = int(max_drop / drop_step)
    for _ in range(steps + 1):
        if pathfinder.is_navigable(probe):
            snapped = np.array(pathfinder.snap_point(probe), dtype=np.float32)
            if np.isnan(snapped).any():
                return None
            if not pathfinder.is_navigable(snapped):
                return None
            return snapped
        probe[1] -= drop_step
    return None


def collect_reference_viewpoints(goal: Dict[str, object]) -> List[Dict[str, object]]:
    """Collect legacy viewpoints and normalize their 3-tilt IoU into single-frame score."""
    refs: List[Dict[str, object]] = []
    goal_pos = goal.get("position") or []

    for vp in goal.get("view_points") or []:
        pos = (vp.get("agent_state") or {}).get("position")
        iou = vp.get("iou")
        if not pos or iou is None:
            continue

        try:
            legacy_iou = float(iou)
        except (TypeError, ValueError):
            continue

        # Legacy HSSD viewpoints can have IoU up to 3.0 from 3 tilt actions.
        single_frame_score = max(0.0, min(legacy_iou / 3.0, 1.0))
        dist = planar_xz(pos, goal_pos) if goal_pos else 0.0
        refs.append(
            {
                "position": np.array(pos, dtype=np.float32),
                "single_score": single_frame_score,
                "distance": float(dist),
            }
        )

    return refs


def proxy_viewpoint_score(
    candidate_pos: np.ndarray,
    goal_pos: np.ndarray,
    references: List[Dict[str, object]],
    preferred_max_distance: float,
    fallback_max_distance: float,
    neighbor_decay: float,
) -> float:
    """Estimate a tilt-free viewpoint quality score in [0, 1]."""
    goal_dist = planar_xz(candidate_pos.tolist(), goal_pos.tolist())

    if goal_dist <= preferred_max_distance:
        near_term = 1.0
    elif goal_dist >= fallback_max_distance:
        near_term = 0.0
    else:
        near_term = 1.0 - (
            (goal_dist - preferred_max_distance)
            / max(1e-6, fallback_max_distance - preferred_max_distance)
        )

    dist_term = max(0.0, 1.0 - goal_dist / max(1e-6, fallback_max_distance))

    if references:
        nearest_ref = min(
            references,
            key=lambda r: float(np.linalg.norm(candidate_pos - r["position"])),
        )
        ref_dist = float(np.linalg.norm(candidate_pos - nearest_ref["position"]))
        ref_term = float(nearest_ref["single_score"]) * math.exp(
            -ref_dist / max(1e-6, neighbor_decay)
        )
        score = 0.7 * ref_term + 0.3 * near_term * dist_term
    else:
        score = near_term * dist_term

    return float(max(0.0, min(score, 1.0)))


def generate_candidates(
    sim,
    goal_pos: np.ndarray,
    target_center: np.ndarray,
    target_half_sizes: np.ndarray,
    obb,
    references: List[Dict[str, object]],
    preferred_max_distance: float,
    max_radius: float,
    neighbor_decay: float,
    cell_size: float,
    min_distance: float,
    max_drop: float,
    drop_step: float,
) -> List[Dict[str, object]]:
    center = target_center.astype(np.float32)
    sizes = target_half_sizes.astype(np.float32) * 2.0
    pathfinder = sim.pathfinder

    x_half = float(sizes[0] / 2.0 + max_radius)
    z_half = float(sizes[2] / 2.0 + max_radius)

    eps = 1e-5
    xs = np.arange(center[0] - x_half, center[0] + x_half + eps, cell_size)
    zs = np.arange(center[2] - z_half, center[2] + z_half + eps, cell_size)

    out: List[Dict[str, object]] = []
    for x in xs:
        for z in zs:
            cand = np.array([x, center[1], z], dtype=np.float32)
            if obb is not None and float(obb.distance(cand)) > max_radius:
                continue

            snapped = down_and_snap(pathfinder, cand, max_drop=max_drop, drop_step=drop_step)
            if snapped is None:
                continue

            dist = planar_xz(snapped.tolist(), goal_pos.tolist())
            if dist < min_distance or dist > max_radius:
                continue

            view_dir = goal_pos - snapped
            view_dir[1] = 0.0
            norm = float(np.linalg.norm(view_dir))
            if norm < 1e-6:
                continue

            view_dir /= norm
            rotation = quat_from_two_vectors(habitat_sim.geo.FRONT, view_dir)
            score = proxy_viewpoint_score(
                candidate_pos=snapped,
                goal_pos=goal_pos,
                references=references,
                preferred_max_distance=preferred_max_distance,
                fallback_max_distance=max_radius,
                neighbor_decay=neighbor_decay,
            )

            out.append(
                {
                    "position": snapped.tolist(),
                    "rotation": quat_to_coeffs(rotation).tolist(),
                    "distance": dist,
                    "score": score,
                }
            )

    return out


def regenerate_goal_viewpoints(
    sim,
    sem_scene,
    goal: Dict[str, object],
    preferred_max_distance: float,
    fallback_max_distance: float,
    distance_step: float,
    goal_vp_cell_size: float,
    score_thresh: float,
    proxy_neighbor_decay: float,
    min_distance: float,
    min_keep: int,
    max_keep: int,
    keep_topk_if_empty: bool,
    max_drop: float,
    drop_step: float,
) -> Tuple[List[Dict[str, object]], Dict[str, float]]:
    goal_pos_list = goal.get("position")
    if not goal_pos_list:
        return [], {"status": "missing_goal_position"}

    goal_pos = np.array(goal_pos_list, dtype=np.float32)
    sem_obj = lookup_semantic_object(sem_scene, goal.get("object_id", ""))

    target_center = goal_pos.copy()
    target_half_sizes = np.zeros(3, dtype=np.float32)
    target_obb = None

    target_source = "goal_object_id"
    if sem_obj is not None:
        target_center = np.array(sem_obj.aabb.center, dtype=np.float32)
        target_half_sizes = np.array(sem_obj.aabb.sizes, dtype=np.float32) / 2.0
        target_obb = habitat_sim.geo.OBB(sem_obj.aabb)
        target_source = "semantic_scene"

    references = collect_reference_viewpoints(goal)

    candidates = generate_candidates(
        sim=sim,
        goal_pos=goal_pos,
        target_center=target_center,
        target_half_sizes=target_half_sizes,
        obb=target_obb,
        references=references,
        preferred_max_distance=preferred_max_distance,
        max_radius=fallback_max_distance,
        neighbor_decay=proxy_neighbor_decay,
        cell_size=goal_vp_cell_size,
        min_distance=min_distance,
        max_drop=max_drop,
        drop_step=drop_step,
    )

    if not candidates:
        return [], {"status": "no_navigable_candidates"}

    radius = preferred_max_distance
    selected: List[Dict[str, object]] = []
    used_radius = fallback_max_distance
    while radius <= fallback_max_distance + 1e-6:
        filtered = [
            c
            for c in candidates
            if float(c["distance"]) <= radius and float(c["score"]) >= score_thresh
        ]
        if len(filtered) >= min_keep:
            selected = filtered
            used_radius = radius
            break
        radius += distance_step

    if not selected:
        selected = [c for c in candidates if float(c["score"]) >= score_thresh]
        if selected:
            used_radius = fallback_max_distance

    if not selected and keep_topk_if_empty:
        selected = sorted(candidates, key=lambda c: (float(c["score"]), -float(c["distance"])), reverse=True)[:min_keep]
        used_radius = fallback_max_distance

    selected = sorted(selected, key=lambda c: (float(c["score"]), -float(c["distance"])), reverse=True)
    selected = selected[:max_keep]

    view_points = [
        {
            "agent_state": {
                "position": c["position"],
                "rotation": c["rotation"],
            },
            "iou": float(c["score"]),
        }
        for c in selected
    ]

    if not view_points:
        return [], {"status": "no_selected_viewpoints"}

    distances = [float(c["distance"]) for c in selected]
    scores = [float(c["score"]) for c in selected]
    return view_points, {
        "status": "ok",
        "target_source": target_source,
        "reference_count": float(len(references)),
        "used_radius": float(used_radius),
        "median_distance": float(median(distances)),
        "median_score": float(median(scores)),
        "selected_count": float(len(selected)),
    }


def process_split(
    in_root: Path,
    out_root: Path,
    scenes_root: Path,
    scene_dataset_config: Path,
    split: str,
    preferred_max_distance: float,
    fallback_max_distance: float,
    distance_step: float,
    goal_vp_cell_size: float,
    score_thresh: float,
    proxy_neighbor_decay: float,
    keep_topk_if_empty: bool,
    keep_original_if_empty: bool,
    process_whitelist_only: bool,
    whitelist: Optional[Set[str]],
    gpu_device_id: int,
    navmesh_agent_height: float,
    navmesh_agent_radius: float,
    min_distance: float,
    max_keep: int,
    min_keep: int,
    max_drop: float,
    drop_step: float,
    max_shards: int,
    max_goals_per_shard: int,
) -> Dict[str, float]:
    in_split = in_root / split
    out_split = out_root / split
    out_split.mkdir(parents=True, exist_ok=True)
    (out_split / "content").mkdir(parents=True, exist_ok=True)

    top_in = in_split / f"{split}.json.gz"
    top_out = out_split / f"{split}.json.gz"
    with gzip.open(top_in, "rt", encoding="utf-8") as f:
        top_data = json.load(f)
    with gzip.open(top_out, "wt", encoding="utf-8") as f:
        json.dump(top_data, f, ensure_ascii=True)

    shard_count = 0
    goal_count = 0
    regenerated_goals = 0
    goals_semantic_center = 0
    goals_goal_center_fallback = 0
    skipped_by_whitelist = 0
    kept_original_goals = 0
    fallback_goal_count = 0

    before_vp = 0
    after_vp = 0
    med_before_acc: List[float] = []
    med_after_acc: List[float] = []
    score_after_acc: List[float] = []
    used_radius_acc: List[float] = []

    shard_fps = sorted((in_split / "content").glob("*.json.gz"))
    if max_shards > 0:
        shard_fps = shard_fps[:max_shards]

    for fp in shard_fps:
        shard_count += 1
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            shard = json.load(f)

        episodes = shard.get("episodes") or []
        scene_id = ""
        if episodes:
            scene_id = str((episodes[0] or {}).get("scene_id") or "")

        scene_fp = resolve_scene_path(scene_id, scenes_root)
        if scene_fp is None:
            out_fp = out_split / "content" / fp.name
            with gzip.open(out_fp, "wt", encoding="utf-8") as f:
                json.dump(shard, f, ensure_ascii=True)
            continue

        sim = build_simulator(
            scene_dataset_config=scene_dataset_config,
            scene_file=scene_fp,
            gpu_device_id=gpu_device_id,
            navmesh_agent_height=navmesh_agent_height,
            navmesh_agent_radius=navmesh_agent_radius,
        )
        sem_scene = sim.semantic_scene

        gbc = shard.get("goals_by_category", {})
        processed_in_shard = 0
        for _, goals in gbc.items():
            for goal in goals:
                if max_goals_per_shard > 0 and processed_in_shard >= max_goals_per_shard:
                    break
                processed_in_shard += 1

                category = str(goal.get("object_category") or "").strip().lower()
                old_vp = goal.get("view_points") or []
                old_dist = []
                goal_pos = goal.get("position") or []
                for vp in old_vp:
                    pos = (vp.get("agent_state") or {}).get("position")
                    if pos and goal_pos:
                        old_dist.append(planar_xz(pos, goal_pos))

                goal_count += 1
                before_vp += len(old_vp)
                if old_dist:
                    med_before_acc.append(float(median(old_dist)))

                if process_whitelist_only and whitelist is not None and category not in whitelist:
                    skipped_by_whitelist += 1
                    after_vp += len(old_vp)
                    continue

                new_vp, stats = regenerate_goal_viewpoints(
                    sim=sim,
                    sem_scene=sem_scene,
                    goal=goal,
                    preferred_max_distance=preferred_max_distance,
                    fallback_max_distance=fallback_max_distance,
                    distance_step=distance_step,
                    goal_vp_cell_size=goal_vp_cell_size,
                    score_thresh=score_thresh,
                    proxy_neighbor_decay=proxy_neighbor_decay,
                    min_distance=min_distance,
                    min_keep=min_keep,
                    max_keep=max_keep,
                    keep_topk_if_empty=keep_topk_if_empty,
                    max_drop=max_drop,
                    drop_step=drop_step,
                )

                if not new_vp and keep_original_if_empty:
                    kept_original_goals += 1
                    after_vp += len(old_vp)
                    if old_dist:
                        med_after_acc.append(float(median(old_dist)))
                else:
                    goal["view_points"] = new_vp
                    regenerated_goals += 1
                    after_vp += len(new_vp)
                    new_dist = [
                        planar_xz((vp.get("agent_state") or {}).get("position"), goal_pos)
                        for vp in new_vp
                        if (vp.get("agent_state") or {}).get("position") and goal_pos
                    ]
                    if new_dist:
                        med_after_acc.append(float(median(new_dist)))

                if str(stats.get("target_source", "")) == "semantic_scene":
                    goals_semantic_center += 1
                else:
                    goals_goal_center_fallback += 1

                if float(stats.get("used_radius", preferred_max_distance)) > preferred_max_distance + 1e-6:
                    fallback_goal_count += 1

                if "median_score" in stats:
                    score_after_acc.append(float(stats["median_score"]))
                if "used_radius" in stats:
                    used_radius_acc.append(float(stats["used_radius"]))

        sim.close()

        out_fp = out_split / "content" / fp.name
        with gzip.open(out_fp, "wt", encoding="utf-8") as f:
            json.dump(shard, f, ensure_ascii=True)

    return {
        "split": split,
        "shard_count": shard_count,
        "goal_count": goal_count,
        "goals_regenerated": regenerated_goals,
        "goals_semantic_center": goals_semantic_center,
        "goals_goal_center_fallback": goals_goal_center_fallback,
        "goals_skipped_by_whitelist": skipped_by_whitelist,
        "goals_kept_original": kept_original_goals,
        "fallback_goal_count": fallback_goal_count,
        "viewpoints_before": before_vp,
        "viewpoints_after": after_vp,
        "ratio_after": (after_vp / before_vp) if before_vp else 0.0,
        "median_distance_before_mean": float(mean(med_before_acc)) if med_before_acc else 0.0,
        "median_distance_after_mean": float(mean(med_after_acc)) if med_after_acc else 0.0,
        "median_score_after_mean": float(mean(score_after_acc)) if score_after_acc else 0.0,
        "used_radius_mean": float(mean(used_radius_acc)) if used_radius_acc else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate ObjectNav viewpoints with tilt-free semantic coverage "
            "and navmesh-aware radius fallback."
        )
    )
    parser.add_argument(
        "--input-root",
        default="data/datasets/objectnav/hssd-hab",
        help="Input ObjectNav dataset root.",
    )
    parser.add_argument(
        "--output-root",
        default="data/datasets/objectnav/hssd-hab-tiltfree-v2",
        help="Output dataset root.",
    )
    parser.add_argument(
        "--scene-dataset-config",
        default="data/scene_datasets/hssd-hab/hssd-hab.scene_dataset_config.json",
        help="Habitat scene_dataset_config json for simulator initialization.",
    )
    parser.add_argument(
        "--scenes-root",
        default="data/scene_datasets/hssd-hab/scenes",
        help="Directory containing *.scene_instance.json files.",
    )
    parser.add_argument(
        "--whitelist-json",
        default="",
        help="Optional whitelist json containing selected_categories.",
    )
    parser.add_argument(
        "--process-whitelist-only",
        action="store_true",
        help="Only regenerate goals whose object_category is in whitelist.",
    )
    parser.add_argument(
        "--keep-original-if-empty",
        action="store_true",
        help="Keep original viewpoints when regeneration returns empty.",
    )
    parser.add_argument(
        "--keep-topk-if-empty",
        action="store_true",
        help="If threshold removes all candidates, keep top-k coverage candidates.",
    )
    parser.add_argument(
        "--preferred-max-distance",
        type=float,
        default=0.25,
        help="Preferred maximum viewpoint distance to goal position (meters).",
    )
    parser.add_argument(
        "--fallback-max-distance",
        type=float,
        default=0.8,
        help="Maximum fallback distance when navmesh blocks close viewpoints.",
    )
    parser.add_argument(
        "--distance-step",
        type=float,
        default=0.1,
        help="Radius expansion step from preferred to fallback distance.",
    )
    parser.add_argument(
        "--goal-vp-cell-size",
        type=float,
        default=0.1,
        help="Grid cell size for candidate viewpoint generation.",
    )
    parser.add_argument(
        "--score-thresh",
        type=float,
        default=0.12,
        help=(
            "Tilt-free viewpoint quality threshold in [0, 1]. "
            "Legacy 3-tilt IoU is normalized by /3 before proxy scoring."
        ),
    )
    parser.add_argument(
        "--proxy-neighbor-decay",
        type=float,
        default=0.20,
        help="Spatial decay (meters) when transferring normalized legacy IoU to nearby new candidates.",
    )
    parser.add_argument("--gpu-device-id", type=int, default=0)
    parser.add_argument(
        "--navmesh-agent-height",
        type=float,
        default=0.88,
        help="Agent height used when recomputing scene navmesh.",
    )
    parser.add_argument(
        "--navmesh-agent-radius",
        type=float,
        default=0.18,
        help="Agent radius used when recomputing scene navmesh.",
    )
    parser.add_argument("--min-distance", type=float, default=0.1)
    parser.add_argument("--max-keep", type=int, default=128)
    parser.add_argument("--min-keep", type=int, default=8)
    parser.add_argument(
        "--max-drop",
        type=float,
        default=2.0,
        help="Maximum vertical drop to search for navigable candidate point.",
    )
    parser.add_argument(
        "--drop-step",
        type=float,
        default=0.05,
        help="Vertical step size while searching downward for navigable point.",
    )
    parser.add_argument(
        "--max-shards",
        type=int,
        default=0,
        help="Optional cap for number of content shards per split (0 means all).",
    )
    parser.add_argument(
        "--max-goals-per-shard",
        type=int,
        default=0,
        help="Optional cap for goals per shard for fast debug runs (0 means all).",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val"],
        help="Dataset splits to process.",
    )
    args = parser.parse_args()

    if habitat_sim is None:
        raise RuntimeError(
            "habitat_sim is not available in current Python environment. "
            "Please run this script in an env with habitat_sim, e.g. conda run -n hssd39 ..."
        )

    in_root = Path(args.input_root)
    out_root = Path(args.output_root)
    scenes_root = Path(args.scenes_root)
    scene_dataset_config = Path(args.scene_dataset_config)
    whitelist = load_whitelist_categories(Path(args.whitelist_json)) if args.whitelist_json else None

    reports = []
    for split in args.splits:
        reports.append(
            process_split(
                in_root=in_root,
                out_root=out_root,
                scenes_root=scenes_root,
                scene_dataset_config=scene_dataset_config,
                split=split,
                preferred_max_distance=args.preferred_max_distance,
                fallback_max_distance=args.fallback_max_distance,
                distance_step=args.distance_step,
                goal_vp_cell_size=args.goal_vp_cell_size,
                score_thresh=args.score_thresh,
                proxy_neighbor_decay=args.proxy_neighbor_decay,
                keep_topk_if_empty=args.keep_topk_if_empty,
                keep_original_if_empty=args.keep_original_if_empty,
                process_whitelist_only=args.process_whitelist_only,
                whitelist=whitelist,
                gpu_device_id=args.gpu_device_id,
                navmesh_agent_height=args.navmesh_agent_height,
                navmesh_agent_radius=args.navmesh_agent_radius,
                min_distance=args.min_distance,
                max_keep=args.max_keep,
                min_keep=args.min_keep,
                max_drop=args.max_drop,
                drop_step=args.drop_step,
                max_shards=args.max_shards,
                max_goals_per_shard=args.max_goals_per_shard,
            )
        )

    summary = {
        "input_root": str(in_root),
        "output_root": str(out_root),
        "scene_dataset_config": str(scene_dataset_config),
        "scenes_root": str(scenes_root),
        "whitelist_json": args.whitelist_json,
        "process_whitelist_only": args.process_whitelist_only,
        "keep_original_if_empty": args.keep_original_if_empty,
        "keep_topk_if_empty": args.keep_topk_if_empty,
        "preferred_max_distance": args.preferred_max_distance,
        "fallback_max_distance": args.fallback_max_distance,
        "distance_step": args.distance_step,
        "goal_vp_cell_size": args.goal_vp_cell_size,
        "score_thresh": args.score_thresh,
        "proxy_neighbor_decay": args.proxy_neighbor_decay,
        "gpu_device_id": args.gpu_device_id,
        "navmesh_agent_height": args.navmesh_agent_height,
        "navmesh_agent_radius": args.navmesh_agent_radius,
        "min_distance": args.min_distance,
        "max_keep": args.max_keep,
        "min_keep": args.min_keep,
        "max_drop": args.max_drop,
        "drop_step": args.drop_step,
        "max_shards": args.max_shards,
        "max_goals_per_shard": args.max_goals_per_shard,
        "reports": reports,
    }

    out_root.mkdir(parents=True, exist_ok=True)
    with (out_root / "rebuild_viewpoints_report.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=True)

    print(json.dumps(summary, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
