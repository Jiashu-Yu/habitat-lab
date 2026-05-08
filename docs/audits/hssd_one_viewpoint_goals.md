# HSSD Goals With Exactly One Viewpoint

Dataset root: `hssd\habitat-lab\data\datasets\objectnav\hssd-hab`

This is a static read-only audit of native HSSD ObjectNav JSON/GZip shards. It does not run Habitat simulation, render images, train models, or modify source/dataset files.

## Summary

| files | episodes | unique goals | view_points | unique one-viewpoint goals |
| --- | --- | --- | --- | --- |
| 164 | 121800 | 5504 | 1317069 | 17 |

There are **17** unique goals with exactly one viewpoint out of **5504** goals (**0.309%**).
Summed over their scene/category target sets, they appear in target sets for **2698** episodes (**2.215%** of episodes).

Important nuance: an HSSD ObjectNav episode targets a scene/category goal list, not one specific object instance. So if a scene/category contains one one-viewpoint goal, every episode for that scene/category has that goal somewhere in its target set, even though other target objects in the same set may have many viewpoints.

## Category-Level Viewpoint Count Position

| category | goals | one-vp goals | % one-vp | min | p05 | median | mean | p95 | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bed | 418 | 0 | 0.000 | 12 | 150.550 | 390.000 | 440.620 | 907.050 | 1488 |
| chair | 2361 | 3 | 0.127 | 1 | 48.000 | 223.000 | 231.735 | 458.000 | 956 |
| couch | 417 | 1 | 0.240 | 1 | 105.800 | 414.000 | 520.782 | 1437.800 | 2594 |
| potted_plant | 1777 | 13 | 0.732 | 1 | 15.800 | 129.000 | 164.945 | 386.400 | 5589 |
| toilet | 241 | 0 | 0.000 | 6 | 52.000 | 115.000 | 126.556 | 244.000 | 332 |
| tv | 290 | 0 | 0.000 | 2 | 15.450 | 150.500 | 155.134 | 322.000 | 638 |

For every listed goal, `viewpoint_count = 1` is at the bottom of its category's viewpoint-count distribution.

## All Unique Goals With Exactly One Viewpoint

| split | scene_id | category | object_id | object_name | goals_key | goal_index | episodes containing goal in target set | viewpoint position | viewpoint rotation | iou | category position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| val | 104862384_172226319 | chair | 123 | f6b5bf924de25d8ca15fe6e233045025e21c2be6_:0000 | 104862384_172226319_chair | 6 | 5 | [-7.26336, 0.19176, 0.58908] | [0.0, -0.73992, 0.0, 0.67269] | 0.161 | 3/2361 bottom goals |
| train | 105515151_173104068 | chair | 960 | 7df0dd6937e5576eb07c70edcd4d5f6c8d9f549f_part_3_:0000 | 105515151_173104068_chair | 79 | 333 | [16.34279, 0.191, -5.86612] | [0.0, -0.97338, 0.0, 0.2292] | 0.001 | 3/2361 bottom goals |
| train | 108294846_176710506 | chair | 77 | 8a042c83502854ccd12ff65ca73cc273f8a1c7e5_part_1_:0007 | 108294846_176710506_chair | 11 | 333 | [-26.60947, 0.19904, -2.34451] | [0.0, -0.34838, 0.0, 0.93735] | 0.059 | 3/2361 bottom goals |
| train | 104348160_171513093 | couch | 59 | 85a26550bdf81dc4da5389afd672a933bb5cc4d7_:0000 | 104348160_171513093_couch | 2 | 166 | [-2.29002, 0.19369, -3.13753] | [0.0, -0.94067, 0.0, 0.33931] | 0.038 | 1/417 bottom goals |
| train | 102816729 | potted_plant | 164 | c65b5e4533cf2fc2a8c145dddddfc79ba394c25a_:0000 | 102816729_potted_plant | 15 | 166 | [-5.26389, 0.09346, 0.65518] | [0.0, 0.61152, 0.0, 0.79123] | 0.047 | 13/1777 bottom goals |
| val | 102816756 | potted_plant | 202 | b79121538512576ec56d645e67e30fc5ebefd858_:0000 | 102816756_potted_plant | 20 | 5 | [-4.70867, 0.09346, -8.02034] | [0.0, 0.03226, 0.0, 0.99948] | 0.029 | 13/1777 bottom goals |
| train | 103997403_171030405 | potted_plant | 32 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0000 | 103997403_171030405_potted_plant | 2 | 250 | [-9.48319, 0.09346, -3.28375] | [0.0, -0.88623, 0.0, 0.46325] | 0.018 | 13/1777 bottom goals |
| train | 103997541_171030615 | potted_plant | 101 | 8d017fc7709614540587256fc11b809c9d7dc570_:0000 | 103997541_171030615_potted_plant | 7 | 200 | [-7.13007, 0.08293, 2.06889] | [0.0, -0.77043, 0.0, 0.63752] | 0.001 | 13/1777 bottom goals |
| train | 103997541_171030615 | potted_plant | 119 | ea233d6e83ef6d189dc92600b820430307b58cea_:0000 | 103997541_171030615_potted_plant | 15 | 200 | [-7.25037, 0.08293, 1.84117] | [0.0, -0.71257, 0.0, 0.7016] | 0.001 | 13/1777 bottom goals |
| train | 104862687_172226883 | potted_plant | 34 | 34170a3abede075d1e15942197394d95ee063bf7_:0000 | 104862687_172226883_potted_plant | 4 | 166 | [-1.70075, 0.19477, -0.91094] | [0.0, -0.92282, 0.0, 0.38523] | 0.145 | 13/1777 bottom goals |
| val | 106878915_174887025 | potted_plant | 166 | b827ad39b820d4908a4222dc95dd4b63ecf6c0a6_part_2_:0001 | 106878915_174887025_potted_plant | 19 | 5 | [-3.4789, 0.19388, -1.27182] | [0.0, -0.69462, 0.0, 0.71938] | 0.001 | 13/1777 bottom goals |
| train | 107734227_176000091 | potted_plant | 130 | 9eccc1dea9b821181517b1bbea57d70c6fad51af_:0000 | 107734227_176000091_potted_plant | 12 | 200 | [3.32956, 0.16061, -1.23419] | [0.0, -0.85275, 0.0, 0.52233] | 0.091 | 13/1777 bottom goals |
| train | 108294798_176710428 | potted_plant | 125 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0006 | 108294798_176710428_potted_plant | 16 | 166 | [-10.11291, 0.1847, -4.63136] | [0.0, 0.94077, 0.0, 0.33905] | 0.023 | 13/1777 bottom goals |
| train | 108294798_176710428 | potted_plant | 96 | 95603e700e54fdebbae7c3228ecd0f9a849424d3_:0000 | 108294798_176710428_potted_plant | 1 | 166 | [-6.33017, 0.1847, -4.13232] | [0.0, -0.95374, 0.0, 0.30064] | 0.001 | 13/1777 bottom goals |
| train | 108294897_176710602 | potted_plant | 22 | 1babc21347ad1d49accb8c6df726aa9f85bdde93_part_8_:0000 | 108294897_176710602_potted_plant | 1 | 166 | [3.66629, 0.08723, -2.07672] | [0.0, -0.99897, 0.0, 0.04539] | 0.018 | 13/1777 bottom goals |
| train | 108736656_177263304 | potted_plant | 200 | 09b1df19e95ab47e50c8aac06137ef2f51144d34_:0000 | 108736656_177263304_potted_plant | 0 | 166 | [-5.55097, 0.09, -5.21933] | [0.0, 0.9517, 0.0, 0.30703] | 0.032 | 13/1777 bottom goals |
| val | 108736800_177263517 | potted_plant | 175 | 054a4edb60cf2145e98274ad3fcbfc212e6e2445_:0001 | 108736800_177263517_potted_plant | 1 | 5 | [1.90205, 0.19356, -2.47046] | [0.0, -0.97478, 0.0, 0.22315] | 0.008 | 13/1777 bottom goals |

## Interpretation

These one-viewpoint goals are a very small minority of unique goals. They look like edge cases in the static dataset rather than a broad episode-to-goal integrity failure.

However, they still matter for HSSD-to-OVON/VLM/Cosmos work because a one-viewpoint object has an extremely narrow success region. Static integrity is intact, but these goals may be brittle for metric replay, viewpoint quality analysis, or rendered video supervision.

Recommended next check: inspect these 17 goals visually or with a static semantic/object-label audit before using them as evidence of clean viewpoint quality.

Machine-readable details: `ovon_hssd_audit/outputs/hssd_one_viewpoint_goals.json`
