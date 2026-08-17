# Run Record: fMRIPrep Geometry Audit 20260817-145053

- Date: 2026-08-17
- Production checkout: `/ZPOOL/data/projects/rf1-sra-linux2`
- Workflow commit: `be59d1ce`
- Status: Audit and repair preview completed; repair not yet applied.
- Pristine BIDS modified: No.

## Scope

The audit inspected every non-echo, 4D,
`space-MNI152NLin6Asym_desc-preproc_bold.nii.gz` in the production fMRIPrep
derivatives tree. Echo-specific outputs and CIFTI files were outside scope.

## Result

- Files audited: 2,722
- Files on modal grid: 2,713
- Outliers: 9
- Invalid/unreadable images: 0
- Affected subjects: 2

Modal grid:

```text
shape:       57 x 70 x 54
voxel size: 2.70 x 2.70 x 2.97 mm
orientation: RAS
origin:     -74.80, -109.80, -72.00 mm
```

Shared outlier grid:

```text
shape:       53 x 70 x 59
voxel size: 2.97 x 2.70 x 2.70 mm
orientation: RAS
origin:     -76.15, -109.80, -72.00 mm
```

All nine outliers shared this same alternate grid. Their physical coverage was
similar to the modal grid, consistent with a coherent alternate sampling grid
rather than unreadable or randomly corrupted headers.

## Affected Runs

| Subject | Session | Task | Run |
| --- | --- | --- | --- |
| 11909 | 01 | sharedreward | 1 |
| 12013 | 01 | doors | 1 |
| 12013 | 01 | sharedreward | 1 |
| 12013 | 01 | sharedreward | 2 |
| 12013 | 01 | socialdoors | 1 |
| 12013 | 01 | trust | 1 |
| 12013 | 01 | trust | 2 |
| 12013 | 01 | ugr | 1 |
| 12013 | 01 | ugr | 2 |

The `sub-12013` findings cover its complete expected session-01 task/run set.
Only Shared Reward run 1 was nonmodal for `sub-11909`.

## Production Artifacts

- Audit JSON: `/ZPOOL/data/projects/rf1-sra-linux2/logs/geometry/fmriprep-geometry-20260817-145053.json`
- Audit TSV: `/ZPOOL/data/projects/rf1-sra-linux2/logs/geometry/fmriprep-geometry-20260817-145053.tsv`
- Planned original backup root: `/ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep_geometry/originals/fmriprep-geometry-20260817-145053`
- Planned repair provenance root: `/ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep_geometry/repairs/fmriprep-geometry-20260817-145053`

The JSON report contains the modal-reference checksum and each original
outlier checksum. The full JSON/TSV reports and imaging backups remain on
Linux2 and are intentionally not stored in GitHub.

## Repair Preview

The preview rechecked the complete derivative inventory, modal reference, and
all outlier checksums against the frozen audit contract.

```text
Audit outliers: 9
Pending repair: 9
Already repaired and verified: 0
DRY RUN: no files were copied, resampled, or replaced.
```

No inventory drift, changed input, stale backup, or partial prior repair was
reported. The next reviewed action is `fmriprep_geometry.py repair --apply`
against this exact audit JSON, followed by `fmriprep_geometry.py verify`.
