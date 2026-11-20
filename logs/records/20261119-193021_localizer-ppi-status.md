# Run Record: localizer-ppi-status

- Timestamp: 20261119-193021
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261119-193021_localizer-ppi-status.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
python3 - /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-localizer-ppi-v1
```

## Full Log

```text
RUN START: 20261119-193021
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2
COMMAND: python3 - /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-localizer-ppi-v1

Seed/run checks: 2336; failed: 12
Affected participants: 5; distinct runs: 6
vmpfc: QA passed 584/584; L1 completion receipts 0/584
ffa_left: QA passed 584/584; L1 completion receipts 0/584
ffa_right: QA passed 578/584; L1 completion receipts 0/584
ffa_bilateral: QA passed 578/584; L1 completion receipts 0/584
Failed checks (aggregate; bilateral coverage is the worse hemisphere):
  ffa_bilateral doors: inherited hemisphere failure; in-mask=54/54; relative signal=1.0502257845574794; count=1
  ffa_bilateral doors: inherited hemisphere failure; in-mask=54/54; relative signal=1.1140263378831112; count=1
  ffa_bilateral doors: inherited hemisphere failure; in-mask=54/54; relative signal=1.2316520663749013; count=1
  ffa_bilateral socialdoors: inherited hemisphere failure; in-mask=54/54; relative signal=0.9240182162875973; count=1
  ffa_bilateral socialdoors: inherited hemisphere failure; in-mask=54/54; relative signal=0.9931333354328772; count=1
  ffa_bilateral socialdoors: inherited hemisphere failure; in-mask=54/54; relative signal=1.0498768794368363; count=1
  ffa_right doors: unusable in-mask voxels; in-mask=27/27; relative signal=1.1018700278575733; count=1
  ffa_right doors: unusable in-mask voxels; in-mask=27/27; relative signal=1.1218723169102989; count=1
  ffa_right doors: unusable in-mask voxels; in-mask=27/27; relative signal=1.1380933048525113; count=1
  ffa_right socialdoors: unusable in-mask voxels; in-mask=27/27; relative signal=0.9261364647010961; count=1
  ffa_right socialdoors: unusable in-mask voxels; in-mask=27/27; relative signal=0.9965958456973371; count=1
  ffa_right socialdoors: unusable in-mask voxels; in-mask=27/27; relative signal=1.0540092393944092; count=1
VS replay pass receipts: 0 / 2
Randomise attempt records: 0 | completed: 0 / 264

COMMAND EXIT: 0
```
