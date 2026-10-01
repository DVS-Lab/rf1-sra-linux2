# Run Record: socdoors-missing-source-audit

- Timestamp: 20261001-194326
- Branch: main
- Commit: cf89e2fe
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261001-194326_socdoors-missing-source-audit.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
python3 -
```

## Full Log

```text
RUN START: 20261001-194326
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main cf89e2fe
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2
COMMAND: python3 -

# Missing Doors/SocialDoors: source and conversion audit
Read-only. Label matches are clues, not proof of acquisition identity.
dim4 below is HeuDiConv's recorded dimension, not per-echo NIfTI volumes.

## sub-11083
Matching source folders: 1
Source scan directories: 34
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=34, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11085
Matching source folders: 1
Source scan directories: 28
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=27, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11110
Matching source folders: 1
Source scan directories: 29
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=29, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11128
Matching source folders: 1
Source scan directories: 35
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=35, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11145
Matching source folders: 1
Source scan directories: 32
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=32, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11171
Matching source folders: 1
Source scan directories: 19
Doors-like source scan directories: 2
  source series 19: DICOM/IMA files=8
  source series 20: DICOM/IMA files=635
Saved conversion inventories: 1
  inventory 1, ses-01: rows=19, Doors-like=2
    series=19 task=doors dim4=8 RF1-match=- XA30-match=-
    series=19 task=socialdoors dim4=8 RF1-match=- XA30-match=-
    series=20 task=doors dim4=635 RF1-match=- XA30-match=-
    series=20 task=socialdoors dim4=635 RF1-match=- XA30-match=-
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11203
Matching source folders: 1
Source scan directories: 34
Doors-like source scan directories: 6
  source series 19: DICOM/IMA files=8
  source series 20: DICOM/IMA files=748
  source series 21: DICOM/IMA files=748
  source series 22: DICOM/IMA files=8
  source series 23: DICOM/IMA files=48
  source series 24: DICOM/IMA files=48
Saved conversion inventories: 1
  inventory 1, ses-01: rows=33, Doors-like=6
    series=19 task=doors dim4=8 RF1-match=- XA30-match=-
    series=19 task=socialdoors dim4=8 RF1-match=- XA30-match=-
    series=20 task=doors dim4=748 RF1-match=- XA30-match=-
    series=20 task=socialdoors dim4=748 RF1-match=- XA30-match=-
    series=21 task=doors dim4=748 RF1-match=- XA30-match=-
    series=21 task=socialdoors dim4=748 RF1-match=- XA30-match=-
    series=22 task=doors dim4=8 RF1-match=- XA30-match=-
    series=22 task=socialdoors dim4=8 RF1-match=- XA30-match=-
    series=23 task=doors dim4=48 RF1-match=- XA30-match=-
    series=23 task=socialdoors dim4=48 RF1-match=- XA30-match=-
    series=24 task=doors dim4=48 RF1-match=- XA30-match=-
    series=24 task=socialdoors dim4=48 RF1-match=- XA30-match=-
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11317
Matching source folders: 1
Source scan directories: 13
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=13, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11364
Matching source folders: 1
Source scan directories: 34
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=34, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11396
Matching source folders: 1
Source scan directories: 20
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=19, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

## sub-11443
Matching source folders: 1
Source scan directories: 22
Doors-like source scan directories: 0
Saved conversion inventories: 1
  inventory 1, ses-01: rows=22, Doors-like=0
  BIDS ses-01 task-doors: 0 BOLD files
  BIDS ses-01 task-socialdoors: 0 BOLD files

Inventory finished.
No matching source labels does NOT establish that the task was never acquired.
Heuristic matches describe current rules, not proof of the historical mapping.
Search scope: matching participant folders, not the entire source archive.
No data, conversion rules, or exclusions were changed.

COMMAND EXIT: 0
```
