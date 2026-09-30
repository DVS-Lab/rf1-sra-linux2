# Run Record: sharedreward-refresh-full-analysis-20260930-203949-441196-build_run_qc

- Timestamp: 20260930-163949
- Branch: main
- Commit: 21d468ce
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260930-163949_sharedreward-refresh-full-analysis-20260930-203949-441196-build_run_qc.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: 2761 acquired BIDS run(s) have complete, internally consistent canonical imaging QC outputs.

## Command

```bash
/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python /ZPOOL/data/projects/rf1-sra-linux2/code/build_run_qc.py build --overwrite
```

## Check

```bash
/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python /ZPOOL/data/projects/rf1-sra-linux2/code/build_run_qc.py check
```

## Full Log

```text
RUN START: 20260930-163949
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 21d468ce
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2
COMMAND: /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python /ZPOOL/data/projects/rf1-sra-linux2/code/build_run_qc.py build --overwrite

Run inventory: 2761
Complete QC rows: 2761
Incomplete QC rows: 0
Any imaging-QC criterion flagged: 479
Complete rows with imaging-QC outlier status: 479
Incomplete rows with a known criterion flagged: 0
task-doors: total=364 complete=364 incomplete=0 tsnr=2 fd=26 tedana=30 coverage=18 any=66
task-sharedreward: total=668 complete=668 incomplete=0 tsnr=0 fd=36 tedana=56 coverage=31 any=113
task-socialdoors: total=364 complete=364 incomplete=0 tsnr=2 fd=19 tedana=29 coverage=19 any=60
task-trust: total=652 complete=652 incomplete=0 tsnr=0 fd=48 tedana=65 coverage=25 any=128
task-ugr: total=713 complete=713 incomplete=0 tsnr=1 fd=36 tedana=55 coverage=31 any=112
Outlier-criterion overlap:
  brain_coverage_pct: 102
  fd_mean: 137
  fd_mean+brain_coverage_pct: 1
  fd_mean+tedana_rejected_components: 25
  tedana_rejected_components: 191
  tedana_rejected_components+brain_coverage_pct: 18
  tsnr+brain_coverage_pct: 2
  tsnr+fd_mean: 2
  tsnr+tedana_rejected_components+brain_coverage_pct: 1
Thresholds:
  sharedreward tsnr: n=668 lower_fence=1.437022632 outliers=0
  sharedreward fd_mean: n=668 upper_fence=0.4231431547 outliers=36
  sharedreward tedana_rejected_components: n=668 upper_fence=39 outliers=56
  sharedreward brain_coverage_pct: n=668 lower_fence=99.15178809 outliers=31
  trust tsnr: n=652 lower_fence=0.3375875571 outliers=0
  trust fd_mean: n=652 upper_fence=0.4284161525 outliers=48
  trust tedana_rejected_components: n=652 upper_fence=40.375 outliers=65
  trust brain_coverage_pct: n=652 lower_fence=99.16573676 outliers=25
  ugr tsnr: n=713 lower_fence=4.94090939 outliers=1
  ugr fd_mean: n=713 upper_fence=0.4274789498 outliers=36
  ugr tedana_rejected_components: n=713 upper_fence=41.5 outliers=55
  ugr brain_coverage_pct: n=713 lower_fence=99.10927786 outliers=31
  socialdoors tsnr: n=728 lower_fence=6.863284165 outliers=4
  socialdoors fd_mean: n=728 upper_fence=0.385144583 outliers=45
  socialdoors tedana_rejected_components: n=728 upper_fence=36.5 outliers=59
  socialdoors brain_coverage_pct: n=728 lower_fence=99.07540252 outliers=37
QC outputs written under: /ZPOOL/data/projects/rf1-sra-linux2/qc

COMMAND EXIT: 0

CHECK COMMAND: /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python /ZPOOL/data/projects/rf1-sra-linux2/code/build_run_qc.py check

Run inventory: 2761
Complete QC rows: 2761
Incomplete QC rows: 0
Any imaging-QC criterion flagged: 479
Complete rows with imaging-QC outlier status: 479
Incomplete rows with a known criterion flagged: 0
task-doors: total=364 complete=364 incomplete=0 tsnr=2 fd=26 tedana=30 coverage=18 any=66
task-sharedreward: total=668 complete=668 incomplete=0 tsnr=0 fd=36 tedana=56 coverage=31 any=113
task-socialdoors: total=364 complete=364 incomplete=0 tsnr=2 fd=19 tedana=29 coverage=19 any=60
task-trust: total=652 complete=652 incomplete=0 tsnr=0 fd=48 tedana=65 coverage=25 any=128
task-ugr: total=713 complete=713 incomplete=0 tsnr=1 fd=36 tedana=55 coverage=31 any=112
Outlier-criterion overlap:
  brain_coverage_pct: 102
  fd_mean: 137
  fd_mean+brain_coverage_pct: 1
  fd_mean+tedana_rejected_components: 25
  tedana_rejected_components: 191
  tedana_rejected_components+brain_coverage_pct: 18
  tsnr+brain_coverage_pct: 2
  tsnr+fd_mean: 2
  tsnr+tedana_rejected_components+brain_coverage_pct: 1
Thresholds:
  sharedreward tsnr: n=668 lower_fence=1.437022632 outliers=0
  sharedreward fd_mean: n=668 upper_fence=0.4231431547 outliers=36
  sharedreward tedana_rejected_components: n=668 upper_fence=39 outliers=56
  sharedreward brain_coverage_pct: n=668 lower_fence=99.15178809 outliers=31
  trust tsnr: n=652 lower_fence=0.3375875571 outliers=0
  trust fd_mean: n=652 upper_fence=0.4284161525 outliers=48
  trust tedana_rejected_components: n=652 upper_fence=40.375 outliers=65
  trust brain_coverage_pct: n=652 lower_fence=99.16573676 outliers=25
  ugr tsnr: n=713 lower_fence=4.94090939 outliers=1
  ugr fd_mean: n=713 upper_fence=0.4274789498 outliers=36
  ugr tedana_rejected_components: n=713 upper_fence=41.5 outliers=55
  ugr brain_coverage_pct: n=713 lower_fence=99.10927786 outliers=31
  socialdoors tsnr: n=728 lower_fence=6.863284165 outliers=4
  socialdoors fd_mean: n=728 upper_fence=0.385144583 outliers=45
  socialdoors tedana_rejected_components: n=728 upper_fence=36.5 outliers=59
  socialdoors brain_coverage_pct: n=728 lower_fence=99.07540252 outliers=37
CHECK PASSED: 2761 acquired BIDS run(s) have complete, internally consistent canonical imaging QC outputs.

CHECK EXIT: 0
```
