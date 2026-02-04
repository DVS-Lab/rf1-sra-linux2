import os
import glob
import pydicom

# Melanie Kos (with help from neurostars and chatgpt)
# Script to address "Assertion Error  Conflicting study identifiers found" from heudiconv (prepdata) output
# This script is for subjects that probably had to be pulled out mid-scan and then were named something else
# Note that this is for RF1-SRA project; since there are 1000s of images, it will take a few min to run

# Insert subject ID to be amended
sub_id = "11891"

base_dir = f"/ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-{sub_id}/Smith-SRA-{sub_id}/scans"

# Recursively grab EVERY .dcm file under scans
alldcm = glob.glob(os.path.join(base_dir, "**", "*.dcm"), recursive=True)

if len(alldcm) == 0:
    raise RuntimeError(f"No DICOMs found for subject {sub_id} in {base_dir}")

print(f"Found {len(alldcm)} DICOMs for subject {sub_id}")

studyUID = None

for jj, dcm_path in enumerate(alldcm):
    ds = pydicom.dcmread(dcm_path)

    if studyUID is None:
        studyUID = ds.StudyInstanceUID
        print(f"Using StudyInstanceUID: {studyUID}")

    ds.StudyInstanceUID = studyUID
    ds.save_as(dcm_path)

print("Done. All StudyInstanceUIDs standardized.")

