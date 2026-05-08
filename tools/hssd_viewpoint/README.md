# HSSD Viewpoint Tools

This directory contains prototype and future production tools for HSSD ObjectNav viewpoint generation and quality audits.

Current tool:

- `hssd_fixed_camera_viewpoint_prototype.py`: prototype fixed-camera viewpoint visibility audit/generator.
- `run_fixed_camera_viewpoint_prototype.sh`: Linux wrapper with `dry`, `small`, and `full` modes.

Runtime outputs should go under repo-root `outputs/`, which is ignored by git. Do not commit rendered media, debug images, generated viewpoint shards, or logs.
