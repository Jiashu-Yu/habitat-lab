#!/usr/bin/env python3
"""Prototype fixed-camera HSSD ObjectNav viewpoint generation audit.

Dry-run mode only parses HSSD scene/object/category metadata and writes a
sampling plan. Non-dry-run mode lazily imports Habitat-Sim, samples navigable
positions around each target object, renders fixed-pitch RGB + semantic masks,
and measures target visibility. This script never edits source or dataset files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_CATEGORIES = [
    "table",
    "cabinet",
    "dresser",
    "stool",
    "fridge",
    "bathtub",
    "bench",
    "desk",
    "counter",
    "sink",
    "nightstand",
    "oven",
    "microwave",
    "dishwasher",
    "vase",
]

MIN_VISIBLE_PIXELS = [100, 300, 500, 1000]
MIN_IMAGE_FRACTION = [0.001, 0.003, 0.005, 0.01]
MAX_DISTANCE = [1.0, 1.5, 2.0, 3.0]
MIN_VIEWPOINTS_PER_OBJECT = [1, 3, 5]

habitat_sim = None
np = None
quat_from_two_vectors = None
quat_to_coeffs = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prototype fixed-camera viewpoint generator for expanded HSSD ObjectNav "
            "targets. Use --dry-run to avoid importing Habitat-Sim."
        )
    )
    parser.add_argument(
        "--scene-root",
        type=Path,
        default=Path("data/scene_datasets/hssd-hab"),
        help="HSSD scene dataset root, relative to repo root by default.",
    )
    parser.add_argument(
        "--inventory-json",
        type=Path,
        default=Path("docs/audits/hssd_category_expansion_inventory.json"),
        help="Category expansion inventory JSON for context and category validation.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/hssd_fixed_camera_viewpoint_prototype"),
        help="Directory for JSON/Markdown outputs and optional debug images.",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=list(DEFAULT_CATEGORIES),
        help=(
            "Target categories. Accepts space-separated values and comma-separated "
            "tokens. Defaults to the first expansion shortlist."
        ),
    )
    parser.add_argument(
        "--max-scenes",
        type=int,
        default=3,
        help="Maximum target-containing scenes to process. Use 0 or negative for no limit.",
    )
    parser.add_argument(
        "--max-objects-per-category",
        type=int,
        default=5,
        help="Maximum target objects per category. Use 0 or negative for no limit.",
    )
    parser.add_argument(
        "--samples-per-object",
        type=int,
        default=24,
        help="Candidate positions to sample around each object.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only parse scene/object/category metadata. Do not import or initialize Habitat.",
    )
    parser.add_argument(
        "--debug-images",
        action="store_true",
        help="In non-dry-run mode, save RGB and target-mask debug PNGs under output-dir/debug_images.",
    )
    parser.add_argument("--seed", type=int, default=13, help="Random seed.")

    # Runtime/simulator parameters. These are deliberately explicit so the
    # generated viewpoints can be tied to camera and embodiment assumptions.
    parser.add_argument(
        "--scene-dir",
        default="scenes",
        help="Subdirectory under scene-root containing *.scene_instance.json files.",
    )
    parser.add_argument(
        "--scene-dataset-config",
        type=Path,
        default=Path("data/scene_datasets/hssd-hab/hssd-hab.scene_dataset_config.json"),
        help="Habitat-Sim scene dataset config used only in non-dry-run mode.",
    )
    parser.add_argument("--gpu-device-id", type=int, default=0)
    parser.add_argument("--image-width", type=int, default=640)
    parser.add_argument("--image-height", type=int, default=480)
    parser.add_argument("--hfov", type=float, default=79.0)
    parser.add_argument(
        "--camera-height",
        type=float,
        default=0.88,
        help="Sensor height in agent frame. Default matches LoCoBot-like HSSD configs.",
    )
    parser.add_argument(
        "--camera-pitch-deg",
        type=float,
        default=0.0,
        help="Fixed camera pitch in degrees. No tilt sweep is used.",
    )
    parser.add_argument("--agent-height", type=float, default=0.88)
    parser.add_argument("--agent-radius", type=float, default=0.18)
    parser.add_argument(
        "--candidate-radii",
        nargs="*",
        type=float,
        default=[0.75, 1.0, 1.5, 2.0, 3.0],
        help="Candidate sampling radii around object center.",
    )
    parser.add_argument(
        "--max-debug-images",
        type=int,
        default=100,
        help="Maximum debug image pairs to write when --debug-images is enabled.",
    )
    return parser.parse_args()


def normalize_category(value: Any) -> str:
    text = "" if value is None else str(value).strip().lower()
    text = text.replace(" ", "_").replace("-", "_").replace("/", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def parse_categories(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        for token in str(value).split(","):
            cat = normalize_category(token)
            if cat and cat not in out:
                out.append(cat)
    return out


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_vec3(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if isinstance(value, list):
        parts = value
    else:
        text = str(value).strip().replace("[", "").replace("]", "")
        if not text:
            return None
        parts = [p.strip() for p in text.split(",")]
    out: List[float] = []
    for part in parts:
        try:
            out.append(float(part))
        except (TypeError, ValueError):
            return None
    if len(out) != 3 or not all(math.isfinite(v) for v in out):
        return None
    return out


def template_candidates(template_name: str) -> List[str]:
    name = str(template_name or "").strip()
    candidates: List[str] = []
    if name:
        candidates.append(name)
    if "_part_" in name:
        candidates.append(name.split("_part_", 1)[0])
    if "_:" in name:
        candidates.append(name.split("_:", 1)[0])
    if ":" in name:
        candidates.append(name.split(":", 1)[0])
    deduped: List[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def first_present(row: Dict[str, Any], field_names: Iterable[str]) -> str:
    for field in field_names:
        if field in row and str(row[field]).strip():
            return str(row[field]).strip()
    return ""


def load_object_metadata(scene_root: Path) -> Dict[str, Dict[str, Any]]:
    metadata: Dict[str, Dict[str, Any]] = defaultdict(dict)

    for row in read_csv(scene_root / "semantics" / "objects.csv"):
        obj_id = first_present(row, ["id"])
        if not obj_id:
            continue
        entry = metadata[obj_id]
        entry["id"] = obj_id
        entry["name"] = first_present(row, ["name"])
        entry["main_category"] = normalize_category(first_present(row, ["main_category"]))
        entry["super_category"] = normalize_category(first_present(row, ["super_category"]))
        entry["dims"] = parse_vec3(first_present(row, ["aligned.dims"])) or parse_vec3(
            first_present(row, ["dims"])
        )

    condensed_rows = read_csv(scene_root / "metadata" / "hssd_obj_semantics_condensed.csv")
    hash_field = ""
    condensed_field = ""
    primary_field = ""
    if condensed_rows:
        for field in condensed_rows[0].keys():
            lower = field.lower()
            if "object hash" in lower:
                hash_field = field
            if "condensed" in lower and "semantic" in lower:
                condensed_field = field
            if "primary semantic category" in lower:
                primary_field = field

    for row in condensed_rows:
        obj_id = first_present(row, [hash_field]) if hash_field else ""
        if not obj_id:
            continue
        entry = metadata[obj_id]
        entry["id"] = obj_id
        if condensed_field:
            entry["condensed_category"] = normalize_category(row.get(condensed_field, ""))
        if primary_field:
            entry["primary_semantic_category"] = normalize_category(row.get(primary_field, ""))

    for row in read_csv(scene_root / "metadata" / "object_categories_filtered.csv"):
        obj_id = first_present(row, ["id"])
        if obj_id:
            metadata[obj_id]["clean_category"] = normalize_category(
                first_present(row, ["clean_category"])
            )

    return dict(metadata)


def resolve_metadata(
    template_name: str, object_metadata: Dict[str, Dict[str, Any]]
) -> Tuple[str, Dict[str, Any], List[str]]:
    candidates = template_candidates(template_name)
    for candidate in candidates:
        if candidate in object_metadata:
            return candidate, object_metadata[candidate], candidates
    return candidates[0] if candidates else "", {}, candidates


def choose_category(meta: Dict[str, Any]) -> Tuple[str, str]:
    for source in [
        "condensed_category",
        "primary_semantic_category",
        "main_category",
        "clean_category",
        "super_category",
    ]:
        category = normalize_category(meta.get(source))
        if category and category not in {"na", "n_a", "none", "nan", "null"}:
            return category, source
    return "unknown", "unresolved"


def scaled_dims(
    dims: Optional[List[float]], scale: Optional[List[float]]
) -> Optional[List[float]]:
    if not dims:
        return None
    if not scale:
        scale = [1.0, 1.0, 1.0]
    return [abs(float(dims[i]) * float(scale[i])) for i in range(3)]


def object_center_from_translation_and_dims(
    translation: Optional[List[float]], dims: Optional[List[float]]
) -> Optional[List[float]]:
    if not translation:
        return None
    center = list(translation)
    # HSSD static object origins are often at the base for large furniture.
    # This is only a static aiming approximation; true mode may replace it with
    # a semantic-scene AABB center if a matching semantic object is found.
    if dims:
        center[1] = center[1] + dims[1] * 0.5
    return center


def load_inventory_context(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "available_categories": [],
            "note": "inventory JSON missing; category validation skipped",
        }
    data = read_json(path)
    categories = sorted((data.get("categories") or {}).keys())
    return {
        "exists": True,
        "path": str(path),
        "available_categories": categories,
        "classification_counts": (data.get("classification") or {}).get("bucket_counts", {}),
        "shortlist": data.get("practical_first_expansion_shortlist", {}),
    }


def scene_id_from_path(path: Path) -> str:
    name = path.name
    suffix = ".scene_instance.json"
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return path.stem


def collect_target_objects(
    scene_root: Path,
    scene_dir: str,
    categories: List[str],
    max_scenes: int,
    max_objects_per_category: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    object_metadata = load_object_metadata(scene_root)
    scene_paths = sorted((scene_root / scene_dir).glob("*.scene_instance.json"))
    selected_objects: List[Dict[str, Any]] = []
    selected_scene_ids: List[str] = []
    objects_by_category: Counter[str] = Counter()
    scenes_seen_by_category: Dict[str, set] = defaultdict(set)
    skipped_by_category_cap: Counter[str] = Counter()
    scenes_with_targets = 0

    category_set = set(categories)
    unlimited_scenes = max_scenes <= 0
    unlimited_objects = max_objects_per_category <= 0

    for scene_path in scene_paths:
        scene_id = scene_id_from_path(scene_path)
        if not unlimited_scenes and scenes_with_targets >= max_scenes:
            break

        try:
            scene_data = read_json(scene_path)
        except Exception as exc:  # noqa: BLE001
            selected_objects.append(
                {
                    "scene_id": scene_id,
                    "scene_path": str(scene_path),
                    "error": "scene_json_parse_failed",
                    "exception": repr(exc),
                }
            )
            continue

        scene_target_objects: List[Dict[str, Any]] = []
        instances = scene_data.get("object_instances") or []
        for idx, instance in enumerate(instances):
            if not isinstance(instance, dict):
                continue
            template_name = str(instance.get("template_name") or "")
            resolved_id, meta, tried = resolve_metadata(template_name, object_metadata)
            category, category_source = choose_category(meta)
            if category not in category_set:
                continue
            if not unlimited_objects and objects_by_category[category] >= max_objects_per_category:
                skipped_by_category_cap[category] += 1
                continue

            translation = parse_vec3(instance.get("translation"))
            scale = parse_vec3(instance.get("non_uniform_scale"))
            dims = meta.get("dims") if isinstance(meta.get("dims"), list) else None
            sdims = scaled_dims(dims, scale)
            center = object_center_from_translation_and_dims(translation, sdims)
            object_uid = f"{scene_id}:{idx}:{template_name}"
            record = {
                "object_uid": object_uid,
                "scene_id": scene_id,
                "scene_path": str(scene_path),
                "instance_index": idx,
                "template_name": template_name,
                "resolved_metadata_id": resolved_id,
                "metadata_lookup_candidates": tried,
                "category": category,
                "category_source": category_source,
                "object_name": meta.get("name", ""),
                "translation": translation,
                "rotation": instance.get("rotation"),
                "non_uniform_scale": scale,
                "metadata_dims": dims,
                "scaled_dims_static_approx": sdims,
                "object_center_static_approx": center,
            }
            scene_target_objects.append(record)
            objects_by_category[category] += 1
            scenes_seen_by_category[category].add(scene_id)

        if scene_target_objects:
            scenes_with_targets += 1
            selected_scene_ids.append(scene_id)
            selected_objects.extend(scene_target_objects)

    summary = {
        "scene_files_available": len(scene_paths),
        "target_containing_scenes_selected": len(selected_scene_ids),
        "selected_scene_ids": selected_scene_ids,
        "objects_selected": len(selected_objects),
        "objects_by_category": dict(objects_by_category),
        "scene_count_by_category": {k: len(v) for k, v in scenes_seen_by_category.items()},
        "skipped_by_category_cap": dict(skipped_by_category_cap),
        "metadata_entries": len(object_metadata),
    }
    return selected_objects, summary


def sample_candidate_positions(
    center: List[float],
    samples_per_object: int,
    radii: Sequence[float],
    rng: random.Random,
) -> List[Dict[str, Any]]:
    if samples_per_object <= 0:
        return []
    if not radii:
        radii = [1.0, 1.5, 2.0]
    angle_offset = rng.random() * 2.0 * math.pi
    candidates: List[Dict[str, Any]] = []
    for idx in range(samples_per_object):
        radius = float(radii[idx % len(radii)])
        angle = angle_offset + 2.0 * math.pi * (idx / float(samples_per_object))
        position = [
            center[0] + radius * math.sin(angle),
            center[1],
            center[2] + radius * math.cos(angle),
        ]
        candidates.append(
            {
                "candidate_index": idx,
                "radius": radius,
                "angle_rad": angle,
                "requested_position": position,
            }
        )
    return candidates


def euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def planar_distance_xz(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[2]) - float(b[2])) ** 2)


def lazy_import_habitat() -> None:
    global habitat_sim, np, quat_from_two_vectors, quat_to_coeffs
    if habitat_sim is not None:
        return
    import numpy as np_mod  # noqa: PLC0415
    import habitat_sim as habitat_sim_mod  # noqa: PLC0415
    from habitat_sim.utils.common import (  # noqa: PLC0415
        quat_from_two_vectors as q_from_two_vectors,
    )
    from habitat_sim.utils.common import quat_to_coeffs as q_to_coeffs  # noqa: PLC0415

    np = np_mod
    habitat_sim = habitat_sim_mod
    quat_from_two_vectors = q_from_two_vectors
    quat_to_coeffs = q_to_coeffs


def build_simulator(args: argparse.Namespace, scene_path: Path):
    lazy_import_habitat()

    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_dataset_config_file = str(args.scene_dataset_config)
    sim_cfg.scene_id = str(scene_path)
    sim_cfg.enable_physics = False
    sim_cfg.gpu_device_id = int(args.gpu_device_id)

    rgb_spec = habitat_sim.CameraSensorSpec()
    rgb_spec.uuid = "rgb"
    rgb_spec.sensor_type = habitat_sim.SensorType.COLOR
    rgb_spec.resolution = [int(args.image_height), int(args.image_width)]
    rgb_spec.position = [0.0, float(args.camera_height), 0.0]
    rgb_spec.orientation = [math.radians(float(args.camera_pitch_deg)), 0.0, 0.0]
    rgb_spec.hfov = float(args.hfov)

    sem_spec = habitat_sim.CameraSensorSpec()
    sem_spec.uuid = "semantic"
    sem_spec.sensor_type = habitat_sim.SensorType.SEMANTIC
    sem_spec.resolution = [int(args.image_height), int(args.image_width)]
    sem_spec.position = [0.0, float(args.camera_height), 0.0]
    sem_spec.orientation = [math.radians(float(args.camera_pitch_deg)), 0.0, 0.0]
    sem_spec.hfov = float(args.hfov)

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [rgb_spec, sem_spec]
    if hasattr(agent_cfg, "height"):
        agent_cfg.height = float(args.agent_height)
    if hasattr(agent_cfg, "radius"):
        agent_cfg.radius = float(args.agent_radius)

    sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_cfg]))

    if not sim.pathfinder.is_loaded:
        nav_settings = habitat_sim.NavMeshSettings()
        nav_settings.set_defaults()
        nav_settings.agent_height = float(args.agent_height)
        nav_settings.agent_radius = float(args.agent_radius)
        nav_settings.include_static_objects = True
        sim.recompute_navmesh(sim.pathfinder, nav_settings)

    return sim


def object_category_name(sem_obj: Any) -> str:
    category = getattr(sem_obj, "category", None)
    if category is None:
        return ""
    name_attr = getattr(category, "name", None)
    if callable(name_attr):
        try:
            return str(name_attr())
        except TypeError:
            return ""
    if name_attr is not None:
        return str(name_attr)
    return str(category)


def semantic_object_center(sem_obj: Any) -> Optional[Any]:
    aabb = getattr(sem_obj, "aabb", None)
    if aabb is None:
        return None
    center = getattr(aabb, "center", None)
    if center is None:
        return None
    return np.array(center, dtype=np.float32)


def semantic_object_sizes(sem_obj: Any) -> Optional[List[float]]:
    aabb = getattr(sem_obj, "aabb", None)
    if aabb is None:
        return None
    sizes = getattr(aabb, "sizes", None)
    if sizes is None:
        return None
    return [float(v) for v in list(sizes)]


def find_semantic_object(sim: Any, target: Dict[str, Any]) -> Dict[str, Any]:
    center = target.get("object_center_static_approx") or target.get("translation")
    if not center:
        return {"semantic_object": None, "match_method": "missing_static_center"}
    target_center = np.array(center, dtype=np.float32)
    target_category = normalize_category(target.get("category"))

    best = None
    best_score = float("inf")
    best_info: Dict[str, Any] = {}
    objects = list(getattr(sim.semantic_scene, "objects", []) or [])
    for idx, sem_obj in enumerate(objects):
        if sem_obj is None:
            continue
        sem_center = semantic_object_center(sem_obj)
        if sem_center is None:
            continue
        dist = float(np.linalg.norm(sem_center - target_center))
        sem_category = normalize_category(object_category_name(sem_obj))
        category_bonus = 0.0 if sem_category == target_category else 0.5
        score = dist + category_bonus
        if score < best_score:
            best = sem_obj
            best_score = score
            best_info = {
                "semantic_object_index": idx,
                "semantic_object_id": str(getattr(sem_obj, "id", "")),
                "semantic_category": sem_category,
                "semantic_center": sem_center.tolist(),
                "semantic_sizes": semantic_object_sizes(sem_obj),
                "distance_static_to_semantic_center": dist,
            }

    if best is None:
        return {"semantic_object": None, "match_method": "no_semantic_objects"}
    best_info["semantic_object"] = best
    best_info["match_method"] = "nearest_semantic_aabb_center_with_category_bonus"
    return best_info


def candidate_semantic_ids(sem_obj: Any, sem_obj_index: Optional[int]) -> List[int]:
    ids = set()
    if sem_obj_index is not None:
        ids.add(int(sem_obj_index))
    for attr in ["semantic_id", "object_id", "id"]:
        value = getattr(sem_obj, attr, None)
        if value is None:
            continue
        if isinstance(value, int):
            ids.add(value)
            continue
        for token in re.findall(r"-?\d+", str(value)):
            try:
                ids.add(int(token))
            except ValueError:
                pass
    return sorted(ids)


def snap_navigable(pathfinder: Any, requested: List[float]) -> Tuple[Optional[Any], str]:
    point = np.array(requested, dtype=np.float32)
    if not pathfinder.is_loaded:
        return None, "pathfinder_not_loaded"
    try:
        snapped = np.array(pathfinder.snap_point(point), dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        return None, "snap_point_failed:" + repr(exc)
    if np.isnan(snapped).any():
        return None, "snap_point_nan"
    try:
        if not pathfinder.is_navigable(snapped):
            return None, "snapped_point_not_navigable"
    except Exception as exc:  # noqa: BLE001
        return None, "is_navigable_failed:" + repr(exc)
    return snapped, "snapped_navigable"


def yaw_to_face_target(position: Any, target_center: Any):
    view_dir = np.array(target_center, dtype=np.float32) - np.array(position, dtype=np.float32)
    view_dir[1] = 0.0
    norm = float(np.linalg.norm(view_dir))
    if norm < 1e-6:
        return None
    view_dir /= norm
    return quat_from_two_vectors(habitat_sim.geo.FRONT, view_dir)


def count_target_pixels(semantic_obs: Any, semantic_ids: List[int]) -> Dict[str, Any]:
    arr = np.asarray(semantic_obs)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    h, w = arr.shape[:2]
    total = int(h * w)
    mask = np.zeros((h, w), dtype=bool)
    per_id: Dict[str, int] = {}
    for sem_id in semantic_ids:
        this_mask = arr == sem_id
        count = int(np.count_nonzero(this_mask))
        if count > 0:
            per_id[str(sem_id)] = count
        mask |= this_mask
    visible_pixels = int(np.count_nonzero(mask))
    if visible_pixels == 0:
        bbox = None
        fill_fraction = 0.0
    else:
        ys, xs = np.where(mask)
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        bbox_area = int((x1 - x0 + 1) * (y1 - y0 + 1))
        bbox = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "area": bbox_area}
        fill_fraction = float(visible_pixels / max(1, bbox_area))
    return {
        "visible_pixel_count": visible_pixels,
        "image_fraction": float(visible_pixels / max(1, total)),
        "semantic_id_pixel_counts": per_id,
        "mask_bbox": bbox,
        "mask_bbox_fill_fraction": fill_fraction,
        "mask": mask,
    }


def safe_filename(value: str, max_len: int = 140) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return text[:max_len].strip("_") or "item"


def write_debug_images(
    debug_dir: Path,
    object_uid: str,
    candidate_index: int,
    rgb_obs: Any,
    mask: Any,
) -> List[str]:
    debug_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_filename(f"{object_uid}_candidate_{candidate_index}")
    rgb_path = debug_dir / f"{stem}_rgb.png"
    mask_path = debug_dir / f"{stem}_mask.png"

    rgb = np.asarray(rgb_obs)
    if rgb.ndim == 3 and rgb.shape[2] == 4:
        rgb = rgb[:, :, :3]
    mask_img = (np.asarray(mask).astype(np.uint8) * 255)

    try:
        from PIL import Image  # noqa: PLC0415

        Image.fromarray(rgb.astype(np.uint8)).save(rgb_path)
        Image.fromarray(mask_img).save(mask_path)
    except Exception:
        try:
            import imageio.v2 as imageio  # noqa: PLC0415

            imageio.imwrite(rgb_path, rgb.astype(np.uint8))
            imageio.imwrite(mask_path, mask_img)
        except Exception as exc:  # noqa: BLE001
            return ["debug_image_write_failed:" + repr(exc)]
    return [str(rgb_path), str(mask_path)]


def evaluate_threshold_sweep(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    sweep: Dict[str, Any] = {}
    for min_pixels in MIN_VISIBLE_PIXELS:
        for min_fraction in MIN_IMAGE_FRACTION:
            for max_distance in MAX_DISTANCE:
                key = (
                    f"pix>={min_pixels}|frac>={min_fraction}|"
                    f"dist<={max_distance}"
                )
                count = 0
                for cand in candidates:
                    visible_pixels = cand.get("visible_pixel_count")
                    image_fraction = cand.get("image_fraction")
                    distance = cand.get("distance_to_object")
                    if visible_pixels is None or image_fraction is None or distance is None:
                        continue
                    if (
                        int(visible_pixels) >= min_pixels
                        and float(image_fraction) >= min_fraction
                        and float(distance) <= max_distance
                    ):
                        count += 1
                sweep[key] = {
                    "qualified_viewpoints": count,
                    "passes_min_viewpoints": {
                        str(min_vp): count >= min_vp for min_vp in MIN_VIEWPOINTS_PER_OBJECT
                    },
                }
    return sweep


def process_object_dry_run(
    obj: Dict[str, Any],
    args: argparse.Namespace,
    rng: random.Random,
) -> Dict[str, Any]:
    center = obj.get("object_center_static_approx") or obj.get("translation")
    candidates = sample_candidate_positions(
        center=center,
        samples_per_object=args.samples_per_object,
        radii=args.candidate_radii,
        rng=rng,
    ) if center else []
    return {
        "object": obj,
        "mode": "dry-run",
        "fixed_camera": fixed_camera_summary(args),
        "candidate_plan_count": len(candidates),
        "candidate_plan_sample": candidates[: min(5, len(candidates))],
        "note": "dry-run did not import Habitat, test navigability, render, or compute visibility",
        "threshold_sweep": {},
    }


def process_object_true(
    sim: Any,
    obj: Dict[str, Any],
    args: argparse.Namespace,
    rng: random.Random,
    debug_state: Dict[str, int],
) -> Dict[str, Any]:
    center = obj.get("object_center_static_approx") or obj.get("translation")
    if not center:
        return {
            "object": obj,
            "mode": "habitat-render",
            "error": "missing_object_center",
            "candidate_results": [],
            "threshold_sweep": {},
        }

    sem_match = find_semantic_object(sim, obj)
    sem_obj = sem_match.pop("semantic_object", None)
    sem_obj_index = sem_match.get("semantic_object_index")
    target_center = (
        sem_match.get("semantic_center") if sem_match.get("semantic_center") else center
    )
    semantic_ids = candidate_semantic_ids(sem_obj, sem_obj_index) if sem_obj is not None else []

    candidate_plans = sample_candidate_positions(
        center=center,
        samples_per_object=args.samples_per_object,
        radii=args.candidate_radii,
        rng=rng,
    )
    agent = sim.get_agent(0)
    candidate_results: List[Dict[str, Any]] = []

    for plan in candidate_plans:
        requested = plan["requested_position"]
        snapped, snap_status = snap_navigable(sim.pathfinder, requested)
        result = dict(plan)
        result["snap_status"] = snap_status
        if snapped is None:
            result["rejected"] = True
            result["rejection_reason"] = snap_status
            candidate_results.append(result)
            continue

        rotation = yaw_to_face_target(snapped, np.array(target_center, dtype=np.float32))
        if rotation is None:
            result["rejected"] = True
            result["rejection_reason"] = "cannot_compute_yaw_to_target"
            candidate_results.append(result)
            continue

        agent_state = habitat_sim.AgentState()
        agent_state.position = snapped
        agent_state.rotation = rotation
        agent.set_state(agent_state)
        observations = sim.get_sensor_observations()
        rgb_obs = observations.get("rgb")
        semantic_obs = observations.get("semantic")

        distance = euclidean(snapped.tolist(), target_center)
        planar_dist = planar_distance_xz(snapped.tolist(), target_center)
        visibility = (
            count_target_pixels(semantic_obs, semantic_ids)
            if semantic_obs is not None and semantic_ids
            else {
                "visible_pixel_count": 0,
                "image_fraction": 0.0,
                "semantic_id_pixel_counts": {},
                "mask_bbox": None,
                "mask_bbox_fill_fraction": 0.0,
                "mask": None,
            }
        )
        mask = visibility.pop("mask", None)

        result.update(
            {
                "navigable_position": snapped.tolist(),
                "agent_state": {
                    "position": snapped.tolist(),
                    "rotation": quat_to_coeffs(rotation).tolist(),
                },
                "distance_to_object": float(distance),
                "planar_distance_to_object_xz": float(planar_dist),
                "semantic_ids_checked": semantic_ids,
                "visible_pixel_count": visibility["visible_pixel_count"],
                "image_fraction": visibility["image_fraction"],
                "semantic_id_pixel_counts": visibility["semantic_id_pixel_counts"],
                "mask_bbox": visibility["mask_bbox"],
                "coverage_score": visibility["mask_bbox_fill_fraction"],
                "iou": None,
                "iou_note": "not computed in prototype; no projected object extent/reference mask available",
            }
        )

        if args.debug_images and rgb_obs is not None and mask is not None:
            if debug_state["written"] < args.max_debug_images:
                paths = write_debug_images(
                    args.output_dir / "debug_images",
                    obj["object_uid"],
                    int(plan["candidate_index"]),
                    rgb_obs,
                    mask,
                )
                result["debug_images"] = paths
                debug_state["written"] += 1

        candidate_results.append(result)

    return {
        "object": obj,
        "mode": "habitat-render",
        "fixed_camera": fixed_camera_summary(args),
        "semantic_match": sem_match,
        "semantic_ids_checked": semantic_ids,
        "candidate_results": candidate_results,
        "threshold_sweep": evaluate_threshold_sweep(candidate_results),
    }


def fixed_camera_summary(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "image_width": args.image_width,
        "image_height": args.image_height,
        "hfov": args.hfov,
        "camera_height": args.camera_height,
        "camera_pitch_deg": args.camera_pitch_deg,
        "uses_look_up_down_or_tilt_sweep": False,
        "agent_height": args.agent_height,
        "agent_radius": args.agent_radius,
    }


def group_objects_by_scene(objects: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        if "error" in obj:
            continue
        grouped[obj["scene_id"]].append(obj)
    return dict(grouped)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    rng = random.Random(args.seed)
    categories = parse_categories(args.categories)
    args.categories = categories
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.debug_images:
        (args.output_dir / "debug_images").mkdir(parents=True, exist_ok=True)

    inventory_context = load_inventory_context(args.inventory_json)
    selected_objects, selection_summary = collect_target_objects(
        scene_root=args.scene_root,
        scene_dir=args.scene_dir,
        categories=categories,
        max_scenes=args.max_scenes,
        max_objects_per_category=args.max_objects_per_category,
    )

    result: Dict[str, Any] = {
        "script": "tools/hssd_viewpoint/hssd_fixed_camera_viewpoint_prototype.py",
        "mode": "dry-run" if args.dry_run else "habitat-render",
        "args": serializable_args(args),
        "thresholds": {
            "min_visible_pixels": MIN_VISIBLE_PIXELS,
            "min_image_fraction": MIN_IMAGE_FRACTION,
            "max_distance": MAX_DISTANCE,
            "min_viewpoints_per_object": MIN_VIEWPOINTS_PER_OBJECT,
        },
        "fixed_camera": fixed_camera_summary(args),
        "inventory_context": inventory_context,
        "selection_summary": selection_summary,
        "failed_scenes": [],
        "object_results": [],
    }

    grouped = group_objects_by_scene(selected_objects)
    debug_state = {"written": 0}

    if args.dry_run:
        for scene_id, objects in grouped.items():
            for obj in objects:
                result["object_results"].append(process_object_dry_run(obj, args, rng))
        return finalize_result(result)

    lazy_import_habitat()
    for scene_id, objects in grouped.items():
        scene_path = Path(objects[0]["scene_path"])
        sim = None
        try:
            sim = build_simulator(args, scene_path)
            for obj in objects:
                result["object_results"].append(
                    process_object_true(sim, obj, args, rng, debug_state)
                )
        except Exception as exc:  # noqa: BLE001
            result["failed_scenes"].append(
                {
                    "scene_id": scene_id,
                    "scene_path": str(scene_path),
                    "exception": repr(exc),
                    "traceback": traceback.format_exc(),
                }
            )
        finally:
            if sim is not None:
                try:
                    sim.close()
                except Exception:
                    pass

    result["debug_images_written"] = debug_state["written"]
    return finalize_result(result)


def serializable_args(args: argparse.Namespace) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in vars(args).items():
        if isinstance(value, Path):
            out[key] = str(value)
        else:
            out[key] = value
    return out


def finalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    by_category: Counter[str] = Counter()
    objects_with_any_visible = 0
    rendered_candidates = 0
    candidates_with_visible_pixels = 0

    for obj_result in result["object_results"]:
        obj = obj_result.get("object") or {}
        if obj.get("category"):
            by_category[obj["category"]] += 1
        candidates = obj_result.get("candidate_results") or []
        rendered_candidates += len(
            [c for c in candidates if c.get("visible_pixel_count") is not None]
        )
        if any((c.get("visible_pixel_count") or 0) > 0 for c in candidates):
            objects_with_any_visible += 1
        candidates_with_visible_pixels += len(
            [c for c in candidates if (c.get("visible_pixel_count") or 0) > 0]
        )

    result["summary"] = {
        "objects_processed": len(result["object_results"]),
        "objects_by_category": dict(by_category),
        "failed_scene_count": len(result["failed_scenes"]),
        "objects_with_any_visible_pixels": objects_with_any_visible,
        "rendered_candidates": rendered_candidates,
        "candidates_with_visible_pixels": candidates_with_visible_pixels,
    }
    return result


def write_outputs(result: Dict[str, Any], output_dir: Path) -> Tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hssd_fixed_camera_viewpoint_prototype.json"
    md_path = output_dir / "hssd_fixed_camera_viewpoint_prototype.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(build_markdown(result), encoding="utf-8")
    return json_path, md_path


def build_markdown(result: Dict[str, Any]) -> str:
    args = result["args"]
    summary = result["summary"]
    selection = result["selection_summary"]
    lines = [
        "# HSSD Fixed-camera Viewpoint Prototype",
        "",
        "This is a prototype audit/generation run. Dry-run mode does not import Habitat-Sim. Non-dry-run mode renders fixed-pitch RGB and semantic observations only; it does not use look_up/look_down/tilt sweeps.",
        "",
        "## Run Mode",
        "",
        f"- mode: `{result['mode']}`",
        f"- scene root: `{args['scene_root']}`",
        f"- inventory JSON: `{args['inventory_json']}`",
        f"- output dir: `{args['output_dir']}`",
        f"- target categories: {', '.join(args['categories'])}",
        f"- max scenes: {args['max_scenes']}",
        f"- max objects per category: {args['max_objects_per_category']}",
        f"- samples per object: {args['samples_per_object']}",
        f"- seed: {args['seed']}",
        "",
        "## Fixed Camera / Embodiment",
        "",
    ]
    for key, value in result["fixed_camera"].items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(
        [
            "",
            "## Selection Summary",
            "",
            f"- scene files available: {selection['scene_files_available']}",
            f"- target-containing scenes selected: {selection['target_containing_scenes_selected']}",
            f"- objects selected: {selection['objects_selected']}",
            f"- metadata entries: {selection['metadata_entries']}",
            f"- objects by category: {selection['objects_by_category']}",
            f"- skipped by category cap: {selection['skipped_by_category_cap']}",
            "",
            "## Visibility Summary",
            "",
            f"- objects processed: {summary['objects_processed']}",
            f"- failed scenes: {summary['failed_scene_count']}",
            f"- rendered candidates: {summary['rendered_candidates']}",
            f"- candidates with visible pixels: {summary['candidates_with_visible_pixels']}",
            f"- objects with any visible pixels: {summary['objects_with_any_visible_pixels']}",
            "",
            "## Threshold Sweep",
            "",
            "The sweep is computed per object in JSON. Thresholds are:",
            "",
            f"- min_visible_pixels: {result['thresholds']['min_visible_pixels']}",
            f"- min_image_fraction: {result['thresholds']['min_image_fraction']}",
            f"- max_distance: {result['thresholds']['max_distance']}",
            f"- min_viewpoints_per_object: {result['thresholds']['min_viewpoints_per_object']}",
            "",
        ]
    )

    if result["failed_scenes"]:
        lines.extend(["## Failed Scenes", ""])
        for failure in result["failed_scenes"][:20]:
            lines.append(
                f"- `{failure['scene_id']}`: `{failure['exception']}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- `image_fraction` is visible target pixels divided by full image pixels.",
            "- `coverage_score` is currently mask fill inside the observed target-mask bounding box.",
            "- `iou` is left as `null` in this prototype because a projected full-object reference mask is not yet available.",
            "- A candidate viewpoint is only meaningful for the final dataset after manual visual spot checks and consistency checks against the task camera config.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    result = run(args)
    json_path, md_path = write_outputs(result, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
