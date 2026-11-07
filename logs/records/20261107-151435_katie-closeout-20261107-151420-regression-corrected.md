# Run Record: katie-closeout-20261107-151420-regression-corrected

- Timestamp: 20261107-151435
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-environment-SD/work/katie-closeout-release-99b52e4c8f0b`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261107-151435_katie-closeout-20261107-151420-regression-corrected.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: corrected screener MSPSS only; N=97, image/mask/order and all other columns unchanged; 64 jobs / 384 signed tests, activation and VS-PPI, all four contrasts; exclusions unchanged.

## Command

```bash
/ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python -m unittest discover -s tests -p test_corrected_mspss.py -v
```

## Full Log

```text
RUN START: 20261107-151435
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-environment-SD/work/katie-closeout-release-99b52e4c8f0b
COMMAND: /ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python -m unittest discover -s tests -p test_corrected_mspss.py -v

test_changed_original_plan_and_unknown_output_fail_closed (test_corrected_mspss.CorrectedMSPSS.test_changed_original_plan_and_unknown_output_fail_closed) ... ok
test_duplicate_coverage_wrong_matrix_and_row_order_fail (test_corrected_mspss.CorrectedMSPSS.test_duplicate_coverage_wrong_matrix_and_row_order_fail) ... ok
test_exact_scope_retained_models_and_only_mspss_columns_change (test_corrected_mspss.CorrectedMSPSS.test_exact_scope_retained_models_and_only_mspss_columns_change) ... ok
test_launcher_bounds_syntax_and_single_thread_configuration (test_corrected_mspss.CorrectedMSPSS.test_launcher_bounds_syntax_and_single_thread_configuration) ... ok
test_native_run_resume_and_frozen_release_not_live_data (test_corrected_mspss.CorrectedMSPSS.test_native_run_resume_and_frozen_release_not_live_data) ... HASH AUDIT 100/119 unique files
HASH AUDIT 119/119 unique files
CHECK PASSED: corrected screener MSPSS only; N=97, image/mask/order and all other columns unchanged; 64 jobs / 384 signed tests, activation and VS-PPI, all four contrasts; exclusions unchanged.
SMOKE activation/social_specific/adixmspss/z-2p6
SMOKE connectivity/social_specific/adixmspss/z-2p6
STARTED activation/social_specific/fevsxmspss/z-3p1
STARTED activation/social_specific/pm25xmspss/z-2p6
STARTED activation/social_specific/pm25xmspss/z-3p1
STARTED activation/social_specific/adixmspss/z-2p6
STARTED activation/social_specific/adixmspss/z-3p1STARTED activation/social_specific/fevsxmspss/z-2p6
STARTED activation/social_specific/oafemxmspss/z-3p1

STARTED activation/social_specific/oafemxmspss/z-2p6
COMPLETED activation/social_specific/fevsxmspss/z-2p6 (1/64)
COMPLETED activation/social_specific/pm25xmspss/z-2p6 (2/64)
COMPLETED activation/social_specific/adixmspss/z-2p6 (3/64)
COMPLETED activation/social_specific/oafemxmspss/z-2p6 (4/64)
STARTED activation/average/adixmspss/z-2p6
STARTED activation/average/adixmspss/z-3p1
STARTED activation/average/pm25xmspss/z-3p1
STARTED activation/average/pm25xmspss/z-2p6
STARTED activation/average/fevsxmspss/z-2p6
STARTED activation/average/fevsxmspss/z-3p1
STARTED activation/average/oafemxmspss/z-2p6
STARTED activation/average/oafemxmspss/z-3p1
COMPLETED activation/social_specific/fevsxmspss/z-3p1 (5/64)
COMPLETED activation/social_specific/adixmspss/z-3p1 (6/64)
COMPLETED activation/social_specific/oafemxmspss/z-3p1 (7/64)
COMPLETED activation/social_specific/pm25xmspss/z-3p1 (8/64)
COMPLETED activation/average/pm25xmspss/z-2p6 (9/64)
STARTED activation/win_only/adixmspss/z-2p6
COMPLETED activation/average/oafemxmspss/z-2p6 (10/64)
STARTED activation/win_only/adixmspss/z-3p1
COMPLETED activation/average/pm25xmspss/z-3p1 (11/64)
COMPLETED activation/average/adixmspss/z-2p6 (12/64)
STARTED activation/win_only/pm25xmspss/z-2p6
COMPLETED activation/average/adixmspss/z-3p1 (13/64)
STARTED activation/win_only/pm25xmspss/z-3p1
COMPLETED activation/average/oafemxmspss/z-3p1 (14/64)
STARTED activation/win_only/fevsxmspss/z-3p1
STARTED activation/win_only/fevsxmspss/z-2p6
COMPLETED activation/average/fevsxmspss/z-2p6 (15/64)
STARTED activation/win_only/oafemxmspss/z-2p6
COMPLETED activation/average/fevsxmspss/z-3p1 (16/64)
STARTED activation/win_only/oafemxmspss/z-3p1
COMPLETED activation/win_only/adixmspss/z-2p6 (17/64)
STARTED activation/loss_only/adixmspss/z-2p6
COMPLETED activation/win_only/adixmspss/z-3p1 (18/64)
COMPLETED activation/win_only/oafemxmspss/z-3p1 (19/64)
STARTED activation/loss_only/adixmspss/z-3p1
COMPLETED activation/win_only/oafemxmspss/z-2p6 (20/64)
STARTED activation/loss_only/pm25xmspss/z-2p6
COMPLETED activation/win_only/pm25xmspss/z-2p6 (21/64)
COMPLETED activation/win_only/fevsxmspss/z-3p1 (22/64)
STARTED activation/loss_only/pm25xmspss/z-3p1
STARTED activation/loss_only/fevsxmspss/z-3p1
STARTED activation/loss_only/fevsxmspss/z-2p6
COMPLETED activation/win_only/fevsxmspss/z-2p6 (23/64)
COMPLETED activation/win_only/pm25xmspss/z-3p1 (24/64)
STARTED activation/loss_only/oafemxmspss/z-2p6
STARTED activation/loss_only/oafemxmspss/z-3p1
COMPLETED activation/loss_only/adixmspss/z-2p6 (25/64)
STARTED connectivity/social_specific/adixmspss/z-2p6
COMPLETED activation/loss_only/pm25xmspss/z-3p1 (26/64)
STARTED connectivity/social_specific/adixmspss/z-3p1
COMPLETED activation/loss_only/adixmspss/z-3p1 (27/64)
COMPLETED activation/loss_only/fevsxmspss/z-2p6 (28/64)
STARTED connectivity/social_specific/pm25xmspss/z-2p6
STARTED connectivity/social_specific/pm25xmspss/z-3p1
COMPLETED activation/loss_only/fevsxmspss/z-3p1 (29/64)
COMPLETED activation/loss_only/pm25xmspss/z-2p6 (30/64)
STARTED connectivity/social_specific/fevsxmspss/z-2p6
STARTED connectivity/social_specific/fevsxmspss/z-3p1COMPLETED activation/loss_only/oafemxmspss/z-2p6 (31/64)

STARTED connectivity/social_specific/oafemxmspss/z-2p6
COMPLETED activation/loss_only/oafemxmspss/z-3p1 (32/64)
STARTED connectivity/social_specific/oafemxmspss/z-3p1
COMPLETED connectivity/social_specific/adixmspss/z-2p6 (33/64)
STARTED connectivity/average/adixmspss/z-2p6
COMPLETED connectivity/social_specific/adixmspss/z-3p1 (34/64)
STARTED connectivity/average/adixmspss/z-3p1
COMPLETED connectivity/social_specific/pm25xmspss/z-2p6 (35/64)
STARTED connectivity/average/pm25xmspss/z-2p6
COMPLETED connectivity/social_specific/pm25xmspss/z-3p1 (36/64)
COMPLETED connectivity/social_specific/oafemxmspss/z-2p6 (37/64)
STARTED connectivity/average/pm25xmspss/z-3p1
COMPLETED connectivity/social_specific/fevsxmspss/z-3p1 (38/64)
STARTED connectivity/average/fevsxmspss/z-2p6
COMPLETED connectivity/social_specific/fevsxmspss/z-2p6 (39/64)
STARTED connectivity/average/fevsxmspss/z-3p1
COMPLETED connectivity/social_specific/oafemxmspss/z-3p1 (40/64)
STARTED connectivity/average/oafemxmspss/z-2p6
STARTED connectivity/average/oafemxmspss/z-3p1
COMPLETED connectivity/average/adixmspss/z-2p6 (41/64)
STARTED connectivity/win_only/adixmspss/z-2p6
COMPLETED connectivity/average/adixmspss/z-3p1 (42/64)
STARTED connectivity/win_only/adixmspss/z-3p1
COMPLETED connectivity/average/oafemxmspss/z-2p6 (43/64)
COMPLETED connectivity/average/pm25xmspss/z-2p6 (44/64)
STARTED connectivity/win_only/pm25xmspss/z-2p6
STARTED connectivity/win_only/pm25xmspss/z-3p1
COMPLETED connectivity/average/fevsxmspss/z-3p1 (45/64)
COMPLETED connectivity/average/fevsxmspss/z-2p6 (46/64)
COMPLETED connectivity/average/pm25xmspss/z-3p1 (47/64)
STARTED connectivity/win_only/fevsxmspss/z-2p6
STARTED connectivity/win_only/fevsxmspss/z-3p1
STARTED connectivity/win_only/oafemxmspss/z-2p6
COMPLETED connectivity/average/oafemxmspss/z-3p1 (48/64)
STARTED connectivity/win_only/oafemxmspss/z-3p1
COMPLETED connectivity/win_only/adixmspss/z-2p6 (49/64)
STARTED connectivity/loss_only/adixmspss/z-2p6
COMPLETED connectivity/win_only/adixmspss/z-3p1 (50/64)
STARTED connectivity/loss_only/adixmspss/z-3p1
COMPLETED connectivity/win_only/pm25xmspss/z-2p6 (51/64)
STARTED connectivity/loss_only/pm25xmspss/z-2p6
COMPLETED connectivity/win_only/pm25xmspss/z-3p1 (52/64)
COMPLETED connectivity/win_only/oafemxmspss/z-2p6 (53/64)
COMPLETED connectivity/win_only/fevsxmspss/z-2p6 (54/64)
STARTED connectivity/loss_only/pm25xmspss/z-3p1
STARTED connectivity/loss_only/fevsxmspss/z-3p1
STARTED connectivity/loss_only/fevsxmspss/z-2p6
COMPLETED connectivity/win_only/fevsxmspss/z-3p1 (55/64)
STARTED connectivity/loss_only/oafemxmspss/z-2p6
COMPLETED connectivity/win_only/oafemxmspss/z-3p1 (56/64)
STARTED connectivity/loss_only/oafemxmspss/z-3p1
COMPLETED connectivity/loss_only/adixmspss/z-2p6 (57/64)
COMPLETED connectivity/loss_only/adixmspss/z-3p1 (58/64)
COMPLETED connectivity/loss_only/pm25xmspss/z-2p6 (59/64)
COMPLETED connectivity/loss_only/pm25xmspss/z-3p1 (60/64)
COMPLETED connectivity/loss_only/fevsxmspss/z-3p1 (61/64)
COMPLETED connectivity/loss_only/oafemxmspss/z-2p6 (62/64)
COMPLETED connectivity/loss_only/fevsxmspss/z-2p6 (63/64)
COMPLETED connectivity/loss_only/oafemxmspss/z-3p1 (64/64)
CHECK PASSED: 64/64 corrected-MSPSS jobs, all 384 directional maps; original outputs unchanged.
CHECK PASSED: corrected screener MSPSS only; N=97, image/mask/order and all other columns unchanged; 64 jobs / 384 signed tests, activation and VS-PPI, all four contrasts; exclusions unchanged.
CHECK PASSED: corrected screener MSPSS only; N=97, image/mask/order and all other columns unchanged; 64 jobs / 384 signed tests, activation and VS-PPI, all four contrasts; exclusions unchanged.
REUSED activation/social_specific/adixmspss/z-3p1 (1/64)
REUSED activation/social_specific/adixmspss/z-2p6 (2/64)
REUSED activation/social_specific/pm25xmspss/z-3p1 (3/64)
REUSED activation/social_specific/fevsxmspss/z-2p6 (4/64)
REUSED activation/social_specific/oafemxmspss/z-2p6 (5/64)
REUSED activation/social_specific/oafemxmspss/z-3p1 (6/64)
REUSED activation/social_specific/pm25xmspss/z-2p6 (7/64)
REUSED activation/social_specific/fevsxmspss/z-3p1 (8/64)
REUSED activation/average/adixmspss/z-3p1 (9/64)
REUSED activation/average/oafemxmspss/z-2p6 (10/64)
REUSED activation/average/adixmspss/z-2p6 (11/64)
REUSED activation/average/pm25xmspss/z-2p6 (12/64)
REUSED activation/average/fevsxmspss/z-3p1 (13/64)
REUSED activation/average/pm25xmspss/z-3p1 (14/64)
REUSED activation/average/fevsxmspss/z-2p6 (15/64)
REUSED activation/average/oafemxmspss/z-3p1 (16/64)
REUSED activation/win_only/pm25xmspss/z-2p6 (17/64)
REUSED activation/win_only/oafemxmspss/z-2p6 (18/64)
REUSED activation/win_only/adixmspss/z-3p1 (19/64)
REUSED activation/win_only/pm25xmspss/z-3p1 (20/64)
REUSED activation/win_only/fevsxmspss/z-3p1 (21/64)
REUSED activation/win_only/adixmspss/z-2p6 (22/64)
REUSED activation/win_only/fevsxmspss/z-2p6 (23/64)
REUSED activation/win_only/oafemxmspss/z-3p1 (24/64)
REUSED activation/loss_only/adixmspss/z-2p6 (25/64)
REUSED activation/loss_only/fevsxmspss/z-3p1 (26/64)
REUSED activation/loss_only/pm25xmspss/z-2p6 (27/64)
REUSED activation/loss_only/fevsxmspss/z-2p6 (28/64)
REUSED activation/loss_only/oafemxmspss/z-2p6 (29/64)
REUSED activation/loss_only/adixmspss/z-3p1 (30/64)
REUSED activation/loss_only/pm25xmspss/z-3p1 (31/64)
REUSED activation/loss_only/oafemxmspss/z-3p1 (32/64)
REUSED connectivity/social_specific/adixmspss/z-3p1 (33/64)
REUSED connectivity/social_specific/pm25xmspss/z-3p1 (34/64)
REUSED connectivity/social_specific/adixmspss/z-2p6 (35/64)
REUSED connectivity/social_specific/fevsxmspss/z-2p6 (36/64)
REUSED connectivity/social_specific/pm25xmspss/z-2p6 (37/64)
REUSED connectivity/social_specific/oafemxmspss/z-2p6 (38/64)
REUSED connectivity/social_specific/fevsxmspss/z-3p1 (39/64)
REUSED connectivity/social_specific/oafemxmspss/z-3p1 (40/64)
REUSED connectivity/average/adixmspss/z-2p6 (41/64)
REUSED connectivity/average/adixmspss/z-3p1 (42/64)
REUSED connectivity/average/pm25xmspss/z-2p6 (43/64)
REUSED connectivity/average/fevsxmspss/z-3p1 (44/64)
REUSED connectivity/average/fevsxmspss/z-2p6 (45/64)
REUSED connectivity/average/pm25xmspss/z-3p1 (46/64)
REUSED connectivity/average/oafemxmspss/z-2p6 (47/64)
REUSED connectivity/average/oafemxmspss/z-3p1 (48/64)
REUSED connectivity/win_only/adixmspss/z-2p6 (49/64)
REUSED connectivity/win_only/adixmspss/z-3p1 (50/64)
REUSED connectivity/win_only/pm25xmspss/z-2p6 (51/64)
REUSED connectivity/win_only/fevsxmspss/z-2p6 (52/64)
REUSED connectivity/win_only/pm25xmspss/z-3p1 (53/64)
REUSED connectivity/win_only/fevsxmspss/z-3p1 (54/64)
REUSED connectivity/loss_only/adixmspss/z-2p6 (55/64)
REUSED connectivity/win_only/oafemxmspss/z-2p6 (56/64)
REUSED connectivity/win_only/oafemxmspss/z-3p1 (57/64)
REUSED connectivity/loss_only/adixmspss/z-3p1 (58/64)
REUSED connectivity/loss_only/pm25xmspss/z-2p6 (59/64)
REUSED connectivity/loss_only/fevsxmspss/z-2p6 (60/64)
REUSED connectivity/loss_only/pm25xmspss/z-3p1 (61/64)
REUSED connectivity/loss_only/fevsxmspss/z-3p1 (62/64)
REUSED connectivity/loss_only/oafemxmspss/z-2p6 (63/64)
REUSED connectivity/loss_only/oafemxmspss/z-3p1 (64/64)
CHECK PASSED: 64/64 corrected-MSPSS jobs, all 384 directional maps; original outputs unchanged.
ok
test_source_and_design_tampering_stop_without_overwrite (test_corrected_mspss.CorrectedMSPSS.test_source_and_design_tampering_stop_without_overwrite) ... HASH AUDIT 100/119 unique files
HASH AUDIT 119/119 unique files
CHECK PASSED: corrected screener MSPSS only; N=97, image/mask/order and all other columns unchanged; 64 jobs / 384 signed tests, activation and VS-PPI, all four contrasts; exclusions unchanged.
ok
test_source_provenance_order_range_and_legacy_hash_not_adopted (test_corrected_mspss.CorrectedMSPSS.test_source_provenance_order_range_and_legacy_hash_not_adopted) ... HASH FAILURE Frozen source/result changed: /tmp/tmpv2uy8t7_/legacy.json
HASH AUDIT 100/119 unique files
HASH AUDIT 119/119 unique files
ok

----------------------------------------------------------------------
Ran 7 tests in 12.253s

OK

COMMAND EXIT: 0
```
