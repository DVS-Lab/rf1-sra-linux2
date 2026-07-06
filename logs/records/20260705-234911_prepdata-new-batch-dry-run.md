# Run Record: prepdata-new-batch-dry-run

- Timestamp: 20260705-234911
- Branch: main
- Commit: 7e3ce83f
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260705-234911_prepdata-new-batch-dry-run.log`
- Command exit: 1
- Check exit: none
- Summary: COMMAND FAILED: exit 1; no check command was provided.

## Command

```bash
bash run_prepdata.sh --sublist sublist-new.txt --jobs 10 --dry-run
```

## Error Lines

```text
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11772-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11772 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11774-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11774 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11773-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11773 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11788-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11788 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11784-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11784 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11787-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11787 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11790-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11790 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11789-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11789 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11793-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11793 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11815-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11815 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11795-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11795 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11823-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11823 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11822-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11822 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11824-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11824 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11828-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11828 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11840-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11840 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11829-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11829 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11836-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11836 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11847-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11847 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11854-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11854 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11853-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11853 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11861-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11861 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11866-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11866 -ss 01 -c dcm2niix -b --minmeta --overwrite
Required source directory not found: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11891/Smith-SRA-11891
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11867-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11867 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11870-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11870 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11872-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11872 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11876-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11876 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11881-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11881 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11885-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11885 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11877-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11877 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11902-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11902 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11900-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11900 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11897-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11897 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11909-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11909 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11914-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11914 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11913-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11913 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11922-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11922 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11920-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11920 -ss 01 -c dcm2niix -b --minmeta --overwrite
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11923-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11923 -ss 01 -c dcm2niix -b --minmeta --overwrite
```

## Log Tail

```text
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11861/Smith-SRA-11861/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11861/Smith-SRA-11861/scans/39-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11861-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11861 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11866 ses-01: heuristics_XA30.py [seen=2026-04-21 17:16:19; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11866/Smith-SRA-11866/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11866-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11866 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11877 ses-01
Launching prepdata sub-11877 ses-02
Launching prepdata sub-11881 ses-01
Launching prepdata sub-11881 ses-02
Launching prepdata sub-11885 ses-01
No source directory for optional sub-11877 ses-02; skipping.
Launching prepdata sub-11885 ses-02
Launching prepdata sub-11891 ses-01
No source directory for optional sub-11881 ses-02; skipping.
No source directory for optional sub-11885 ses-02; skipping.
Required source directory not found: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11891/Smith-SRA-11891
Heuristic chosen for sub-11867 ses-01: heuristics_XA30.py [seen=2026-04-21 16:49:57; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11867/Smith-SRA-11867/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11867-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11867 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11870 ses-01: heuristics_XA30.py [seen=2026-04-21 17:23:49; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11870/Smith-SRA-11870/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11870/Smith-SRA-11870/scans/39-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11870-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11870 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11872 ses-01: heuristics_XA30.py [seen=2026-04-21 18:05:03; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11872/Smith-SRA-11872/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11872/Smith-SRA-11872/scans/39-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11872-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11872 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11891 ses-02
Launching prepdata sub-11897 ses-01
Launching prepdata sub-11897 ses-02
Launching prepdata sub-11900 ses-01
No source directory for optional sub-11891 ses-02; skipping.
Launching prepdata sub-11900 ses-02
Launching prepdata sub-11902 ses-01
No source directory for optional sub-11897 ses-02; skipping.
Launching prepdata sub-11902 ses-02
Launching prepdata sub-11909 ses-01
No source directory for optional sub-11900 ses-02; skipping.
No source directory for optional sub-11902 ses-02; skipping.
Heuristic chosen for sub-11876 ses-01: heuristics_XA30.py [seen=2026-04-21 18:49:15; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11876/Smith-SRA-11876/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11876-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11876 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11881 ses-01: heuristics_XA30.py [seen=2026-04-21 19:07:43; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11881/Smith-SRA-11881/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11881-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11881 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11909 ses-02
Launching prepdata sub-11913 ses-01
Launching prepdata sub-11913 ses-02
Launching prepdata sub-11914 ses-01
No source directory for optional sub-11909 ses-02; skipping.
No source directory for optional sub-11913 ses-02; skipping.
Heuristic chosen for sub-11885 ses-01: heuristics_XA30.py [seen=2026-04-21 19:16:40; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11885/Smith-SRA-11885/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11885-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11885 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11877 ses-01: heuristics_XA30.py [seen=2026-04-21 16:39:59; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11877/Smith-SRA-11877/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11877/Smith-SRA-11877/scans/23-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11877-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11877 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11914 ses-02
Launching prepdata sub-11920 ses-01
Launching prepdata sub-11920 ses-02
Launching prepdata sub-11922 ses-01
No source directory for optional sub-11914 ses-02; skipping.
No source directory for optional sub-11920 ses-02; skipping.
Heuristic chosen for sub-11902 ses-01: heuristics_XA30.py [seen=2026-04-21 19:51:11; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11902/Smith-SRA-11902/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11902-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11902 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11900 ses-01: heuristics_XA30.py [seen=2026-04-21 19:37:20; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11900/Smith-SRA-11900/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11900-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11900 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11897 ses-01: heuristics_XA30.py [seen=2026-04-21 19:58:12; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11897/Smith-SRA-11897/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11897-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11897 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11909 ses-01: heuristics_XA30.py [seen=2026-04-21 20:18:40; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11909/Smith-SRA-11909/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11909-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11909 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11922 ses-02
Launching prepdata sub-11923 ses-01
Launching prepdata sub-11923 ses-02
No source directory for optional sub-11922 ses-02; skipping.
No source directory for optional sub-11923 ses-02; skipping.
Heuristic chosen for sub-11914 ses-01: heuristics_XA30.py [seen=2026-04-21 20:11:48; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11914/Smith-SRA-11914/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11914-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11914 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11913 ses-01: heuristics_XA30.py [seen=2026-04-21 20:27:55; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11913/Smith-SRA-11913/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11913/Smith-SRA-11913/scans/49-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11913-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11913 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11922 ses-01: heuristics_XA30.py [seen=2026-04-21 20:04:37; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11922/Smith-SRA-11922/scans/1-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11922/Smith-SRA-11922/scans/27-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11922/Smith-SRA-11922/scans/35-localizer
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11922/Smith-SRA-11922/scans/43-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11922-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11922 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11920 ses-01: heuristics_XA30.py [seen=2026-04-21 19:44:12; cutoff=2025-03-04]
Leaving raw localizer in place: /ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-11920/Smith-SRA-11920/scans/1-localizer
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11920-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11920 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Heuristic chosen for sub-11923 ses-01: heuristics_XA30.py [seen=2026-06-11 19:27:10; cutoff=2025-03-04]
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11923-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11923 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.

COMMAND EXIT: 1
```
