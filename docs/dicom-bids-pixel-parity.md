# DICOM And Raw BIDS Pixel Parity

## Scope

`check_dicom_bids_pixels.py` uses the saved 88-header inventory and live Linux2
source DICOMs/raw BIDS. It touches no derivatives, repair workspaces, TEDANA
experiments, QC rules or exclusions. All outputs stay in a new ignored work
directory. Lab files retain `umask 0000`. Run sequentially; no worker pool is
needed for this bounded verification.

For each collected sample:

1. Verify the live source size/mtime, BIDS JSON SHA256 and candidate metadata
   against the saved inventory. Changed inputs stop that sample.
2. Independently decode the single echo-1 DICOM volume using pydicom and NiBabel
   Siemens Mosaic/Enhanced-MR readers, including header-defined intensity scale.
3. Match patient geometry to raw BIDS using only full-grid axis permutations
   and flips (LPS/RAS coordinate conventions handled explicitly). No registration,
   interpolation, cropping, padding, or fitted intensity scaling is permitted.
4. Check every voxel against each BIDS timepoint; require exactly one matching
   volume within absolute tolerance 0.0001, with exact equality also recorded.
5. Independently copy that DICOM into scratch and convert it with dcm2niix in
   the production HeuDiConv container, using `-x i` to disable 3D crop/rotation.
   Compare this output against the independently decoded pixels as well.
6. Recheck input signatures and retain source/NIfTI/container/tool hashes,
   converter versions, transforms, errors and matched volume indices privately.

The independent decoder never uses dcm2niix output as its reference. Orientation
changes are index changes, not interpolations. NIfTI qform/sform numerical
rounding is allowed up to 0.001 voxel when recognizing an integer index map.
A failed geometry or pixel comparison is REVIEW/ERROR, not proof of smoothing:
source identity, unsupported decoding, scaling, or coordinate metadata may be
responsible. No silent numerical fitting or nearest-neighbor resampling is used
to manufacture a pass.

This checks **one volume, echo 1, per sampled run**, not every timepoint/echo or
every participant. It can establish that sampled output pixels were preserved;
it cannot exclude scanner-side reconstruction smoothing already present in the
DICOM. The newly converted scratch volume does not claim to recreate the exact
historical command if converter versions/settings differ. Canonical BIDS is
checked directly regardless of the scratch converter version.

## Linux2 Launch

Use the published commit as `FIX_REF`; fetch/archive does not alter the active
checkout or frozen repair code. The original header inventory must still exist.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
FIX_REF=REPLACE_WITH_PUBLISHED_COMMIT
TOOLS="$PWD/work/dicom-pixels-tools-$FIX_REF"
mkdir -p "$TOOLS" logs/runs
git archive "$FIX_REF" code | tar -x -C "$TOOLS"
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
INVENTORY="$PWD/work/dicom-reconstruction-20261024-154055/inventory-private.json"
test -f "$INVENTORY"
STAMP=dicom-bids-pixels-$(date +%Y%m%d-%H%M%S)
OUTPUT="$PWD/work/$STAMP"
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
  "$AUDIT_PYTHON" "$TOOLS/code/check_dicom_bids_pixels.py" \
    --project "$PWD" --inventory "$INVENTORY" --output "$OUTPUT" \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
echo "REPORT=$OUTPUT/report-private.json"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
)
```

The Git-trackable run record is written on completion. `summary.md` contains
aggregate status only. Keep the raw copied DICOM, converted images and detailed
headers/UIDs in ignored work; never `git add -f` this directory. A report with
any REVIEW/ERROR requires inspection, not changes to source mappings or data.
