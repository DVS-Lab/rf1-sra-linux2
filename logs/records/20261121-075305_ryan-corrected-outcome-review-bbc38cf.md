# Run Record: ryan-corrected-outcome-review-bbc38cf

- Timestamp: 20261121-075305
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261121-075305_ryan-corrected-outcome-review-bbc38cf.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: 132 corrected jobs, 264 directional maps; directions with surviving voxels: act=11, VS=0. No fits, masks, seeds or exclusions changed.

## Command

```bash
env PYTHONPATH=/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-8kCZ0Xas/code PYTHONUNBUFFERED=1 /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/.venv/bin/python - --state /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1
```

## Full Log

```text
RUN START: 20261121-075305
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial
COMMAND: env PYTHONPATH=/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-8kCZ0Xas/code PYTHONUNBUFFERED=1 /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/.venv/bin/python - --state /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1

Cluster-extent spatial FWE; .025 per direction is the two-direction rule. No correction across models or CDTs. Peak = strongest signed effect among surviving voxels.
modality	outcome	cohort	model	CDT	N	direction	min_cluster_p	vox_p05	vox_p025	peak_MNI	signed_t	cluster_p_at_peak	peak_atlas
act	social_loss_minus_monetary_loss	core	age	z2p6	292	positive	0.633800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core	age	z2p6	292	negative	0.006400	488	488	-28.90,-47.70,-6.66	-6.914	0.006400	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_loss_minus_monetary_loss	core	age	z3p1	292	positive	0.637800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core	age	z3p1	292	negative	0.000800	300	300	-28.90,-47.70,-6.66	-6.914	0.000800	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_loss_minus_monetary_loss	core	depression	z2p6	292	positive	0.676300	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core	depression	z2p6	292	negative	0.500500	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core	depression	z3p1	292	positive	0.876000	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core	depression	z3p1	292	negative	0.275700	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	age	z2p6	199	positive	0.520400	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	age	z2p6	199	negative	0.013800	357	357	-28.90,-47.70,-6.66	-5.842	0.013800	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_loss_minus_monetary_loss	core_plus_ucla	age	z3p1	199	positive	0.252000	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	age	z3p1	199	negative	0.002300	193	193	-28.90,-47.70,-6.66	-5.842	0.002300	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_loss_minus_monetary_loss	core_plus_ucla	depression	z2p6	199	positive	0.488200	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	depression	z2p6	199	negative	0.816100	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	depression	z3p1	199	positive	0.355500	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	depression	z3p1	199	negative	0.944000	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z2p6	199	positive	0.103800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z2p6	199	negative	0.172300	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z3p1	199	positive	0.184300	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z3p1	199	negative	0.117200	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.440100	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.163800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.465800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.101800	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.081300	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.177400	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.073600	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.106100	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.601100	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.822100	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.450000	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.864000	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.033500	129	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.203400	0	0	none	-	-	-
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.024500	43	43	-4.60,54.90,34.92	4.883	0.024500	Cortical: Superior Frontal Gyrus; Subcortical: Left Cerebral Cortex
act	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.189000	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	age	z2p6	292	positive	0.444700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	age	z2p6	292	negative	0.005300	548	548	-28.90,-47.70,-6.66	-6.886	0.006400	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_win_minus_monetary_win	core	age	z3p1	292	positive	0.539000	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	age	z3p1	292	negative	0.000300	412	383	-28.90,-47.70,-6.66	-6.886	0.000300	Cortical: Lingual Gyrus; Subcortical: Left Cerebral Cortex
act	social_win_minus_monetary_win	core	depression	z2p6	292	positive	0.554800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	depression	z2p6	292	negative	0.571700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	depression	z3p1	292	positive	0.764800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core	depression	z3p1	292	negative	0.864500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	age	z2p6	199	positive	0.402000	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	age	z2p6	199	negative	0.008100	461	461	-26.20,-47.70,-9.63	-6.278	0.008400	Cortical: Temporal Occipital Fusiform Cortex; Subcortical: Left Cerebral Cortex
act	social_win_minus_monetary_win	core_plus_ucla	age	z3p1	199	positive	0.618300	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	age	z3p1	199	negative	0.001000	271	271	-26.20,-47.70,-9.63	-6.278	0.001000	Cortical: Temporal Occipital Fusiform Cortex; Subcortical: Left Cerebral Cortex
act	social_win_minus_monetary_win	core_plus_ucla	depression	z2p6	199	positive	0.316300	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	depression	z2p6	199	negative	0.392600	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	depression	z3p1	199	positive	0.355500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	depression	z3p1	199	negative	0.184500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness	z2p6	199	positive	0.310700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness	z2p6	199	negative	0.129700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness	z3p1	199	positive	0.636500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness	z3p1	199	negative	0.159300	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.524800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.492800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.400800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.469500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.251500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.065800	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.735700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.140200	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.387400	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.262100	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.579500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.498500	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.049300	109	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.116700	0	0	none	-	-	-
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.022700	47	47	0.80,44.10,34.92	4.364	0.022700	Cortical: Superior Frontal Gyrus; Subcortical: Left Cerebral Cortex
act	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.138400	0	0	none	-	-	-
act	win_loss_double_subtraction	core	age	z2p6	292	positive	0.238200	0	0	none	-	-	-
act	win_loss_double_subtraction	core	age	z2p6	292	negative	0.400300	0	0	none	-	-	-
act	win_loss_double_subtraction	core	age	z3p1	292	positive	0.248900	0	0	none	-	-	-
act	win_loss_double_subtraction	core	age	z3p1	292	negative	0.383600	0	0	none	-	-	-
act	win_loss_double_subtraction	core	belonging_by_age	z2p6	292	positive	0.550100	0	0	none	-	-	-
act	win_loss_double_subtraction	core	belonging_by_age	z2p6	292	negative	0.388500	0	0	none	-	-	-
act	win_loss_double_subtraction	core	belonging_by_age	z3p1	292	positive	0.482200	0	0	none	-	-	-
act	win_loss_double_subtraction	core	belonging_by_age	z3p1	292	negative	0.403400	0	0	none	-	-	-
act	win_loss_double_subtraction	core	depression	z2p6	292	positive	0.402500	0	0	none	-	-	-
act	win_loss_double_subtraction	core	depression	z2p6	292	negative	0.040700	110	0	none	-	-	-
act	win_loss_double_subtraction	core	depression	z3p1	292	positive	0.673300	0	0	none	-	-	-
act	win_loss_double_subtraction	core	depression	z3p1	292	negative	0.295400	0	0	none	-	-	-
act	win_loss_double_subtraction	core	support_by_depression	z2p6	292	positive	0.933600	0	0	none	-	-	-
act	win_loss_double_subtraction	core	support_by_depression	z2p6	292	negative	0.455500	0	0	none	-	-	-
act	win_loss_double_subtraction	core	support_by_depression	z3p1	292	positive	0.886900	0	0	none	-	-	-
act	win_loss_double_subtraction	core	support_by_depression	z3p1	292	negative	0.795900	0	0	none	-	-	-
act	win_loss_double_subtraction	core	task_mean	z2p6	292	positive	0.033500	114	0	none	-	-	-
act	win_loss_double_subtraction	core	task_mean	z2p6	292	negative	0.130800	0	0	none	-	-	-
act	win_loss_double_subtraction	core	task_mean	z3p1	292	positive	0.023600	37	37	19.70,-90.90,-6.66	4.964	0.023600	Cortical: unlabeled; Subcortical: Right Cerebral Cortex
act	win_loss_double_subtraction	core	task_mean	z3p1	292	negative	0.110700	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	age	z2p6	199	positive	0.399800	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	age	z2p6	199	negative	0.288700	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	age	z3p1	199	positive	0.627200	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	age	z3p1	199	negative	0.627400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z2p6	199	positive	0.451400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z2p6	199	negative	0.686200	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z3p1	199	positive	0.265700	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z3p1	199	negative	0.952900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	depression	z2p6	199	positive	0.359600	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	depression	z2p6	199	negative	0.383100	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	depression	z3p1	199	positive	0.300700	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	depression	z3p1	199	negative	0.533800	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness	z2p6	199	positive	0.830400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness	z2p6	199	negative	0.067400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness	z3p1	199	positive	0.865000	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness	z3p1	199	negative	0.036400	35	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.191100	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.365200	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.465800	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.469700	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.864300	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.072900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.866900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.029800	38	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.660600	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.593600	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.871400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.760000	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.679900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.267400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.744300	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.228400	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z2p6	199	positive	0.667900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z2p6	199	negative	0.898500	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z3p1	199	positive	0.805300	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z3p1	199	negative	0.716100	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	task_mean	z2p6	199	positive	0.400900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	task_mean	z2p6	199	negative	0.333900	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	task_mean	z3p1	199	positive	0.304600	0	0	none	-	-	-
act	win_loss_double_subtraction	core_plus_ucla	task_mean	z3p1	199	negative	0.367500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	age	z2p6	292	positive	0.722300	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	age	z2p6	292	negative	0.464000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	age	z3p1	292	positive	0.387200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	age	z3p1	292	negative	0.484700	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	depression	z2p6	292	positive	0.573900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	depression	z2p6	292	negative	0.529900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	depression	z3p1	292	positive	0.807800	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core	depression	z3p1	292	negative	0.584000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	age	z2p6	199	positive	0.661200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	age	z2p6	199	negative	0.355500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	age	z3p1	199	positive	0.815300	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	age	z3p1	199	negative	0.300300	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	depression	z2p6	199	positive	0.209200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	depression	z2p6	199	negative	0.116500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	depression	z3p1	199	positive	0.094900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	depression	z3p1	199	negative	0.077000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z2p6	199	positive	0.172300	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z2p6	199	negative	0.697900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z3p1	199	positive	0.558500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness	z3p1	199	negative	0.803900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.298900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.788200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.107000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.563800	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.155200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.538400	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.458000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.568800	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.252300	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.683200	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.473900	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.670700	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.462500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.107000	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.668500	0	0	none	-	-	-
VS	social_loss_minus_monetary_loss	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.215800	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	age	z2p6	292	positive	0.460000	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	age	z2p6	292	negative	0.281200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	age	z3p1	292	positive	0.159600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	age	z3p1	292	negative	0.246400	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	depression	z2p6	292	positive	0.911200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	depression	z2p6	292	negative	0.302200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	depression	z3p1	292	positive	0.702800	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core	depression	z3p1	292	negative	0.327900	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	age	z2p6	199	positive	0.218600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	age	z2p6	199	negative	0.397500	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	age	z3p1	199	positive	0.105700	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	age	z3p1	199	negative	0.360100	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	depression	z2p6	199	positive	0.413300	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	depression	z2p6	199	negative	0.283200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	depression	z3p1	199	positive	0.898300	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	depression	z3p1	199	negative	0.320400	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness	z2p6	199	positive	0.186300	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness	z2p6	199	negative	0.437200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness	z3p1	199	positive	0.054700	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness	z3p1	199	negative	0.789700	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.591600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.105600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.660600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.320200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.157900	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.365700	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.040200	24	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.558100	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.117300	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.232600	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.246100	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.229000	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.292500	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.327200	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.308300	0	0	none	-	-	-
VS	social_win_minus_monetary_win	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.454000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	age	z2p6	292	positive	0.772900	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	age	z2p6	292	negative	0.679500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	age	z3p1	292	positive	0.598200	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	age	z3p1	292	negative	0.602800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	belonging_by_age	z2p6	292	positive	0.922100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	belonging_by_age	z2p6	292	negative	0.883400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	belonging_by_age	z3p1	292	positive	0.913900	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	belonging_by_age	z3p1	292	negative	0.909300	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	depression	z2p6	292	positive	0.987800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	depression	z2p6	292	negative	0.382500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	depression	z3p1	292	positive	0.977500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	depression	z3p1	292	negative	0.496400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	support_by_depression	z2p6	292	positive	0.999000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	support_by_depression	z2p6	292	negative	0.684100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	support_by_depression	z3p1	292	positive	1.000000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	support_by_depression	z3p1	292	negative	0.642800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	task_mean	z2p6	292	positive	0.302900	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	task_mean	z2p6	292	negative	0.590900	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	task_mean	z3p1	292	positive	0.473400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core	task_mean	z3p1	292	negative	0.998500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	age	z2p6	199	positive	0.860300	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	age	z2p6	199	negative	0.093700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	age	z3p1	199	positive	0.697600	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	age	z3p1	199	negative	0.462100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z2p6	199	positive	0.278000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z2p6	199	negative	0.177800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z3p1	199	positive	0.332500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	belonging_by_age	z3p1	199	negative	0.046900	26	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	depression	z2p6	199	positive	0.831200	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	depression	z2p6	199	negative	0.059400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	depression	z3p1	199	positive	0.901000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	depression	z3p1	199	negative	0.117400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness	z2p6	199	positive	0.424500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness	z2p6	199	negative	0.763600	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness	z3p1	199	positive	0.679500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness	z3p1	199	negative	0.811600	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z2p6	199	positive	0.518800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z2p6	199	negative	0.165200	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z3p1	199	positive	0.577100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age	z3p1	199	negative	0.176900	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	positive	0.267000	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z2p6	199	negative	0.634800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	positive	0.324400	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_age__ucla	z3p1	199	negative	0.693100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z2p6	199	positive	0.295100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z2p6	199	negative	0.258300	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z3p1	199	positive	0.357700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_depression	z3p1	199	negative	0.579700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	positive	0.548800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z2p6	199	negative	0.668700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	positive	0.565300	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	loneliness_by_support__ucla	z3p1	199	negative	0.396200	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z2p6	199	positive	0.939700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z2p6	199	negative	0.870200	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z3p1	199	positive	0.983500	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	support_by_depression	z3p1	199	negative	0.823800	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	task_mean	z2p6	199	positive	0.356100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	task_mean	z2p6	199	negative	0.381100	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	task_mean	z3p1	199	positive	0.447700	0	0	none	-	-	-
VS	win_loss_double_subtraction	core_plus_ucla	task_mean	z3p1	199	negative	0.854800	0	0	none	-	-	-
CHECK PASSED: 132 corrected jobs, 264 directional maps; directions with surviving voxels: act=11, VS=0. No fits, masks, seeds or exclusions changed.

COMMAND EXIT: 0
```
