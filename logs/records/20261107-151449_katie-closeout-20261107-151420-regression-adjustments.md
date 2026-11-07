# Run Record: katie-closeout-20261107-151420-regression-adjustments

- Timestamp: 20261107-151449
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-environment-SD/work/katie-closeout-release-99b52e4c8f0b`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261107-151449_katie-closeout-20261107-151420-regression-adjustments.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.

## Command

```bash
/ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python -m unittest discover -s tests -p test_fevs_imaging_adjustments.py -v
```

## Full Log

```text
RUN START: 20261107-151449
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-environment-SD/work/katie-closeout-release-99b52e4c8f0b
COMMAND: /ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python -m unittest discover -s tests -p test_fevs_imaging_adjustments.py -v

test_archived_inputs_not_stale_live_checkout_and_full_native_resume (test_fevs_imaging_adjustments.ImagingAdjustments.test_archived_inputs_not_stale_live_checkout_and_full_native_resume) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 90/90 unique files
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
SMOKE activation_fevs/adi/z-2p6
SMOKE vs_fevs_pm25/adi/z-2p6
STARTED activation_fevs/adi_ecog/z-2p6STARTED activation_fevs/ecog/z-2p6STARTED activation_fevs/adi/z-2p6


STARTED activation_fevs/adi/z-3p1
COMPLETED activation_fevs/adi/z-3p1
COMPLETED activation_fevs/adi/z-2p6
STARTED activation_fevs/ecog/z-3p1
COMPLETED activation_fevs/adi_ecog/z-2p6
COMPLETED activation_fevs/ecog/z-2p6
STARTED activation_fevs/adi_ecog/z-3p1
STARTED activation_fevs_pm25/adi/z-2p6
STARTED activation_fevs_pm25/ecog/z-2p6
COMPLETED activation_fevs/adi_ecog/z-3p1
COMPLETED activation_fevs/ecog/z-3p1
STARTED activation_fevs_pm25/adi/z-3p1
STARTED activation_fevs_pm25/adi_ecog/z-2p6
STARTED activation_fevs_pm25/ecog/z-3p1
STARTED activation_fevs_pm25/adi_ecog/z-3p1
COMPLETED activation_fevs_pm25/ecog/z-2p6
COMPLETED activation_fevs_pm25/adi/z-2p6
COMPLETED activation_fevs_pm25/adi_ecog/z-2p6
COMPLETED activation_fevs_pm25/ecog/z-3p1
STARTED vs_fevs_pm25/adi/z-2p6
STARTED vs_fevs_pm25/adi/z-3p1
STARTED vs_fevs_pm25/ecog/z-2p6
STARTED vs_fevs_pm25/adi_ecog/z-2p6
COMPLETED activation_fevs_pm25/adi_ecog/z-3p1
COMPLETED activation_fevs_pm25/adi/z-3p1
COMPLETED vs_fevs_pm25/adi/z-2p6
COMPLETED vs_fevs_pm25/ecog/z-2p6
COMPLETED vs_fevs_pm25/adi_ecog/z-2p6
COMPLETED vs_fevs_pm25/adi/z-3p1
STARTED vs_fevs_pm25/ecog/z-3p1
STARTED vs_fevs_pm25/adi_ecog/z-3p1
COMPLETED vs_fevs_pm25/ecog/z-3p1
COMPLETED vs_fevs_pm25/adi_ecog/z-3p1
RESULT activation_fevs +baseline Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +baseline Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +baseline Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +baseline Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +baseline Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +baseline Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +baseline Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +baseline Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +baseline Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +baseline Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +baseline Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +baseline Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +adi Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +adi Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +adi Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +adi Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +adi_ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi_ecog Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +ecog Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +ecog Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +ecog Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +ecog Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi_ecog Z=3.1 negative p=1 voxels=0
CHECK PASSED: 18/18 adjustment jobs and all 48 baseline/adjusted FEVS maps verified; original results unchanged.
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
REUSED activation_fevs/adi/z-3p1
REUSED activation_fevs/ecog/z-2p6
REUSED activation_fevs/adi_ecog/z-2p6
REUSED activation_fevs/adi/z-2p6
REUSED activation_fevs/ecog/z-3p1
REUSED activation_fevs/adi_ecog/z-3p1
REUSED activation_fevs_pm25/ecog/z-2p6
REUSED activation_fevs_pm25/adi/z-2p6
REUSED activation_fevs_pm25/adi/z-3p1
REUSED activation_fevs_pm25/adi_ecog/z-2p6
REUSED activation_fevs_pm25/ecog/z-3p1
REUSED activation_fevs_pm25/adi_ecog/z-3p1
REUSED vs_fevs_pm25/adi/z-2p6
REUSED vs_fevs_pm25/adi_ecog/z-2p6
REUSED vs_fevs_pm25/ecog/z-2p6
REUSED vs_fevs_pm25/adi/z-3p1
REUSED vs_fevs_pm25/ecog/z-3p1
REUSED vs_fevs_pm25/adi_ecog/z-3p1
RESULT activation_fevs +baseline Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +baseline Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +baseline Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +baseline Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +baseline Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +baseline Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +baseline Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +baseline Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +baseline Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +baseline Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +baseline Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +baseline Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +adi Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +adi Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs +adi Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +adi Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs +adi_ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +ecog Z=3.1 negative p=1 voxels=0
RESULT activation_fevs_pm25 +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT activation_fevs_pm25 +adi_ecog Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +ecog Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +ecog Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi_ecog Z=2.6 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi_ecog Z=2.6 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +ecog Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +ecog Z=3.1 negative p=1 voxels=0
RESULT vs_fevs_pm25 +adi_ecog Z=3.1 positive p=0.04 voxels=8
RESULT vs_fevs_pm25 +adi_ecog Z=3.1 negative p=1 voxels=0
CHECK PASSED: 18/18 adjustment jobs and all 48 baseline/adjusted FEVS maps verified; original results unchanged.
ok
test_baseline_score_or_conditional_interaction_mismatch_stops (test_fevs_imaging_adjustments.ImagingAdjustments.test_baseline_score_or_conditional_interaction_mismatch_stops) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_catalog_preserves_base_columns_and_adds_only_centered_adjustments (test_fevs_imaging_adjustments.ImagingAdjustments.test_catalog_preserves_base_columns_and_adds_only_centered_adjustments) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_changed_adjustment_design_is_not_replaced (test_fevs_imaging_adjustments.ImagingAdjustments.test_changed_adjustment_design_is_not_replaced) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 90/90 unique files
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
ok
test_changed_input_design_or_mask_refuses_resume (test_fevs_imaging_adjustments.ImagingAdjustments.test_changed_input_design_or_mask_refuses_resume) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 90/90 unique files
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
ok
test_completed_native_command_and_missing_products_stop (test_fevs_imaging_adjustments.ImagingAdjustments.test_completed_native_command_and_missing_products_stop) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_failed_v1_plan_is_untouched (test_fevs_imaging_adjustments.ImagingAdjustments.test_failed_v1_plan_is_untouched) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 90/90 unique files
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
ok
test_incorrect_recorded_size_is_not_replaced (test_fevs_imaging_adjustments.ImagingAdjustments.test_incorrect_recorded_size_is_not_replaced) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH FAILURE Frozen source/result changed: /tmp/tmpxdb2amdw/old-live-checkout/derivatives/fsl/randomise/katie-main-effects-v1/plan.json
HASH AUDIT 1/1 unique files
ok
test_live_orphan_refuses_duplicate_execution (test_fevs_imaging_adjustments.ImagingAdjustments.test_live_orphan_refuses_duplicate_execution) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 90/90 unique files
CHECK PASSED: matched N=97, unchanged images/masks/order and baseline columns; 18 additive adjustment jobs, both FEVS directions, model-specific Z-to-t CDTs. Scoring provisional; exclusions unchanged.
ok
test_missing_baseline_product_stops_before_any_new_job (test_fevs_imaging_adjustments.ImagingAdjustments.test_missing_baseline_product_stops_before_any_new_job) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_optional_size_normalization_keeps_hash_and_rejects_real_changes (test_fevs_imaging_adjustments.ImagingAdjustments.test_optional_size_normalization_keeps_hash_and_rejects_real_changes) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
HASH AUDIT 1/1 unique files
HASH FAILURE Frozen source/result changed: /tmp/tmp1anhiqq5/old-live-checkout/derivatives/fsl/randomise/katie-main-effects-v1/plan.json
HASH AUDIT 1/1 unique files
ok
test_rank_deficiency_and_unauthorized_interactions_stop (test_fevs_imaging_adjustments.ImagingAdjustments.test_rank_deficiency_and_unauthorized_interactions_stop) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_unrecognized_output_is_not_overwritten (test_fevs_imaging_adjustments.ImagingAdjustments.test_unrecognized_output_is_not_overwritten) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok
test_wrong_order_duplicates_and_nonfinite_adjustment_stop (test_fevs_imaging_adjustments.ImagingAdjustments.test_wrong_order_duplicates_and_nonfinite_adjustment_stop) ... STARTED activation/win_only/fevs/z-2p6
STARTED activation/win_only/fevs/z-3p1
STARTED activation/win_only/fevsxpm25/z-2p6
STARTED activation/win_only/fevsxpm25/z-3p1
STARTED connectivity/social_specific/fevsxpm25/z-2p6
STARTED connectivity/social_specific/fevsxpm25/z-3p1
ok

----------------------------------------------------------------------
Ran 14 tests in 26.232s

OK

COMMAND EXIT: 0
```
