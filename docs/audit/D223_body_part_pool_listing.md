# D223 — Body Part Pool Listing (gym_full, warmup+test excluded)

Generated for Phase 0.4 of B224. Scope: 9 body parts with `main < 3` in `gym_full` scenario.

Ordering: main → accessory → activation → prehab → other; alphabetical within each role group.

## forearms  main=0  accessory=0  activation=0  prehab=9  other=3  (totale=12)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `elbow_eccentric_curl` | ['prehab'] | ['prehab_elbow'] | forearm_supination | [] | ['weight', 'resistance_band'] |
| `elbow_wrist_extensor_eccentric` | ['prehab'] | ['prehab_elbow'] | wrist_extension | ['dumbbell'] | [] |
| `finger_extensor_band` | ['prehab'] | ['prehab_finger'] | finger_extension | [] | [] |
| `finger_extensor_training` | ['prehab'] | ['prehab_wrist'] | wrist_extension | [] | [] |
| `finger_tendon_glides` | ['prehab'] | ['prehab_finger'] | tendon_glide | [] | [] |
| `forearm_pronation_supination` | ['prehab'] | ['prehab_elbow'] | forearm_pronation | [] | [] |
| `pronator_terres_isometric_hold` | ['prehab'] | ['prehab_elbow'] | forearm_pronation | ['resistance_band'] | [] |
| `reverse_wrist_curl` | ['prehab'] | ['prehab_wrist'] | wrist_extension | ['weight'] | [] |
| `wrist_curl` | ['prehab'] | ['prehab_wrist'] | wrist_flexion | ['weight'] | [] |
| `cooldown_forearm_wrist_stretch` | ['cooldown'] | ['prehab_wrist', 'flexibility'] | flexibility_passive | [] | [] |
| `farmers_carry` | ['conditioning'] | ['strength_general', 'core'] | carry | [] | ['dumbbell', 'barbell', 'kettlebell'] |
| `forearm_stretches` | ['cooldown'] | ['prehab_wrist', 'flexibility'] | wrist_extension | [] | [] |

## biceps  main=0  accessory=2  activation=0  prehab=0  other=0  (totale=2)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `bicep_curl` | ['accessory'] | ['strength_general'] | elbow_flexion | ['dumbbell'] | [] |
| `chinup` | ['accessory'] | ['strength_general'] | pull_vertical | ['pullup_bar'] | [] |

## triceps  main=1  accessory=6  activation=0  prehab=0  other=0  (totale=7)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `dip` | ['main'] | ['strength_general'] | push | [] | [] |
| `bench_press` | ['accessory'] | ['strength_general'] | push | ['weight'] | [] |
| `handstand_pushup_wall` | ['accessory'] | ['strength_general', 'handstand_skill'] | push | [] | [] |
| `overhead_press` | ['accessory'] | ['strength_general'] | push | ['weight'] | [] |
| `overhead_tricep_extension` | ['accessory'] | ['strength_general'] | push | ['dumbbell'] | [] |
| `pike_pushup` | ['accessory'] | ['strength_general'] | push | [] | [] |
| `ring_pushup` | ['accessory'] | ['strength_general'] | push | ['rings'] | [] |

## chest  main=1  accessory=9  activation=0  prehab=0  other=0  (totale=10)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `dip` | ['main'] | ['strength_general'] | push | [] | [] |
| `bench_press` | ['accessory'] | ['strength_general'] | push | ['weight'] | [] |
| `dumbbell_bench_press` | ['accessory'] | ['strength_general'] | push | ['dumbbell'] | [] |
| `dumbbell_fly` | ['accessory'] | ['strength_general'] | push | ['dumbbell'] | [] |
| `handstand_pushup_wall` | ['accessory'] | ['strength_general', 'handstand_skill'] | push | [] | [] |
| `incline_pushup` | ['accessory'] | ['strength_general'] | push | [] | [] |
| `overhead_press` | ['accessory'] | ['strength_general'] | push | ['weight'] | [] |
| `pike_pushup` | ['accessory'] | ['strength_general'] | push | [] | [] |
| `pushup` | ['accessory'] | ['strength_general'] | push | [] | [] |
| `ring_pushup` | ['accessory'] | ['strength_general'] | push | ['rings'] | [] |

## shoulders  main=0  accessory=9  activation=0  prehab=1  other=0  (totale=10)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `face_pull` | ['accessory', 'prehab'] | ['prehab_shoulder'] | scapular_control | ['resistance_band'] | [] |
| `freestanding_handstand_practice` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `handstand_pushup_wall` | ['accessory'] | ['strength_general', 'handstand_skill'] | push | [] | [] |
| `handstand_shoulder_taps` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `lateral_raise` | ['accessory'] | ['strength_general'] | shoulder_isolation | ['dumbbell'] | [] |
| `overhead_press` | ['accessory'] | ['strength_general'] | push | ['weight'] | [] |
| `scapular_pullup` | ['accessory', 'prehab', 'activation'] | ['strength_general', 'prehab_shoulder'] | scapular_control | ['pullup_bar'] | [] |
| `wall_handstand_hold` | ['accessory'] | ['handstand_skill', 'strength_general'] | handstand | [] | [] |
| `wall_walk_up` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `band_external_rotation` | ['prehab'] | ['prehab_shoulder'] | rotation | ['resistance_band'] | [] |

## core  main=2  accessory=25  activation=0  prehab=0  other=1  (totale=28)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `front_lever_tuck` | ['main'] | ['core'] | anti_extension | ['pullup_bar'] | [] |
| `l_sit_pullup` | ['main'] | ['strength_general', 'core'] | pull_vertical | ['pullup_bar'] | [] |
| `ab_wheel_rollout` | ['accessory'] | ['core'] | anti_extension | [] | [] |
| `copenhagen_adductor_plank` | ['accessory'] | ['strength_general'] | anti_lateral_flexion | [] | [] |
| `copenhagen_plank` | ['accessory'] | ['core'] | anti_rotation | [] | [] |
| `core_hollow_hold` | ['accessory'] | ['core'] | anti_extension | [] | [] |
| `core_l_sit` | ['accessory'] | ['core'] | anti_extension | [] | [] |
| `freestanding_handstand_practice` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `front_lever_one_leg` | ['accessory'] | ['core'] | isometric_hold | ['pullup_bar'] | [] |
| `front_lever_straddle` | ['accessory'] | ['core'] | isometric_hold | ['pullup_bar'] | [] |
| `handstand_pushup_wall` | ['accessory'] | ['strength_general', 'handstand_skill'] | push | [] | [] |
| `handstand_shoulder_taps` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `hanging_leg_raise` | ['accessory'] | ['core'] | compression | ['pullup_bar'] | [] |
| `hip_flexor_strengthening` | ['accessory'] | ['strength_general'] | compression | [] | [] |
| `knees_to_elbows` | ['accessory'] | ['core'] | compression | ['pullup_bar'] | [] |
| `pallof_press` | ['accessory'] | ['core'] | anti_rotation | ['resistance_band'] | [] |
| `plank` | ['accessory'] | ['core'] | anti_extension | [] | [] |
| `plank_shoulder_tap` | ['accessory'] | ['core'] | anti_rotation | [] | [] |
| `seated_leg_raise_hip_flexor` | ['accessory'] | ['strength_general'] | compression | [] | [] |
| `side_plank` | ['accessory'] | ['core'] | anti_lateral_flexion | [] | [] |
| `suitcase_carry` | ['accessory'] | ['core'] | anti_lateral_flexion | [] | ['dumbbell', 'kettlebell'] |
| `toes_to_bar` | ['accessory'] | ['core'] | compression | ['pullup_bar'] | [] |
| `turkish_getup` | ['accessory'] | ['strength_general', 'core'] | rotation | [] | ['dumbbell', 'barbell', 'kettlebell'] |
| `v_up` | ['accessory'] | ['core'] | compression | [] | [] |
| `wall_handstand_hold` | ['accessory'] | ['handstand_skill', 'strength_general'] | handstand | [] | [] |
| `wall_walk_up` | ['accessory'] | ['handstand_skill'] | handstand | [] | [] |
| `windshield_wipers` | ['accessory'] | ['core'] | rotation | ['pullup_bar'] | [] |
| `farmers_carry` | ['conditioning'] | ['strength_general', 'core'] | carry | [] | ['dumbbell', 'barbell', 'kettlebell'] |

## glutes  main=0  accessory=8  activation=0  prehab=0  other=0  (totale=8)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `glute_bridge` | ['accessory'] | ['strength_general'] | hinge | [] | [] |
| `nordic_curl` | ['accessory', 'prehab'] | ['strength_general'] | hinge | [] | [] |
| `pistol_squat_progression` | ['accessory'] | ['strength_general'] | squat | [] | [] |
| `reverse_lunge` | ['accessory'] | ['strength_general'] | lunge | [] | [] |
| `romanian_deadlift` | ['accessory'] | ['strength_general'] | hinge | ['weight'] | [] |
| `single_leg_glute_bridge` | ['accessory'] | ['strength_general'] | hinge | [] | [] |
| `single_leg_rdl` | ['accessory'] | ['strength_general'] | hinge | [] | [] |
| `split_squat` | ['accessory'] | ['strength_general'] | squat | ['weight'] | [] |

## hips  main=0  accessory=6  activation=0  prehab=0  other=0  (totale=6)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `clamshell` | ['accessory'] | ['strength_general'] | hip_isolation | [] | [] |
| `copenhagen_adductor_plank` | ['accessory'] | ['strength_general'] | anti_lateral_flexion | [] | [] |
| `hip_90_90_switch` | ['accessory'] | ['strength_general'] | rotation | [] | [] |
| `hip_flexor_strengthening` | ['accessory'] | ['strength_general'] | compression | [] | [] |
| `side_lying_hip_abduction` | ['accessory'] | ['strength_general'] | hip_isolation | [] | [] |
| `standing_hip_adduction_band` | ['accessory'] | ['strength_general'] | hip_isolation | ['resistance_band'] | [] |

## legs  main=0  accessory=9  activation=0  prehab=0  other=0  (totale=9)

| exercise_id | role | domain | pattern | equipment_required | equipment_required_any |
|---|---|---|---|---|---|
| `bulgarian_split_squat` | ['accessory'] | ['strength_general'] | lunge | [] | [] |
| `cossack_squat` | ['accessory'] | ['strength_general'] | squat | [] | [] |
| `goblet_squat` | ['accessory'] | ['strength_general'] | squat | ['weight'] | [] |
| `nordic_curl` | ['accessory', 'prehab'] | ['strength_general'] | hinge | [] | [] |
| `pistol_squat_progression` | ['accessory'] | ['strength_general'] | squat | [] | [] |
| `reverse_lunge` | ['accessory'] | ['strength_general'] | lunge | [] | [] |
| `single_leg_calf_raise` | ['accessory'] | ['strength_general'] | calf_raise | [] | [] |
| `split_squat` | ['accessory'] | ['strength_general'] | squat | ['weight'] | [] |
| `step_ups` | ['accessory'] | ['strength_general'] | squat | [] | [] |
