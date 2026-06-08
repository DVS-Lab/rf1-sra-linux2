import os
import glob
from nibabel.nicom import dicomwrappers as dw

sub_id = "11923"
base_dir = f"/ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-{sub_id}/Smith-SRA-{sub_id}/scans"

alldcm = glob.glob(os.path.join(base_dir, "**", "*.dcm"), recursive=True)

if len(alldcm) == 0:
    raise RuntimeError(f"No DICOMs found for subject {sub_id} in {base_dir}")

bad = []

for i, dcm_path in enumerate(alldcm, start=1):
    try:
        dw.wrapper_from_file(dcm_path, force=True, stop_before_pixels=True)
    except Exception as e:
        bad.append((dcm_path, str(e)))

    if i % 1000 == 0:
        print(f"Checked {i}/{len(alldcm)}")

print("\nBAD FILES:")
for path, err in bad:
    print(path)
    print(err)
    print()

