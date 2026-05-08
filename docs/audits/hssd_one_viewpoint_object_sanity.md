# HSSD One-Viewpoint Goal Object/Label Sanity Check

Input: `ovon_hssd_audit\outputs\hssd_one_viewpoint_goals.json`

This is a static read-only audit. It reopens the original HSSD ObjectNav dataset files for the 17 exactly-one-viewpoint goals and inspects the goal records. It does not run Habitat simulation, render images, or modify dataset/source files.

## Summary

| one-vp goals | potted_plant goals | scenes | potted scenes |
| --- | --- | --- | --- |
| 17 | 13 | 15 | 11 |

Category counts:

| category | one-vp goals |
| --- | --- |
| chair | 3 |
| couch | 1 |
| potted_plant | 13 |

## What Metadata Exists in These Goal Records

For these 17 native HSSD goal records, the useful static fields are mostly `object_id`, `object_name`, `object_category`, `position`, and `view_points`. The inspected records do **not** expose human-readable object templates, object handles, semantic IDs, bounding boxes, or dimensions in the goal schema.

That means this audit can catch obvious internal inconsistencies, such as category mismatches or missing positions, but it cannot prove that a hash-like `object_name` is truly a potted plant without scene metadata or visualization.

## All 17 Goals

| split | scene_id | category | object_id | object_name | object position | viewpoint position | viewpoint rotation | iou | episode count | sanity issues |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| val | 104862384_172226319 | chair | 123 | f6b5bf924de25d8ca15fe6e233045025e21c2be6_:0000 | `[-5.86212, 0.49523, 0.72276]` | `[-7.26336, 0.19176, 0.58908]` | `[0.0, -0.73992, 0.0, 0.67269]` | 0.1615 | 5 | none |
| train | 105515151_173104068 | chair | 960 | 7df0dd6937e5576eb07c70edcd4d5f6c8d9f549f_part_3_:0000 | `[16.96086, 0.48943, -4.62649]` | `[16.34279, 0.191, -5.86612]` | `[0.0, -0.97338, 0.0, 0.2292]` | 0.0013 | 333 | none |
| train | 108294846_176710506 | chair | 77 | 8a042c83502854ccd12ff65ca73cc273f8a1c7e5_part_1_:0007 | `[-25.7485, 0.51187, -3.34277]` | `[-26.60947, 0.19904, -2.34451]` | `[0.0, -0.34838, 0.0, 0.93735]` | 0.0588 | 333 | none |
| train | 104348160_171513093 | couch | 59 | 85a26550bdf81dc4da5389afd672a933bb5cc4d7_:0000 | `[-0.88389, 0.38503, -1.44201]` | `[-2.29002, 0.19369, -3.13753]` | `[0.0, -0.94067, 0.0, 0.33931]` | 0.0375 | 166 | none |
| train | 102816729 | potted_plant | 164 | c65b5e4533cf2fc2a8c145dddddfc79ba394c25a_:0000 | `[-6.35276, 0.89745, 0.37155]` | `[-5.26389, 0.09346, 0.65518]` | `[0.0, 0.61152, 0.0, 0.79123]` | 0.0471 | 166 | none |
| val | 102816756 | potted_plant | 202 | b79121538512576ec56d645e67e30fc5ebefd858_:0000 | `[-4.77935, 0.9102, -9.11411]` | `[-4.70867, 0.09346, -8.02034]` | `[0.0, 0.03226, 0.0, 0.99948]` | 0.0286 | 5 | none |
| train | 103997403_171030405 | potted_plant | 32 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0000 | `[-8.54819, 0.867, -2.63375]` | `[-9.48319, 0.09346, -3.28375]` | `[0.0, -0.88623, 0.0, 0.46325]` | 0.0183 | 250 | none |
| train | 103997541_171030615 | potted_plant | 101 | 8d017fc7709614540587256fc11b809c9d7dc570_:0000 | `[-6.13742, 1.97775, 2.25798]` | `[-7.13007, 0.08293, 2.06889]` | `[0.0, -0.77043, 0.0, 0.63752]` | 0.0010 | 200 | none |
| train | 103997541_171030615 | potted_plant | 119 | ea233d6e83ef6d189dc92600b820430307b58cea_:0000 | `[-6.15257, 1.9682, 1.85821]` | `[-7.25037, 0.08293, 1.84117]` | `[0.0, -0.71257, 0.0, 0.7016]` | 0.0010 | 200 | none |
| train | 104862687_172226883 | potted_plant | 34 | 34170a3abede075d1e15942197394d95ee063bf7_:0000 | `[-0.7217, 1.06228, 0.05738]` | `[-1.70075, 0.19477, -0.91094]` | `[0.0, -0.92282, 0.0, 0.38523]` | 0.1448 | 166 | none |
| val | 106878915_174887025 | potted_plant | 166 | b827ad39b820d4908a4222dc95dd4b63ecf6c0a6_part_2_:0001 | `[-2.40237, 1.83841, -1.30953]` | `[-3.4789, 0.19388, -1.27182]` | `[0.0, -0.69462, 0.0, 0.71938]` | 0.0011 | 5 | none |
| train | 107734227_176000091 | potted_plant | 130 | 9eccc1dea9b821181517b1bbea57d70c6fad51af_:0000 | `[4.50463, 0.90926, -0.63487]` | `[3.32956, 0.16061, -1.23419]` | `[0.0, -0.85275, 0.0, 0.52233]` | 0.0907 | 200 | none |
| train | 108294798_176710428 | potted_plant | 125 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0006 | `[-10.81291, 1.0194, -3.78635]` | `[-10.11291, 0.1847, -4.63136]` | `[0.0, 0.94077, 0.0, 0.33905]` | 0.0232 | 166 | none |
| train | 108294798_176710428 | potted_plant | 96 | 95603e700e54fdebbae7c3228ecd0f9a849424d3_:0000 | `[-5.70017, 1.56, -3.23232]` | `[-6.33017, 0.1847, -4.13232]` | `[0.0, -0.95374, 0.0, 0.30064]` | 0.0012 | 166 | none |
| train | 108294897_176710602 | potted_plant | 22 | 1babc21347ad1d49accb8c6df726aa9f85bdde93_part_8_:0000 | `[3.7563, 1.37869, -1.08831]` | `[3.66629, 0.08723, -2.07672]` | `[0.0, -0.99897, 0.0, 0.04539]` | 0.0176 | 166 | none |
| train | 108736656_177263304 | potted_plant | 200 | 09b1df19e95ab47e50c8aac06137ef2f51144d34_:0000 | `[-6.2313, 1.75, -4.27467]` | `[-5.55097, 0.09, -5.21933]` | `[0.0, 0.9517, 0.0, 0.30703]` | 0.0321 | 166 | none |
| val | 108736800_177263517 | potted_plant | 175 | 054a4edb60cf2145e98274ad3fcbfc212e6e2445_:0001 | `[2.39459, 0.8096, -1.45107]` | `[1.90205, 0.19356, -2.47046]` | `[0.0, -0.97478, 0.0, 0.22315]` | 0.0077 | 5 | none |

## Potted Plant Focus

| scene_id | count |
| --- | --- |
| 102816729 | 1 |
| 102816756 | 1 |
| 103997403_171030405 | 1 |
| 103997541_171030615 | 2 |
| 104862687_172226883 | 1 |
| 106878915_174887025 | 1 |
| 107734227_176000091 | 1 |
| 108294798_176710428 | 2 |
| 108294897_176710602 | 1 |
| 108736656_177263304 | 1 |
| 108736800_177263517 | 1 |

Potted plant numeric summary:

| field | count | min | median | mean | max |
| --- | --- | --- | --- | --- | --- |
| object_position_y | 13 | 0.8096 | 1.0623 | 1.3037 | 1.9777 |
| viewpoint_position_y | 13 | 0.0829 | 0.0935 | 0.1335 | 0.1948 |
| single_viewpoint_iou | 13 | 0.0010 | 0.0183 | 0.0319 | 0.1448 |

Potted plant records missing bbox: **13 / 13**.
Potted plant records missing dimensions: **13 / 13**.
Potted plant records missing object position: **0 / 13**.

| scene_id | object_id | object_name | object position | object y | viewpoint position | iou | episode count | missing bbox | missing dimensions | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 102816729 | 164 | c65b5e4533cf2fc2a8c145dddddfc79ba394c25a_:0000 | `[-6.35276, 0.89745, 0.37155]` | 0.8974 | `[-5.26389, 0.09346, 0.65518]` | 0.0471 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 102816756 | 202 | b79121538512576ec56d645e67e30fc5ebefd858_:0000 | `[-4.77935, 0.9102, -9.11411]` | 0.9102 | `[-4.70867, 0.09346, -8.02034]` | 0.0286 | 5 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 103997403_171030405 | 32 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0000 | `[-8.54819, 0.867, -2.63375]` | 0.8670 | `[-9.48319, 0.09346, -3.28375]` | 0.0183 | 250 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 103997541_171030615 | 101 | 8d017fc7709614540587256fc11b809c9d7dc570_:0000 | `[-6.13742, 1.97775, 2.25798]` | 1.9777 | `[-7.13007, 0.08293, 2.06889]` | 0.0010 | 200 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 103997541_171030615 | 119 | ea233d6e83ef6d189dc92600b820430307b58cea_:0000 | `[-6.15257, 1.9682, 1.85821]` | 1.9682 | `[-7.25037, 0.08293, 1.84117]` | 0.0010 | 200 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 104862687_172226883 | 34 | 34170a3abede075d1e15942197394d95ee063bf7_:0000 | `[-0.7217, 1.06228, 0.05738]` | 1.0623 | `[-1.70075, 0.19477, -0.91094]` | 0.1448 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 106878915_174887025 | 166 | b827ad39b820d4908a4222dc95dd4b63ecf6c0a6_part_2_:0001 | `[-2.40237, 1.83841, -1.30953]` | 1.8384 | `[-3.4789, 0.19388, -1.27182]` | 0.0011 | 5 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 107734227_176000091 | 130 | 9eccc1dea9b821181517b1bbea57d70c6fad51af_:0000 | `[4.50463, 0.90926, -0.63487]` | 0.9093 | `[3.32956, 0.16061, -1.23419]` | 0.0907 | 200 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 108294798_176710428 | 125 | dd7020ee1b0faeca3b3295e6abc9f3fa4a1a1d13_:0006 | `[-10.81291, 1.0194, -3.78635]` | 1.0194 | `[-10.11291, 0.1847, -4.63136]` | 0.0232 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 108294798_176710428 | 96 | 95603e700e54fdebbae7c3228ecd0f9a849424d3_:0000 | `[-5.70017, 1.56, -3.23232]` | 1.5600 | `[-6.33017, 0.1847, -4.13232]` | 0.0012 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 108294897_176710602 | 22 | 1babc21347ad1d49accb8c6df726aa9f85bdde93_part_8_:0000 | `[3.7563, 1.37869, -1.08831]` | 1.3787 | `[3.66629, 0.08723, -2.07672]` | 0.0176 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 108736656_177263304 | 200 | 09b1df19e95ab47e50c8aac06137ef2f51144d34_:0000 | `[-6.2313, 1.75, -4.27467]` | 1.7500 | `[-5.55097, 0.09, -5.21933]` | 0.0321 | 166 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |
| 108736800_177263517 | 175 | 054a4edb60cf2145e98274ad3fcbfc212e6e2445_:0001 | `[2.39459, 0.8096, -1.45107]` | 0.8096 | `[1.90205, 0.19356, -2.47046]` | 0.0077 | 5 | yes | yes | object_name has no human-readable category hint; semantic label cannot be validated from name alone; no bbox/dimensions fields in goal schema |

## Static Sanity Interpretation

No obvious internal category/metadata inconsistency was detected from the fields available in the native goal records.

The potted_plant one-viewpoint cases are spread across several scenes rather than concentrated in one scene. A few scenes have two potted_plant one-viewpoint goals, but there is no single-scene collapse pattern.

The available goal schema does not include bbox/dimensions, so this static audit cannot determine whether these are physically tiny objects. The `object_position_y` values are present and not obviously missing; some are low and some are around typical tabletop/object heights, but without floor/object geometry this is not enough to call them abnormal.

Many `object_name` values are hash-like asset handles with no readable category word. Therefore, no obvious label mismatch is visible from goal metadata alone, but semantic correctness remains unverified.

## Conclusion

These one-viewpoint goals look most like rare, hard or brittle target cases in the static ObjectNav metadata. They do **not** currently look like an obvious label/object metadata bug from the JSON fields alone. However, because bbox/dimensions and human-readable object templates are absent, this cannot settle whether the potted_plant labels are visually correct. The right next step is visualization or a separate scene-metadata lookup, not training.

Machine-readable details: `ovon_hssd_audit/outputs/hssd_one_viewpoint_object_sanity.json`
