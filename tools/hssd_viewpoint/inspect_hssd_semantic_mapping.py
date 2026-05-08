#!/usr/bin/env python3
"""Inspect HSSD scene_instance object to Habitat-Sim rigid object mapping.

This is a narrow Phase 3 diagnostic tool.  It does not modify datasets or the
main fixed-camera viewpoint prototype.  By default it only checks whether a
scene_instance object can be matched to a runtime rigid object handle.  If
--candidate-index is supplied, it additionally performs a small sentinel-ID
semantic render check for one sampled candidate pose.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import hssd_fixed_camera_viewpoint_prototype as proto  # noqa: E402


CLEAR_NEAREST_MARGIN_METERS = 0.25
MAX_UNIQUE_RESOLVED_DISTANCE_METERS = 0.75


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect whether an HSSD scene_instance object maps cleanly to a "
            "Habitat-Sim rigid object handle and semantic_id."
        )
    )
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--instance-index", required=True, type=int)
    parser.add_argument("--candidate-index", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/hssd_semantic_mapping_inspect"),
    )
    parser.add_argument("--sentinel-id", type=int, default=90000)

    parser.add_argument(
        "--scene-root",
        type=Path,
        default=Path("data/scene_datasets/hssd-hab"),
    )
    parser.add_argument("--scene-dir", default="scenes")
    parser.add_argument(
        "--scene-dataset-config",
        type=Path,
        default=Path("data/scene_datasets/hssd-hab/hssd-hab.scene_dataset_config.json"),
    )
    parser.add_argument("--gpu-device-id", type=int, default=0)
    parser.add_argument("--image-width", type=int, default=640)
    parser.add_argument("--image-height", type=int, default=480)
    parser.add_argument("--hfov", type=float, default=79.0)
    parser.add_argument("--camera-height", type=float, default=0.88)
    parser.add_argument("--camera-pitch-deg", type=float, default=0.0)
    parser.add_argument("--agent-height", type=float, default=0.88)
    parser.add_argument("--agent-radius", type=float, default=0.18)
    parser.add_argument(
        "--candidate-radii",
        nargs="*",
        type=float,
        default=[0.75, 1.0, 1.5, 2.0, 3.0],
    )
    parser.add_argument("--samples-per-object", type=int, default=12)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args()


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    try:
        import numpy as np  # noqa: PLC0415

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    return str(value)


def scene_path_for(args: argparse.Namespace) -> Path:
    return args.scene_root / args.scene_dir / f"{args.scene_id}.scene_instance.json"


def load_target_object(args: argparse.Namespace) -> Dict[str, Any]:
    scene_path = scene_path_for(args)
    scene_data = proto.read_json(scene_path)
    instances = scene_data.get("object_instances") or []
    if args.instance_index < 0 or args.instance_index >= len(instances):
        raise IndexError(
            f"instance_index {args.instance_index} outside object_instances "
            f"range 0..{len(instances) - 1}"
        )

    instance = instances[args.instance_index]
    object_metadata = proto.load_object_metadata(args.scene_root)
    template_name = str(instance.get("template_name") or "")
    resolved_id, meta, tried = proto.resolve_metadata(template_name, object_metadata)
    category, category_source = proto.choose_category(meta)
    translation = proto.parse_vec3(instance.get("translation"))
    scale = proto.parse_vec3(instance.get("non_uniform_scale"))
    dims = meta.get("dims") if isinstance(meta.get("dims"), list) else None
    scaled_dims = proto.scaled_dims(dims, scale)
    center = proto.object_center_from_translation_and_dims(translation, scaled_dims)

    return {
        "scene_id": args.scene_id,
        "scene_path": str(scene_path),
        "instance_index": args.instance_index,
        "category": category,
        "category_source": category_source,
        "template_name": template_name,
        "object_name": meta.get("name", ""),
        "resolved_metadata_id": resolved_id,
        "metadata_lookup_candidates": tried,
        "translation": translation,
        "rotation": instance.get("rotation"),
        "non_uniform_scale": scale,
        "metadata_dims": dims,
        "scaled_dims_static_approx": scaled_dims,
        "object_center_static_approx": center,
        "raw_instance_keys": sorted(instance.keys()),
    }


def vector_to_list(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        parts = [value.x, value.y, value.z]
    else:
        try:
            parts = list(value)
        except TypeError:
            return None
    if len(parts) < 3:
        return None
    out = []
    for part in parts[:3]:
        try:
            val = float(part)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(val):
            return None
        out.append(val)
    return out


def value_or_call(value: Any) -> Any:
    if callable(value):
        try:
            return value()
        except TypeError:
            return value
    return value


def bbox_center_from_object(obj: Any) -> Optional[List[float]]:
    bbox_sources = []
    for attr in ["aabb", "collision_shape_aabb"]:
        if hasattr(obj, attr):
            bbox_sources.append(value_or_call(getattr(obj, attr)))
    node = getattr(obj, "root_scene_node", None)
    if node is not None:
        for attr in ["cumulative_bb", "aabb"]:
            if hasattr(node, attr):
                bbox_sources.append(value_or_call(getattr(node, attr)))

    for bbox in bbox_sources:
        if bbox is None:
            continue
        center = getattr(bbox, "center", None)
        center = value_or_call(center)
        parsed = vector_to_list(center)
        if parsed is not None:
            return parsed

        min_val = None
        max_val = None
        for min_attr, max_attr in [("min", "max"), ("min_point", "max_point")]:
            if hasattr(bbox, min_attr) and hasattr(bbox, max_attr):
                min_val = vector_to_list(value_or_call(getattr(bbox, min_attr)))
                max_val = vector_to_list(value_or_call(getattr(bbox, max_attr)))
                break
        if min_val is not None and max_val is not None:
            return [(min_val[i] + max_val[i]) * 0.5 for i in range(3)]
    return None


def rigid_translation(obj: Any) -> Optional[List[float]]:
    for attr in ["translation", "position"]:
        if hasattr(obj, attr):
            parsed = vector_to_list(value_or_call(getattr(obj, attr)))
            if parsed is not None:
                return parsed
    node = getattr(obj, "root_scene_node", None)
    if node is not None and hasattr(node, "translation"):
        return vector_to_list(value_or_call(getattr(node, "translation")))
    return None


def float_distance(a: Optional[Iterable[float]], b: Optional[Iterable[float]]) -> Optional[float]:
    if a is None or b is None:
        return None
    aa = list(a)
    bb = list(b)
    if len(aa) < 3 or len(bb) < 3:
        return None
    return math.sqrt(sum((float(aa[i]) - float(bb[i])) ** 2 for i in range(3)))


def build_simulator_with_physics(args: argparse.Namespace, scene_path: Path) -> Any:
    proto.lazy_import_habitat()
    habitat_sim = proto.habitat_sim

    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_dataset_config_file = str(args.scene_dataset_config)
    sim_cfg.scene_id = str(scene_path)
    sim_cfg.enable_physics = True
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


def rigid_candidate_record(
    handle: str,
    rigid_obj: Any,
    target_center: Optional[List[float]],
    target_translation: Optional[List[float]],
) -> Dict[str, Any]:
    translation = rigid_translation(rigid_obj)
    aabb_center = bbox_center_from_object(rigid_obj)
    distance_aabb_to_static_center = float_distance(aabb_center, target_center)
    distance_translation_to_static_center = float_distance(translation, target_center)
    distance_translation_to_scene_translation = float_distance(
        translation, target_translation
    )
    distance_values = [
        value
        for value in [
            distance_aabb_to_static_center,
            distance_translation_to_scene_translation,
            distance_translation_to_static_center,
        ]
        if value is not None
    ]
    return {
        "handle": handle,
        "semantic_id": getattr(rigid_obj, "semantic_id", None),
        "object_id": getattr(rigid_obj, "object_id", None),
        "translation": translation,
        "aabb_center": aabb_center,
        "distance_aabb_to_static_center": distance_aabb_to_static_center,
        "distance_translation_to_scene_translation": (
            distance_translation_to_scene_translation
        ),
        "distance_translation_to_static_center": distance_translation_to_static_center,
        "distance_for_sort": min(distance_values) if distance_values else None,
    }


def sort_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            item.get("distance_for_sort") is None,
            item.get("distance_for_sort")
            if item.get("distance_for_sort") is not None
            else float("inf"),
            item.get("handle", ""),
        ),
    )


def resolve_target_rigid_object(sim: Any, target: Dict[str, Any]) -> Dict[str, Any]:
    notes: List[str] = []
    warnings: List[str] = []
    template_name = target.get("template_name") or ""
    target_center = target.get("object_center_static_approx")
    target_translation = target.get("translation")

    try:
        rom = sim.get_rigid_object_manager()
        handles = list(rom.get_object_handles())
    except Exception as exc:  # noqa: BLE001
        return {
            "semantic_mapping_status": "unresolved_rigid_object_manager_error",
            "rigid_object_handle_count": 0,
            "matched_candidate_count": 0,
            "matched_candidates": [],
            "selected_candidate": None,
            "notes": notes,
            "warnings": [repr(exc)],
        }

    matched = []
    for handle in handles:
        if template_name and template_name in handle:
            rigid_obj = rom.get_object_by_handle(handle)
            if rigid_obj is None:
                continue
            matched.append(
                rigid_candidate_record(
                    handle, rigid_obj, target_center, target_translation
                )
            )

    matched = sort_candidates(matched)
    selected = matched[0] if matched else None

    if not matched:
        status = "unresolved_no_template_handle_match"
    elif len(matched) == 1:
        status = "resolved_unique_template"
        dist = selected.get("distance_for_sort")
        if dist is None:
            warnings.append("unique template match has no usable runtime center")
        elif dist > MAX_UNIQUE_RESOLVED_DISTANCE_METERS:
            warnings.append(
                f"unique template match is far from static center: {dist:.3f} m"
            )
    else:
        best = matched[0].get("distance_for_sort")
        second = matched[1].get("distance_for_sort")
        if (
            best is not None
            and second is not None
            and second - best >= CLEAR_NEAREST_MARGIN_METERS
        ):
            status = "resolved_by_nearest_center"
            notes.append(
                "multiple template matches; selected nearest runtime center "
                f"by margin {second - best:.3f} m"
            )
        else:
            status = "ambiguous"
            warnings.append(
                "multiple template matches and nearest-center margin is not reliable"
            )

    return {
        "semantic_mapping_status": status,
        "rigid_object_handle_count": len(handles),
        "matched_candidate_count": len(matched),
        "matched_candidates": matched,
        "selected_candidate": selected,
        "notes": notes,
        "warnings": warnings,
    }


def mask_bbox(mask: Any) -> Optional[Dict[str, int]]:
    np = proto.np
    if mask is None or not np.any(mask):
        return None
    ys, xs = np.where(mask)
    return {
        "x0": int(xs.min()),
        "y0": int(ys.min()),
        "x1": int(xs.max()),
        "y1": int(ys.max()),
        "area": int((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)),
    }


def count_sentinel_pixels(semantic_obs: Any, sentinel_id: int) -> Dict[str, Any]:
    np = proto.np
    arr = np.asarray(semantic_obs)
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    h, w = arr.shape[:2]
    mask = arr == int(sentinel_id)
    visible_pixels = int(np.count_nonzero(mask))
    return {
        "sentinel_semantic_id": int(sentinel_id),
        "sentinel_visible_pixels": visible_pixels,
        "sentinel_image_fraction": float(visible_pixels / max(1, int(h * w))),
        "sentinel_bbox": mask_bbox(mask),
    }


def render_candidate_with_sentinel(
    sim: Any,
    args: argparse.Namespace,
    target: Dict[str, Any],
    selected_candidate: Dict[str, Any],
) -> Dict[str, Any]:
    if selected_candidate is None:
        return {"render_status": "skipped_no_selected_candidate"}
    if args.candidate_index is None:
        return {"render_status": "skipped_no_candidate_index"}

    proto.lazy_import_habitat()
    habitat_sim = proto.habitat_sim
    np = proto.np
    rom = sim.get_rigid_object_manager()
    rigid_obj = rom.get_object_by_handle(selected_candidate["handle"])
    if rigid_obj is None:
        return {"render_status": "failed_selected_handle_not_found"}
    if not hasattr(rigid_obj, "semantic_id"):
        return {"render_status": "failed_selected_object_has_no_semantic_id"}
    try:
        original_semantic_id = int(getattr(rigid_obj, "semantic_id"))
    except (TypeError, ValueError):
        return {
            "render_status": "failed_original_semantic_id_not_integer",
            "original_rigid_semantic_id": repr(getattr(rigid_obj, "semantic_id", None)),
        }

    center = target.get("object_center_static_approx") or target.get("translation")
    if center is None:
        return {"render_status": "failed_missing_target_center"}

    rng = random.Random(args.seed)
    samples_needed = max(int(args.samples_per_object), int(args.candidate_index) + 1)
    candidate_plans = proto.sample_candidate_positions(
        center=center,
        samples_per_object=samples_needed,
        radii=args.candidate_radii,
        rng=rng,
    )
    if args.candidate_index < 0 or args.candidate_index >= len(candidate_plans):
        return {
            "render_status": "failed_candidate_index_out_of_range",
            "candidate_plan_count": len(candidate_plans),
        }

    plan = candidate_plans[args.candidate_index]
    snapped, snap_status = proto.snap_navigable(sim.pathfinder, plan["requested_position"])
    if snapped is None:
        return {
            "render_status": "failed_snap_candidate",
            "candidate_plan": plan,
            "snap_status": snap_status,
        }

    rotation_result = proto.yaw_to_face_target(snapped, np.array(center, dtype=np.float32))
    if rotation_result is None:
        return {
            "render_status": "failed_cannot_compute_yaw_to_target",
            "candidate_plan": plan,
            "snap_status": snap_status,
            "navigable_position": snapped.tolist(),
        }
    rotation, rotation_diag = rotation_result

    try:
        rigid_obj.semantic_id = int(args.sentinel_id)
        agent_state = habitat_sim.AgentState()
        agent_state.position = snapped
        agent_state.rotation = rotation
        sim.get_agent(0).set_state(agent_state)
        observations = sim.get_sensor_observations()
        semantic_obs = observations.get("semantic")
        if semantic_obs is None:
            sentinel_counts = {
                "sentinel_semantic_id": int(args.sentinel_id),
                "sentinel_visible_pixels": 0,
                "sentinel_image_fraction": 0.0,
                "sentinel_bbox": None,
            }
        else:
            sentinel_counts = count_sentinel_pixels(semantic_obs, int(args.sentinel_id))
    finally:
        rigid_obj.semantic_id = original_semantic_id

    return {
        "render_status": "rendered",
        "candidate_index": int(args.candidate_index),
        "candidate_plan": plan,
        "snap_status": snap_status,
        "navigable_position": snapped.tolist(),
        "agent_state": {
            "position": snapped.tolist(),
            "rotation": proto.quat_to_coeffs(rotation).tolist(),
        },
        "rotation_diagnostics": rotation_diag,
        "original_rigid_semantic_id": original_semantic_id,
        **sentinel_counts,
    }


def write_report(result: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = result["target_object"]
    out_path = output_dir / f"{target['scene_id']}_{target['instance_index']}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True, default=json_default)
    return out_path


def main() -> None:
    args = parse_args()
    target = load_target_object(args)
    result: Dict[str, Any] = {
        "target_object": target,
        "scene_id": args.scene_id,
        "instance_index": args.instance_index,
        "enable_physics": True,
        "semantic_mapping_status": "not_run",
        "notes": [],
        "warnings": [],
    }

    sim = None
    try:
        sim = build_simulator_with_physics(args, Path(target["scene_path"]))
        mapping = resolve_target_rigid_object(sim, target)
        result.update(mapping)
        result["semantic_mapping_status"] = mapping["semantic_mapping_status"]
        if args.candidate_index is not None:
            result["sentinel_render_check"] = render_candidate_with_sentinel(
                sim, args, target, mapping.get("selected_candidate")
            )
    except Exception as exc:  # noqa: BLE001
        result["semantic_mapping_status"] = "inspect_failed_exception"
        result["exception"] = repr(exc)
        result["traceback"] = traceback.format_exc()
    finally:
        if sim is not None:
            try:
                sim.close()
            except Exception:
                pass

    out_path = write_report(result, args.output_dir)
    print(json.dumps(
        {
            "output": str(out_path),
            "semantic_mapping_status": result.get("semantic_mapping_status"),
            "rigid_object_handle_count": result.get("rigid_object_handle_count"),
            "matched_candidate_count": result.get("matched_candidate_count"),
            "selected_handle": (
                result.get("selected_candidate") or {}
            ).get("handle"),
            "warnings": result.get("warnings", []),
        },
        indent=2,
        default=json_default,
    ))


if __name__ == "__main__":
    main()
