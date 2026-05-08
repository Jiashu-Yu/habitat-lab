# HSSD Category Expansion Inventory

This is a static, read-only inventory. It reads HSSD metadata and scene_instance JSON files only. It does not run Habitat simulation, render images, train models, or modify source/dataset files.

## Inputs Inspected

- Scene root: `hssd\habitat-lab\data\scene_datasets\hssd-hab`
- Scene instance directory counted: `hssd\habitat-lab\data\scene_datasets\hssd-hab\scenes`
- Scene instance files: 168
- Total object instances counted: 53021
- Unique resolved categories: 391
- Unresolved template instances: 0

Metadata files discovered:
- `semantics_objects_csv`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\semantics\objects.csv` exists=True size=4405002
- `semantic_lexicon_json`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\semantics\hssd-hab_semantic_lexicon.json` exists=True size=32286
- `condensed_semantics_csv`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\metadata\hssd_obj_semantics_condensed.csv` exists=True size=1192823
- `object_categories_filtered_csv`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\metadata\object_categories_filtered.csv` exists=True size=86429
- `objects_json`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\metadata\objects.json` exists=True size=4450064
- `fpmodels_with_decomposed_csv`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\metadata\fpmodels-with-decomposed.csv` exists=True size=5169923
- `scene_splits_yaml`: `hssd\habitat-lab\data\scene_datasets\hssd-hab\scene_splits.yaml` exists=True size=3884

## Classification Summary

- High-confidence categories: 52
- Medium-confidence categories: 209
- Reject categories: 130

Classification is heuristic. It uses static metadata only: category names, instance/scene coverage, object origin y, and approximate dimensions from metadata plus instance scale. It does not prove visual recognizability or navigability.

## High-confidence Target Candidates

| category | instances | scenes | native6 | native_equiv | median_y | median_height | median_extent | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seat | 3020 | 168 | no | chair | 0.000 | 0.857 | 0.893 | native_hssd_objectnav_equivalent:chair |
| toilet | 434 | 167 | yes | toilet | 0.000 | 0.850 | 0.850 | native_hssd_objectnav_category |
| cabinet | 2349 | 166 | no |  | 0.000 | 0.899 | 0.951 | common_household_target_with_good_coverage |
| table | 1275 | 166 | no |  | 0.000 | 0.711 | 1.124 | common_household_target_with_good_coverage |
| picture | 1940 | 163 | no |  | 1.750 | 0.701 | 0.813 | common_household_target_with_good_coverage |
| plant | 1994 | 158 | no | potted_plant | 0.001 | 0.797 | 0.853 | native_hssd_objectnav_equivalent:potted_plant |
| bed | 503 | 157 | yes | bed | 0.000 | 1.160 | 2.125 | native_hssd_objectnav_category |
| couch | 370 | 151 | yes | couch | 0.000 | 0.855 | 2.165 | native_hssd_objectnav_category |
| mirror | 831 | 148 | no |  | 1.602 | 1.100 | 1.156 | common_household_target_with_good_coverage |
| tv | 289 | 138 | yes | tv | 1.621 | 0.803 | 1.258 | native_hssd_objectnav_category |
| stool | 550 | 135 | no |  | 0.000 | 0.760 | 0.762 | common_household_target_with_good_coverage |
| dresser | 528 | 135 | no |  | 0.000 | 0.850 | 1.226 | common_household_target_with_good_coverage |
| flowerpot | 518 | 123 | no | potted_plant | 0.560 | 0.761 | 0.800 | native_hssd_objectnav_equivalent:potted_plant |
| sink_cabinet | 232 | 120 | no |  | 0.000 | 1.168 | 1.194 | common_household_target_with_good_coverage |
| vase | 628 | 119 | no |  | 0.760 | 0.310 | 0.392 | common_household_target_with_good_coverage |
| fridge | 164 | 118 | no |  | 0.000 | 1.901 | 1.933 | common_household_target_with_good_coverage |
| bathtub | 169 | 117 | no |  | 0.000 | 0.833 | 1.799 | common_household_target_with_good_coverage |
| wardrobe | 365 | 115 | no |  | 0.000 | 2.090 | 2.100 | common_household_target_with_good_coverage |
| shower | 192 | 109 | no |  | 0.000 | 2.124 | 2.124 | common_household_target_with_good_coverage |
| rack | 319 | 104 | no |  | 0.000 | 1.799 | 1.800 | common_household_target_with_good_coverage |
| washer_dryer | 155 | 102 | no |  | 0.000 | 0.850 | 0.850 | common_household_target_with_good_coverage |
| basket | 279 | 96 | no |  | 0.000 | 0.381 | 0.527 | common_household_target_with_good_coverage |
| bin | 260 | 90 | no |  | 0.000 | 0.391 | 0.392 | common_household_target_with_good_coverage |
| box | 397 | 88 | no |  | 0.750 | 0.242 | 0.380 | common_household_target_with_good_coverage |
| bench | 247 | 87 | no |  | 0.000 | 0.480 | 1.549 | common_household_target_with_good_coverage |
| desk | 172 | 80 | no |  | 0.000 | 0.762 | 1.500 | common_household_target_with_good_coverage |
| counter | 130 | 79 | no |  | 0.000 | 0.898 | 1.783 | common_household_target_with_good_coverage |
| picture_frame | 108 | 57 | no |  | 0.965 | 0.270 | 0.270 | common_household_target_with_good_coverage |
| sink | 93 | 56 | no |  | 0.000 | 0.941 | 0.997 | common_household_target_with_good_coverage |
| nightstand | 112 | 53 | no |  | 0.000 | 0.610 | 0.635 | common_household_target_with_good_coverage |
| laptop | 78 | 53 | no |  | 0.749 | 0.270 | 0.365 | common_household_target_with_good_coverage |
| toilet_paper | 112 | 52 | no |  | 0.670 | 0.174 | 0.240 | common_household_target_with_good_coverage |
| kitchen_lower_cabinet | 114 | 45 | no |  | 0.000 | 0.899 | 0.901 | common_household_target_with_good_coverage |
| laundry_basket | 67 | 44 | no |  | 0.000 | 0.641 | 0.641 | common_household_target_with_good_coverage |
| towel_rack | 76 | 41 | no |  | 0.954 | 0.628 | 0.650 | common_household_target_with_good_coverage |
| oven | 47 | 40 | no |  | 0.000 | 0.915 | 1.103 | common_household_target_with_good_coverage |
| led_tv | 43 | 33 | no | tv | 1.635 | 0.944 | 1.591 | native_hssd_objectnav_equivalent:tv |
| drawer_desk | 40 | 32 | no |  | 0.000 | 0.762 | 1.522 | common_household_target_with_good_coverage |
| toilet_brush | 54 | 30 | no |  | 0.000 | 0.385 | 0.385 | common_household_target_with_good_coverage |
| piano | 36 | 30 | no |  | 0.000 | 1.155 | 1.520 | common_household_target_with_good_coverage |
| clothes_rack | 43 | 24 | no |  | 0.000 | 2.000 | 2.000 | common_household_target_with_good_coverage |
| bath_sink | 29 | 22 | no |  | 0.000 | 1.637 | 1.996 | common_household_target_with_good_coverage |
| washing_machine_and_dryer | 27 | 22 | no |  | 0.000 | 1.525 | 1.525 | common_household_target_with_good_coverage |
| kitchen_counter | 23 | 22 | no |  | 0.000 | 2.397 | 2.795 | common_household_target_with_good_coverage |
| microwave | 22 | 22 | no |  | 0.900 | 0.275 | 0.474 | common_household_target_with_good_coverage |
| shower_tap | 41 | 21 | no |  | 1.444 | 1.218 | 1.218 | common_household_target_with_good_coverage |
| dishwasher | 29 | 21 | no |  | 0.000 | 0.900 | 0.900 | common_household_target_with_good_coverage |
| book_rack | 32 | 18 | no |  | 0.000 | 0.842 | 0.842 | common_household_target_with_good_coverage |
| tablet | 26 | 18 | no |  | 0.750 | 0.087 | 0.241 | common_household_target_with_good_coverage |
| file_cabinet | 27 | 17 | no |  | 0.000 | 0.700 | 0.700 | common_household_target_with_good_coverage |
| tissue_box | 27 | 17 | no |  | 0.760 | 0.214 | 0.214 | common_household_target_with_good_coverage |
| desk_clutter | 26 | 13 | no |  | 0.760 | 0.136 | 0.153 | common_household_target_with_good_coverage |


## Medium-confidence Target Candidates

| category | instances | scenes | native6 | native_equiv | median_y | median_height | median_extent | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lamp | 3076 | 164 | no |  | 2.743 | 0.504 | 0.590 | possibly_too_high_origin_y_p75=2.800 |
| carpet | 1379 | 161 | no |  | 0.000 | 0.011 | 2.286 | possibly_too_small_height_median=0.011; not_in_common_household_target_hint_list |
| decoration | 1284 | 151 | no |  | 1.567 | 0.310 | 0.437 | possibly_too_high_origin_y_p75=1.820; not_in_common_household_target_hint_list |
| shelf | 1174 | 146 | no |  | 1.434 | 0.402 | 1.373 | possibly_too_high_origin_y_p75=1.858 |
| book | 6988 | 142 | no |  | 1.114 | 0.079 | 0.296 | possibly_too_small_height_median=0.079; not_in_common_household_target_hint_list |
| clock | 258 | 111 | no |  | 1.750 | 0.280 | 0.310 | possibly_too_high_origin_y_p75=2.006; not_in_common_household_target_hint_list |
| cup | 772 | 104 | no |  | 0.710 | 0.158 | 0.180 | not_in_common_household_target_hint_list |
| curtain | 715 | 104 | no |  | 0.050 | 2.594 | 2.654 | not_in_common_household_target_hint_list |
| pillow | 1007 | 103 | no |  | 0.500 | 0.406 | 0.516 | not_in_common_household_target_hint_list |
| candle | 347 | 97 | no |  | 0.760 | 0.197 | 0.234 | not_in_common_household_target_hint_list |
| painting | 183 | 87 | no |  | 1.750 | 1.035 | 1.219 | possibly_too_high_origin_y_p75=1.887 |
| container | 183 | 79 | no |  | 0.900 | 0.216 | 0.427 | not_in_common_household_target_hint_list |
| bottle | 354 | 77 | no |  | 0.977 | 0.259 | 0.259 | not_in_common_household_target_hint_list |
| towel | 299 | 77 | no |  | 1.074 | 0.298 | 0.432 | not_in_common_household_target_hint_list |
| bowl | 172 | 71 | no |  | 0.830 | 0.107 | 0.257 | not_in_common_household_target_hint_list |
| hanger | 474 | 68 | no |  | 1.979 | 0.650 | 0.999 | possibly_too_high_origin_y_p75=2.035; not_in_common_household_target_hint_list |
| computer | 110 | 67 | no |  | 0.760 | 0.489 | 0.645 | not_in_common_household_target_hint_list |
| tray | 166 | 66 | no |  | 0.756 | 0.060 | 0.406 | possibly_too_small_height_median=0.060; not_in_common_household_target_hint_list |
| fruit_bowl | 83 | 63 | no |  | 0.900 | 0.248 | 0.326 | not_in_common_household_target_hint_list |
| fireplace | 74 | 61 | no |  | 0.000 | 1.501 | 2.094 | not_in_common_household_target_hint_list |
| plate | 590 | 56 | no |  | 0.700 | 0.102 | 0.325 | not_in_common_household_target_hint_list |
| car | 120 | 55 | no |  | 0.000 | 1.643 | 4.365 | not_in_common_household_target_hint_list |
| stand | 109 | 53 | no |  | 0.000 | 0.457 | 0.950 | not_in_common_household_target_hint_list |
| kitchen_utensil | 79 | 52 | no |  | 0.900 | 0.290 | 0.353 | not_in_common_household_target_hint_list |
| clothes_hanger | 652 | 48 | no |  | 1.977 | 1.295 | 1.901 | possibly_too_high_origin_y_p75=2.034; not_in_common_household_target_hint_list |
| kitchen_appliance | 608 | 47 | no |  | 0.701 | 0.314 | 0.402 | not_in_common_household_target_hint_list |
| coffee_maker | 60 | 47 | no |  | 0.900 | 0.327 | 0.389 | not_in_common_household_target_hint_list |
| toy | 113 | 43 | no |  | 0.000 | 0.400 | 0.557 | not_in_common_household_target_hint_list |
| showerhead | 73 | 43 | no |  | 1.750 | 1.103 | 1.103 | possibly_too_high_origin_y_p75=2.243 |
| blanket | 71 | 43 | no |  | 0.494 | 0.402 | 0.736 | not_in_common_household_target_hint_list |
| tap | 68 | 41 | no |  | 0.900 | 0.177 | 0.295 | not_in_common_household_target_hint_list |
| board | 376 | 40 | no |  | 0.062 | 0.009 | 0.727 | possibly_too_small_height_median=0.009; not_in_common_household_target_hint_list |
| shoe | 199 | 40 | no |  | 0.433 | 0.133 | 0.245 | not_in_common_household_target_hint_list |
| ventilation_hood | 60 | 40 | no |  | 2.800 | 0.693 | 0.899 | possibly_too_high_origin_y_p75=3.013; not_in_common_household_target_hint_list |
| chandelier | 111 | 39 | no |  | 2.800 | 0.817 | 0.890 | possibly_too_high_origin_y_p75=3.460; not_in_common_household_target_hint_list |
| pot | 60 | 39 | no |  | 0.900 | 0.175 | 0.292 | not_in_common_household_target_hint_list |
| drawer | 52 | 37 | no |  | 0.000 | 0.912 | 1.448 | not_in_common_household_target_hint_list |
| rolling_cart | 50 | 36 | no |  | 0.000 | 0.745 | 0.808 | not_in_common_household_target_hint_list |
| fence | 256 | 35 | no |  | 0.000 | 1.000 | 3.000 | not_in_common_household_target_hint_list |
| bag | 84 | 35 | no |  | 0.507 | 0.384 | 0.480 | not_in_common_household_target_hint_list |
| clothes | 1544 | 34 | no |  | 1.616 | 0.024 | 0.503 | possibly_too_small_height_median=0.024; possibly_too_high_origin_y_p75=2.224; not_in_common_household_target_hint_list |
| coat_hanger | 58 | 34 | no |  | 1.750 | 0.218 | 0.720 | not_in_common_household_target_hint_list |
| ladder | 49 | 33 | no |  | 0.000 | 1.309 | 1.491 | not_in_common_household_target_hint_list |
| machine | 42 | 32 | no |  | 0.000 | 0.697 | 0.840 | not_in_common_household_target_hint_list |
| grill | 33 | 32 | no |  | 0.000 | 1.207 | 1.680 | not_in_common_household_target_hint_list |
| liquid_soap | 60 | 30 | no |  | 1.237 | 0.187 | 0.187 | possibly_too_high_origin_y_p75=2.029; not_in_common_household_target_hint_list |
| phone | 60 | 30 | no |  | 0.759 | 0.130 | 0.149 | possibly_too_small_max_extent_median=0.149; not_in_common_household_target_hint_list |
| knife_holder | 35 | 30 | no |  | 0.900 | 0.343 | 0.343 | not_in_common_household_target_hint_list |
| toaster | 34 | 30 | no |  | 0.900 | 0.200 | 0.322 | not_in_common_household_target_hint_list |
| bathroom_utensil | 199 | 29 | no |  | 1.378 | 0.174 | 0.174 | not_in_common_household_target_hint_list |
| gym_equipment | 67 | 29 | no |  | 0.000 | 0.960 | 1.515 | not_in_common_household_target_hint_list |
| flower_stand | 59 | 29 | no |  | 1.639 | 1.072 | 1.072 | not_in_common_household_target_hint_list |
| cooker | 32 | 29 | no |  | 0.000 | 0.903 | 0.907 | not_in_common_household_target_hint_list |
| appliance | 62 | 28 | no |  | 0.750 | 0.270 | 0.452 | not_in_common_household_target_hint_list |
| tree | 86 | 27 | no |  | 0.000 | 2.573 | 2.573 | not_in_common_household_target_hint_list |
| statue | 60 | 27 | no |  | 0.805 | 0.163 | 0.209 | not_in_common_household_target_hint_list |
| doormat | 44 | 27 | no |  | 0.000 | 0.010 | 0.844 | possibly_too_small_height_median=0.010; not_in_common_household_target_hint_list |
| cosmetic | 70 | 26 | no |  | 0.774 | 0.167 | 0.190 | not_in_common_household_target_hint_list |
| cart | 36 | 26 | no |  | 0.000 | 0.865 | 0.966 | not_in_common_household_target_hint_list |
| kettle | 30 | 26 | no |  | 0.900 | 0.282 | 0.287 | not_in_common_household_target_hint_list |
| jar | 36 | 25 | no |  | 0.900 | 0.186 | 0.186 | not_in_common_household_target_hint_list |
| plush_toy | 69 | 24 | no |  | 0.500 | 0.223 | 0.281 | not_in_common_household_target_hint_list |
| toiletry | 56 | 24 | no |  | 0.800 | 0.138 | 0.139 | possibly_too_small_max_extent_median=0.139 |
| bush | 265 | 23 | no |  | 0.000 | 1.750 | 1.750 | not_in_common_household_target_hint_list |
| coffee_machine | 28 | 23 | no |  | 0.900 | 0.365 | 0.365 | not_in_common_household_target_hint_list |
| photo | 47 | 22 | no |  | 0.864 | 0.214 | 0.224 | not_in_common_household_target_hint_list |
| umbrella | 36 | 22 | no |  | 0.000 | 2.603 | 2.908 | not_in_common_household_target_hint_list |
| printer | 25 | 22 | no |  | 0.740 | 0.228 | 0.420 | not_in_common_household_target_hint_list |
| chest | 32 | 21 | no |  | 0.000 | 0.475 | 0.868 | not_in_common_household_target_hint_list |
| kitchen_island | 31 | 20 | no |  | 0.000 | 0.909 | 1.543 | not_in_common_household_target_hint_list |
| swing | 29 | 20 | no |  | 0.000 | 2.024 | 2.192 | not_in_common_household_target_hint_list |
| boiler | 30 | 19 | no |  | 0.000 | 1.335 | 1.335 | not_in_common_household_target_hint_list |
| heater | 41 | 18 | no |  | 1.492 | 0.920 | 0.940 | not_in_common_household_target_hint_list |
| bicycle | 32 | 18 | no |  | 0.000 | 1.091 | 1.651 | not_in_common_household_target_hint_list |
| stove | 26 | 18 | no |  | 0.000 | 0.938 | 0.938 | not_in_common_household_target_hint_list |
| globe | 20 | 18 | no |  | 0.892 | 0.426 | 0.426 | not_in_common_household_target_hint_list |
| pool | 18 | 18 | no |  | -0.000 | 0.079 | 7.857 | possibly_too_small_height_median=0.079; not_in_common_household_target_hint_list |
| soap_dispenser | 39 | 17 | no |  | 0.900 | 0.180 | 0.180 | not_in_common_household_target_hint_list |
| washbasin | 30 | 17 | no |  | 0.000 | 0.717 | 0.772 | not_in_common_household_target_hint_list |
| shoes | 29 | 17 | no |  | 0.000 | 0.133 | 0.224 | possibly_too_low_and_small:origin_y=0.000,height=0.133; not_in_common_household_target_hint_list |
| teapot | 21 | 17 | no |  | 0.900 | 0.169 | 0.352 | not_in_common_household_target_hint_list |
| can | 50 | 16 | no |  | 0.655 | 0.117 | 0.117 | possibly_too_small_max_extent_median=0.117; not_in_common_household_target_hint_list |
| scale | 26 | 16 | no |  | 0.400 | 0.061 | 0.333 | possibly_too_small_height_median=0.061; not_in_common_household_target_hint_list |
| stack_of_papers | 25 | 16 | no |  | 0.750 | 0.070 | 0.128 | possibly_too_small_height_median=0.070; possibly_too_small_max_extent_median=0.128; not_in_common_household_target_hint_list |
| casket | 18 | 16 | no |  | 0.870 | 0.110 | 0.250 | not_in_common_household_target_hint_list |
| blinds | 65 | 15 | no |  | 1.768 | 0.786 | 1.420 | possibly_too_high_origin_y_p75=1.807; not_in_common_household_target_hint_list |
| tool | 19 | 15 | no |  | 0.900 | 1.329 | 1.329 | not_in_common_household_target_hint_list |
| perfume | 18 | 15 | no |  | 0.842 | 0.150 | 0.150 | not_in_common_household_target_hint_list |
| shampoo | 31 | 14 | no |  | 0.760 | 0.176 | 0.176 | not_in_common_household_target_hint_list |
| media_console | 19 | 14 | no |  | 0.530 | 0.138 | 0.341 | not_in_common_household_target_hint_list |
| toilet_cleaner | 17 | 14 | no |  | 0.000 | 0.390 | 0.390 |  |
| wine_rack | 16 | 14 | no |  | 0.900 | 0.275 | 0.372 |  |
| range_hood | 14 | 14 | no |  | 2.800 | 1.193 | 1.196 | possibly_too_high_origin_y_p75=3.083; not_in_common_household_target_hint_list |
| light_switch | 101 | 13 | no |  | 1.248 | 0.160 | 0.160 | not_in_common_household_target_hint_list |
| speaker | 36 | 13 | no |  | 0.915 | 0.260 | 0.520 | possibly_too_high_origin_y_p75=2.050; not_in_common_household_target_hint_list |
| guitar | 34 | 13 | no |  | 0.071 | 0.888 | 0.978 | not_in_common_household_target_hint_list |
| radio | 26 | 13 | no |  | 0.799 | 0.189 | 0.301 | not_in_common_household_target_hint_list |
| pillar | 63 | 12 | no |  | 0.000 | 3.000 | 3.000 | not_in_common_household_target_hint_list |
| food | 41 | 12 | no |  | 0.720 | 0.147 | 0.306 | not_in_common_household_target_hint_list |
| case | 19 | 12 | no |  | 0.000 | 0.375 | 0.614 | not_in_common_household_target_hint_list |
| bathrobe | 17 | 12 | no |  | 1.230 | 0.286 | 1.625 | not_in_common_household_target_hint_list |
| storage_box | 15 | 12 | no |  | 0.760 | 0.490 | 0.610 |  |
| flowerbed | 14 | 12 | no |  | 0.000 | 0.704 | 1.620 |  |
| record_player | 14 | 12 | no |  | 0.725 | 0.450 | 0.470 | not_in_common_household_target_hint_list |
| soap | 34 | 11 | no |  | 1.433 | 0.100 | 0.100 | possibly_too_small_max_extent_median=0.100; not_in_common_household_target_hint_list |
| radiator | 28 | 11 | no |  | 0.523 | 0.986 | 1.021 | not_in_common_household_target_hint_list |
| clothing | 17 | 11 | no |  | 1.550 | 0.286 | 1.625 | not_in_common_household_target_hint_list |
| towel_ring | 17 | 11 | no |  | 1.321 | 0.511 | 0.511 | not_in_common_household_target_hint_list |
| arcade_game | 14 | 11 | no |  | 0.000 | 0.790 | 1.501 | not_in_common_household_target_hint_list |
| mixer | 14 | 11 | no |  | 0.900 | 0.352 | 0.357 | not_in_common_household_target_hint_list |
| vacuum_cleaner | 14 | 11 | no |  | 0.000 | 1.150 | 1.150 | not_in_common_household_target_hint_list |
| pitcher | 12 | 11 | no |  | 0.900 | 0.210 | 0.210 | not_in_common_household_target_hint_list |
| sofa_set | 11 | 11 | no |  | 0.000 | 0.953 | 3.000 |  |
| electric_outlet | 118 | 10 | no |  | 0.348 | 0.160 | 0.290 | not_in_common_household_target_hint_list |
| balcony | 53 | 10 | no |  | 6.600 | 1.054 | 1.177 | possibly_too_high_origin_y_p75=9.900; not_in_common_household_target_hint_list |
| fencing | 41 | 10 | no |  | 0.000 | 0.610 | 0.999 | not_in_common_household_target_hint_list |
| camera | 31 | 10 | no |  | 2.355 | 0.147 | 0.225 | possibly_too_high_origin_y_p75=2.800; not_in_common_household_target_hint_list |
| drinkware | 24 | 10 | no |  | 0.745 | 0.100 | 0.160 | not_in_common_household_target_hint_list |
| chaise | 17 | 10 | no |  | 0.000 | 0.761 | 1.830 | not_in_common_household_target_hint_list |
| dog_bed | 13 | 10 | no |  | 0.000 | 0.203 | 0.813 |  |


## Reject / Unsuitable Categories

These are rejected by first-pass heuristics because they are structural, unknown/misc/part-like, too rare, too small/high/low by static metadata, or not plausible standalone ObjectNav targets. Some may be recoverable after manual review.

| category | instances | scenes | native6 | native_equiv | median_y | median_height | median_extent | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| window | 2501 | 166 | no |  | 1.540 | 1.500 | 1.700 | structural_or_unsuitable_term:window |
| door | 484 | 161 | no |  | 1.120 | 2.200 | 2.200 | structural_or_unsuitable_term:door |
| unknown | 578 | 111 | no |  | 1.750 | 0.150 | 0.640 | structural_or_unsuitable_term:unknown |
| window_shade | 123 | 32 | no |  | 2.069 | 1.292 | 2.002 | structural_or_unsuitable_term:window |
| stairs | 66 | 32 | no |  | 0.000 | 2.366 | 2.660 | structural_or_unsuitable_term:stairs |
| object_outside | 40 | 21 | no |  | 0.000 | 2.701 | 3.651 | structural_or_unsuitable_term:object |
| balcony_railing | 63 | 17 | no |  | 0.000 | 1.005 | 1.814 | structural_or_unsuitable_term:railing |
| wall | 49 | 15 | no |  | -0.000 | 1.932 | 2.800 | structural_or_unsuitable_term:wall |
| unknown_wall | 31 | 15 | no |  | 0.000 | 1.010 | 3.074 | structural_or_unsuitable_term:unknown |
| ceiling_fan | 40 | 13 | no |  | 2.800 | 0.610 | 1.310 | structural_or_unsuitable_term:ceiling |
| beam | 105 | 12 | no |  | 2.800 | 0.303 | 3.386 | structural_or_unsuitable_term:beam |
| wall_outside | 35 | 10 | no |  | -0.000 | 1.932 | 5.956 | structural_or_unsuitable_term:wall |
| wall_board | 18 | 10 | no |  | 1.700 | 0.991 | 0.991 | structural_or_unsuitable_term:wall |
| fireplace_wall | 10 | 10 | no |  | 0.000 | 2.800 | 2.800 | structural_or_unsuitable_term:wall |
| kitchen_wall | 10 | 10 | no |  | 0.000 | 2.900 | 4.550 | structural_or_unsuitable_term:wall |
| window_shutter | 26 | 7 | no |  | 1.648 | 1.412 | 1.998 | structural_or_unsuitable_term:window |
| railing | 23 | 7 | no |  | -0.000 | 0.999 | 3.306 | structural_or_unsuitable_term:railing |
| wall_panel | 13 | 7 | no |  | 0.777 | 0.354 | 2.800 | structural_or_unsuitable_term:wall |
| wall_desk | 8 | 7 | no |  | 1.317 | 0.612 | 1.819 | structural_or_unsuitable_term:wall |
| floor | 33 | 6 | no |  | 0.000 | 0.100 | 2.000 | structural_or_unsuitable_term:floor |
| wall_cubby | 9 | 6 | no |  | 1.750 | 0.481 | 0.481 | structural_or_unsuitable_term:wall |
| roof | 14 | 5 | no |  | 3.348 | 1.102 | 6.404 | structural_or_unsuitable_term:roof |
| floor_mat | 9 | 5 | no |  | 0.000 | 0.005 | 0.598 | structural_or_unsuitable_term:floor |
| garage_door | 6 | 5 | no |  | 0.000 | 3.073 | 3.073 | structural_or_unsuitable_term:door |
| floor_outside | 5 | 4 | no |  | 0.000 | 1.360 | 5.102 | structural_or_unsuitable_term:floor |
| dressing_table | 4 | 4 | no |  | 0.000 | 1.334 | 1.334 | rare: instances=4, scenes=4, thresholds=5/3 |
| fire_dish | 4 | 4 | no |  | 0.000 | 0.390 | 1.124 | rare: instances=4, scenes=4, thresholds=5/3; not_in_common_household_target_hint_list |
| frame | 4 | 4 | no |  | 0.836 |  |  | rare: instances=4, scenes=4, thresholds=5/3; not_in_common_household_target_hint_list |
| newspaper_basket | 4 | 4 | no |  | 0.000 | 0.700 | 0.700 | rare: instances=4, scenes=4, thresholds=5/3 |
| thermostat | 4 | 4 | no |  | 0.900 | 0.203 | 0.203 | rare: instances=4, scenes=4, thresholds=5/3; not_in_common_household_target_hint_list |
| throw_blanket | 4 | 4 | no |  | 0.498 | 0.082 | 0.535 | rare: instances=4, scenes=4, thresholds=5/3; not_in_common_household_target_hint_list |
| shower_door | 5 | 3 | no |  | 0.000 | 2.000 | 2.000 | structural_or_unsuitable_term:door |
| hose | 4 | 3 | no |  | 0.000 | 0.567 | 0.567 | rare: instances=4, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| switch | 4 | 3 | no |  | 1.414 | 0.148 | 0.188 | rare: instances=4, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| toilet_sink | 4 | 3 | no |  | 0.000 | 1.611 | 1.611 | rare: instances=4, scenes=3, thresholds=5/3 |
| towel_basket | 4 | 3 | no |  | 1.055 | 0.273 | 0.522 | rare: instances=4, scenes=3, thresholds=5/3; possibly_too_high_origin_y_p75=2.110 |
| urinal | 4 | 3 | no |  | 0.000 | 0.536 | 0.536 | rare: instances=4, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| vent | 4 | 3 | no |  | 1.041 | 0.290 | 0.290 | rare: instances=4, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| awning | 3 | 3 | no |  | 0.000 | 2.408 | 4.426 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| desk_and_chairs | 3 | 3 | no |  | 0.000 | 0.482 | 0.840 | rare: instances=3, scenes=3, thresholds=5/3 |
| jewelry_box | 3 | 3 | no |  | 0.867 | 0.072 | 0.205 | rare: instances=3, scenes=3, thresholds=5/3; possibly_too_small_height_median=0.072 |
| motorcycle | 3 | 3 | no |  | 0.000 | 1.158 | 2.447 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| screen | 3 | 3 | no |  | -0.000 | 1.780 | 1.780 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| sculpture | 3 | 3 | no |  | 0.820 | 0.420 | 0.420 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| sitting_area | 3 | 3 | no |  | 0.000 | 0.560 | 0.928 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| staircase | 3 | 3 | no |  | 0.000 | 3.450 | 4.730 | rare: instances=3, scenes=3, thresholds=5/3; not_in_common_household_target_hint_list |
| wreath | 3 | 3 | no |  | 1.749 | 0.183 | 0.640 | rare: instances=3, scenes=3, thresholds=5/3; possibly_too_high_origin_y_p75=1.830; not_in_common_household_target_hint_list |
| shower_wall | 8 | 2 | no |  | 3.320 | 9.600 | 9.600 | structural_or_unsuitable_term:wall |
| bathroom_shelf | 7 | 2 | no |  | 0.000 | 1.050 | 1.050 | rare: instances=7, scenes=2, thresholds=5/3 |
| cover | 7 | 2 | no |  | 2.208 | 0.749 | 1.700 | rare: instances=7, scenes=2, thresholds=5/3; possibly_too_high_origin_y_p75=2.348; not_in_common_household_target_hint_list |
| fruit | 7 | 2 | no |  | 0.760 | 0.106 | 0.125 | rare: instances=7, scenes=2, thresholds=5/3; possibly_too_small_max_extent_median=0.125; not_in_common_household_target_hint_list |
| magazine | 6 | 2 | no |  | 0.540 |  |  | rare: instances=6, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| security_camera | 5 | 2 | no |  | 2.800 | 0.149 | 0.172 | rare: instances=5, scenes=2, thresholds=5/3; possibly_too_high_origin_y_p75=2.800; not_in_common_household_target_hint_list |
| #n_a | 4 | 2 | no |  | 0.000 |  |  | rare: instances=4, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| bed_table | 4 | 2 | no |  | -0.000 | 0.592 | 0.605 | rare: instances=4, scenes=2, thresholds=5/3 |
| freezer | 4 | 2 | no |  | 0.000 | 0.945 | 1.295 | rare: instances=4, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| lamp_table | 4 | 2 | no |  | 0.697 | 0.716 | 0.716 | rare: instances=4, scenes=2, thresholds=5/3 |
| platter | 4 | 2 | no |  | 1.060 | 0.030 | 0.220 | rare: instances=4, scenes=2, thresholds=5/3; possibly_too_small_height_median=0.030; not_in_common_household_target_hint_list |
| step | 4 | 2 | no |  | 0.000 | 0.832 | 2.280 | rare: instances=4, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| art_stand | 3 | 2 | no |  | 0.960 | 0.202 | 0.508 | rare: instances=3, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| bar_cabinet | 3 | 2 | no |  | 0.000 | 1.000 | 1.743 | rare: instances=3, scenes=2, thresholds=5/3 |
| cloth | 3 | 2 | no |  | 1.099 | 0.342 | 1.800 | rare: instances=3, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| decorative_bowl | 3 | 2 | no |  | 0.980 | 0.220 | 0.390 | rare: instances=3, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| kitchen_shelf | 3 | 2 | no |  | 0.000 | 0.930 | 1.000 | rare: instances=3, scenes=2, thresholds=5/3 |
| person | 3 | 2 | no |  | 0.000 | 1.197 | 1.500 | rare: instances=3, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| soapbox | 3 | 2 | no |  | 1.960 | 0.130 | 0.130 | rare: instances=3, scenes=2, thresholds=5/3; possibly_too_small_max_extent_median=0.130; possibly_too_high_origin_y_p75=1.960 |
| watering_can | 3 | 2 | no |  | 0.000 | 0.335 | 0.577 | rare: instances=3, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| baby_changing_station | 2 | 2 | no |  | 0.000 | 0.997 | 1.131 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| box_of_fruit | 2 | 2 | no |  | 0.380 | 0.153 | 0.246 | rare: instances=2, scenes=2, thresholds=5/3 |
| clothes_hanger_rod | 2 | 2 | no |  | 0.000 | 1.600 | 1.740 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| decorative_plate | 2 | 2 | no |  | 1.120 | 0.220 | 0.220 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| drum | 2 | 2 | no |  | 0.000 | 0.940 | 1.034 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| fireplace_utensil | 2 | 2 | no |  | 0.000 | 0.767 | 0.767 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| object | 2 | 2 | no |  | 0.000 | 0.534 | 1.169 | structural_or_unsuitable_term:object |
| painting_frame | 2 | 2 | no |  | 0.378 | 0.290 | 0.290 | rare: instances=2, scenes=2, thresholds=5/3 |
| projector | 2 | 2 | no |  | 2.852 | 0.441 | 0.441 | rare: instances=2, scenes=2, thresholds=5/3; possibly_too_high_origin_y_p75=3.076; not_in_common_household_target_hint_list |
| projector_screen | 2 | 2 | no |  | 0.192 | 1.780 | 1.780 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| rail | 2 | 2 | no |  | 1.781 | 0.339 | 2.270 | structural_or_unsuitable_term:rail |
| sauna_heater | 2 | 2 | no |  | -0.000 | 2.125 | 2.475 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| shack | 2 | 2 | no |  | 0.000 | 2.147 | 2.147 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| shelf_cabinet | 2 | 2 | no |  | 0.381 | 0.508 | 0.940 | rare: instances=2, scenes=2, thresholds=5/3 |
| shirt | 2 | 2 | no |  | 0.001 | 0.827 | 0.827 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| shower_hose | 2 | 2 | no |  | 1.641 | 1.327 | 1.327 | rare: instances=2, scenes=2, thresholds=5/3 |
| slide | 2 | 2 | no |  | -0.000 | 1.024 | 2.098 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| smoke_alarm | 2 | 2 | no |  | 2.985 | 0.036 | 0.140 | rare: instances=2, scenes=2, thresholds=5/3; possibly_too_small_height_median=0.036; possibly_too_small_max_extent_median=0.140 |
| soap_dish | 2 | 2 | no |  | 0.430 | 0.027 | 0.126 | rare: instances=2, scenes=2, thresholds=5/3; possibly_too_small_height_median=0.027; possibly_too_small_max_extent_median=0.126 |
| stair_step | 2 | 2 | no |  | 0.000 | 2.619 | 2.619 | structural_or_unsuitable_term:stair |
| toilet_brush_holder | 2 | 2 | no |  | 0.223 | 0.446 | 0.446 | rare: instances=2, scenes=2, thresholds=5/3 |
| towel_holder | 2 | 2 | no |  | 0.921 | 0.294 | 0.294 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| wooden_house | 2 | 2 | no |  | 0.450 | 2.405 | 3.780 | rare: instances=2, scenes=2, thresholds=5/3; not_in_common_household_target_hint_list |
| semi_chair | 24 | 1 | no |  | 0.001 |  |  | rare: instances=24, scenes=1, thresholds=5/3 |
| hat | 7 | 1 | no |  | 0.729 |  |  | rare: instances=7, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| window_frame | 6 | 1 | no |  | 2.527 | 0.438 | 1.852 | structural_or_unsuitable_term:window |
| barrel | 4 | 1 | no |  | 0.000 | 0.917 | 0.917 | rare: instances=4, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| box_of_tissue | 3 | 1 | no |  | 0.710 | 0.157 | 0.250 | rare: instances=3, scenes=1, thresholds=5/3 |
| partition | 2 | 1 | no |  | 0.900 | 0.050 | 0.350 | rare: instances=2, scenes=1, thresholds=5/3; possibly_too_small_height_median=0.050; not_in_common_household_target_hint_list |
| sunbed | 2 | 1 | no |  | 0.000 | 0.750 | 2.121 | rare: instances=2, scenes=1, thresholds=5/3 |
| bedframe | 1 | 1 | no |  | 1.294 | 1.611 | 2.220 | rare: instances=1, scenes=1, thresholds=5/3 |
| bridge | 1 | 1 | no |  | 0.000 | 0.766 | 3.547 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| bust | 1 | 1 | no |  | 1.070 | 0.697 | 0.735 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| cake_stand | 1 | 1 | no |  | 0.950 | 0.460 | 0.460 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| decorative_quilt | 1 | 1 | no |  | 0.000 | 0.659 | 2.035 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| dj_table | 1 | 1 | no |  | 0.000 | 1.584 | 1.717 | rare: instances=1, scenes=1, thresholds=5/3 |
| fountain | 1 | 1 | no |  | 0.770 | 0.673 | 0.673 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| garden_bower | 1 | 1 | no |  | -0.000 | 2.100 | 2.100 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| hand_wash | 1 | 1 | no |  | 0.000 | 1.260 | 1.260 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| mailbox | 1 | 1 | no |  | 0.000 | 1.287 | 1.287 | rare: instances=1, scenes=1, thresholds=5/3 |
| musical_instrument | 1 | 1 | no |  | 0.000 | 1.151 | 1.151 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| office_utensil | 1 | 1 | no |  | 0.840 | 0.003 | 0.062 | rare: instances=1, scenes=1, thresholds=5/3; possibly_too_small_height_median=0.003; possibly_too_small_max_extent_median=0.062 |
| panel | 1 | 1 | no |  | 0.000 | 1.304 | 1.304 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| photo_mount | 1 | 1 | no |  | 0.770 | 0.100 | 0.150 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| ping_pong_table | 1 | 1 | no |  | 0.000 | 0.846 | 1.610 | rare: instances=1, scenes=1, thresholds=5/3 |
| pipe | 1 | 1 | no |  | 3.000 | 0.674 | 0.731 | rare: instances=1, scenes=1, thresholds=5/3; possibly_too_high_origin_y_p75=3.000; not_in_common_household_target_hint_list |
| playground | 1 | 1 | no |  | 0.000 | 1.320 | 1.881 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| playground_element | 1 | 1 | no |  | 0.000 | 3.962 | 7.940 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| rock | 1 | 1 | no |  | 0.000 | 0.403 | 1.233 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| rocking_horse | 1 | 1 | no |  | -0.000 | 0.490 | 0.799 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| rod | 1 | 1 | no |  | 1.165 | 0.044 | 0.820 | rare: instances=1, scenes=1, thresholds=5/3; possibly_too_small_height_median=0.044; not_in_common_household_target_hint_list |
| shovel | 1 | 1 | no |  | 0.426 | 0.030 | 0.774 | rare: instances=1, scenes=1, thresholds=5/3; possibly_too_small_height_median=0.030; not_in_common_household_target_hint_list |
| skateboard | 1 | 1 | no |  | 0.088 | 0.119 | 0.749 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| spice_rack | 1 | 1 | no |  | 0.900 | 0.353 | 0.353 | rare: instances=1, scenes=1, thresholds=5/3 |
| storage | 1 | 1 | no |  | 0.000 | 2.720 | 3.800 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| stuffed_animal | 1 | 1 | no |  | 0.000 | 1.798 | 1.798 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| telescope | 1 | 1 | no |  | -0.000 | 1.151 | 1.151 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| tissue | 1 | 1 | no |  | 0.730 | 0.350 | 0.350 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| toilet_stall | 1 | 1 | no |  | -0.000 | 0.733 | 0.733 | rare: instances=1, scenes=1, thresholds=5/3 |
| unknown_outside | 1 | 1 | no |  | 1.750 | 0.271 | 0.271 | structural_or_unsuitable_term:unknown |
| wheelbarrow | 1 | 1 | no |  | 0.000 | 0.607 | 1.024 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |
| wine_cabinet | 1 | 1 | no |  | -0.000 | 0.700 | 1.526 | rare: instances=1, scenes=1, thresholds=5/3 |
| yard | 1 | 1 | no |  | 0.000 | 0.340 | 3.657 | rare: instances=1, scenes=1, thresholds=5/3; not_in_common_household_target_hint_list |


## Category Inventory Details

The JSON output contains full per-category records, including top scenes, top metadata IDs, top object names, static y/dimension distributions, and sample instances.

Important static caveats:

- `translation[1]` is treated as object origin height, not guaranteed physical bbox center.
- Metadata dimensions are approximate and then multiplied by `non_uniform_scale`; rotations are not used for oriented bbox reconstruction.
- Categories come from HSSD semantic metadata, with priority: condensed category, primary semantic category, main category, clean category, then super category.
- Fixed-camera visibility cannot be proven from metadata alone; it requires rendering semantic/object-id masks with the actual evaluation camera.

## Fixed-camera Viewpoint Generation Feasibility Design

Because the current action space does not include look_up/look_down/tilt, expanded ObjectNav viewpoints should be generated and validated using the policy/evaluation camera pitch directly.

Required fields/checks:
- Required input: scene_id and scene_instance path
- Required input: object instance template_name / resolved metadata id
- Required input: semantic category chosen for ObjectNav target
- Required input: object translation, rotation, scale
- Required input: object dimensions or bounding box approximation when available
- Required input: agent embodiment: height, radius, camera height, HFOV, resolution, fixed pitch
- Required input: navmesh/pathfinder access for candidate navigability and geodesic distance
- Required input: semantic render or object-id mask for visibility scoring
- Candidate position check: sample candidate positions around object at multiple radii/yaw angles
- Candidate position check: snap or reject positions using navmesh/pathfinder
- Candidate position check: reject positions on a different floor/island from the object when determinable
- Candidate position check: orient agent yaw toward object center; keep camera pitch fixed
- Candidate position check: enforce min/max Euclidean and geodesic distance to object
- Candidate position check: reject collisions using target agent radius/height
- Fixed-camera visibility check: render semantic/object-id mask from fixed-pitch camera only
- Fixed-camera visibility check: count visible target pixels
- Fixed-camera visibility check: compute target mask bounding box and image-area fraction
- Fixed-camera visibility check: compute IoU or coverage score using projected object mask/bbox
- Fixed-camera visibility check: reject viewpoints that only pass with look_up/look_down/tilt
- Fixed-camera visibility check: store camera assumptions with generated dataset metadata

Suggested first threshold sweep:
- `min_visible_pixels`: [100, 500, 1000]
- `min_visible_image_fraction`: [0.001, 0.005, 0.01]
- `min_viewpoints_per_object`: [3, 5, 10]
- `distance_to_object_meters`: ['0.5-3.0 sweep, category-dependent']
- `success_distance_meters`: [0.1, 0.25, 0.5]

Outputs to store per accepted viewpoint:
- agent_state.position
- agent_state.rotation
- camera_hfov/resolution/pitch used for generation
- visible_pixel_count
- visible_image_fraction
- iou_or_coverage_score
- euclidean_distance_to_object
- geodesic_distance_to_object_or_viewpoint when available
- failure reason for rejected candidates

Quality gates:
- each accepted object should have at least the chosen min_viewpoints_per_object
- category-level viewpoint count distribution should not be dominated by 0-1 viewpoint objects
- accepted viewpoints should work without tilt actions
- visual spot checks should confirm object/category correctness before training
- episode success regions should be regenerated after category expansion

## Practical First Expansion Set

A conservative first pass should start from high-confidence, high-coverage household objects and then manually spot-check rendered examples before any training. Native six categories and native-equivalent metadata categories remain useful controls; non-native candidates are candidates for expansion, not benchmark-ready labels.

Native/native-equivalent controls:

| category | instances | scenes | native6 | native_equiv | median_height | notes |
| --- | --- | --- | --- | --- | --- | --- |
| seat | 3020 | 168 | no | chair | 0.857 | native_hssd_objectnav_equivalent:chair |
| bed | 503 | 157 | yes | bed | 1.160 | native_hssd_objectnav_category |
| couch | 370 | 151 | yes | couch | 0.855 | native_hssd_objectnav_category |
| plant | 1994 | 158 | no | potted_plant | 0.797 | native_hssd_objectnav_equivalent:potted_plant |
| flowerpot | 518 | 123 | no | potted_plant | 0.761 | native_hssd_objectnav_equivalent:potted_plant |
| toilet | 434 | 167 | yes | toilet | 0.850 | native_hssd_objectnav_category |
| tv | 289 | 138 | yes | tv | 0.803 | native_hssd_objectnav_category |
| led_tv | 43 | 33 | no | tv | 0.944 | native_hssd_objectnav_equivalent:tv |


Recommended non-native first expansion candidates:

| category | instances | scenes | median_height | median_extent | notes |
| --- | --- | --- | --- | --- | --- |
| table | 1275 | 166 | 0.711 | 1.124 | common_household_target_with_good_coverage |
| cabinet | 2349 | 166 | 0.899 | 0.951 | common_household_target_with_good_coverage |
| dresser | 528 | 135 | 0.850 | 1.226 | common_household_target_with_good_coverage |
| stool | 550 | 135 | 0.760 | 0.762 | common_household_target_with_good_coverage |
| sink_cabinet | 232 | 120 | 1.168 | 1.194 | common_household_target_with_good_coverage |
| fridge | 164 | 118 | 1.901 | 1.933 | common_household_target_with_good_coverage |
| bathtub | 169 | 117 | 0.833 | 1.799 | common_household_target_with_good_coverage |
| wardrobe | 365 | 115 | 2.090 | 2.100 | common_household_target_with_good_coverage |
| shower | 192 | 109 | 2.124 | 2.124 | common_household_target_with_good_coverage |
| washer_dryer | 155 | 102 | 0.850 | 0.850 | common_household_target_with_good_coverage |
| basket | 279 | 96 | 0.381 | 0.527 | common_household_target_with_good_coverage |
| bin | 260 | 90 | 0.391 | 0.392 | common_household_target_with_good_coverage |
| bench | 247 | 87 | 0.480 | 1.549 | common_household_target_with_good_coverage |
| desk | 172 | 80 | 0.762 | 1.500 | common_household_target_with_good_coverage |
| counter | 130 | 79 | 0.898 | 1.783 | common_household_target_with_good_coverage |
| sink | 93 | 56 | 0.941 | 0.997 | common_household_target_with_good_coverage |
| nightstand | 112 | 53 | 0.610 | 0.635 | common_household_target_with_good_coverage |
| kitchen_lower_cabinet | 114 | 45 | 0.899 | 0.901 | common_household_target_with_good_coverage |
| laundry_basket | 67 | 44 | 0.641 | 0.641 | common_household_target_with_good_coverage |
| oven | 47 | 40 | 0.915 | 1.103 | common_household_target_with_good_coverage |
| microwave | 22 | 22 | 0.275 | 0.474 | common_household_target_with_good_coverage |
| dishwasher | 29 | 21 | 0.900 | 0.900 | common_household_target_with_good_coverage |
| vase | 628 | 119 | 0.310 | 0.392 | common_household_target_with_good_coverage |
| laptop | 78 | 53 | 0.270 | 0.365 | common_household_target_with_good_coverage |


Fixed-camera or label-caution categories:

| category | instances | scenes | median_y | median_height | notes |
| --- | --- | --- | --- | --- | --- |
| picture | 1940 | 163 | 1.750 | 0.701 | common_household_target_with_good_coverage |
| picture_frame | 108 | 57 | 0.965 | 0.270 | common_household_target_with_good_coverage |
| mirror | 831 | 148 | 1.602 | 1.100 | common_household_target_with_good_coverage |
| painting | 183 | 87 | 1.750 | 1.035 | possibly_too_high_origin_y_p75=1.887 |
| lamp | 3076 | 164 | 2.743 | 0.504 | possibly_too_high_origin_y_p75=2.800 |
| shelf | 1174 | 146 | 1.434 | 0.402 | possibly_too_high_origin_y_p75=1.858 |
| clock | 258 | 111 | 1.750 | 0.280 | possibly_too_high_origin_y_p75=2.006; not_in_common_household_target_hint_list |
| showerhead | 73 | 43 | 1.750 | 1.103 | possibly_too_high_origin_y_p75=2.243 |
| towel_rack | 76 | 41 | 0.954 | 0.628 | common_household_target_with_good_coverage |
| shower_tap | 41 | 21 | 1.444 | 1.218 | common_household_target_with_good_coverage |
| toilet_paper | 112 | 52 | 0.670 | 0.174 | common_household_target_with_good_coverage |
| tablet | 26 | 18 | 0.750 | 0.087 | common_household_target_with_good_coverage |
| tissue_box | 27 | 17 | 0.760 | 0.214 | common_household_target_with_good_coverage |
| desk_clutter | 26 | 13 | 0.760 | 0.136 | common_household_target_with_good_coverage |


Categories marked reject should not be used until manually reviewed or relabeled.

## Output Files

- JSON: `ovon_hssd_audit\outputs\hssd_category_expansion_inventory.json`
- Markdown: `ovon_hssd_audit\outputs\hssd_category_expansion_inventory.md`
