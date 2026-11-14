# RF1 Storage Audit and Retention

Run **inventory only** while analyses are active. No cleanup, migration, permissions changes, content hashing, or snapshot deletion is needed. The script uses file metadata, skips symlinks and the `.zfs` snapshot namespace, and counts hard-link aliases only once across the scanned trees. "Allocated GiB" is based on reported file blocks; it is not exclusive ZFS usage or a promise of reclaimable space. The inventory can change while jobs are running.

## Linux2 report

Use the existing Linux2 checkout and fetch the reporting script without pulling or editing that checkout. The report contains aggregate project/bucket sizes, not participant IDs or data file paths (mount names, project names, and the scratch root may appear).

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
GIT_TERMINAL_PROMPT=0 git -c remote.origin.url=https://github.com/DVS-Lab/rf1-sra-linux2.git fetch origin main
SCRIPT=$(mktemp /tmp/rf1-storage-audit.XXXXXX)
trap 'rm -f -- "$SCRIPT"' EXIT
git show FETCH_HEAD:code/audit_storage.py > "$SCRIPT"
bash code/run_logged.sh --label "rf1-storage-audit-$(date +%Y%m%d-%H%M%S)" --include-full-log -- \
  nice -n 10 python3 -u "$SCRIPT"
GIT_TERMINAL_PROMPT=0 python3 code/publish_run_logs.py --project "$PWD"
)
```

The inventory covers installed RF1 projects and wrappers, Shared Reward Aging and TUBRIC QA if present, the canonical RF1 source roots, and **this account's** scratch. An absent or unreadable root is noted; other accounts' scratch and unrelated projects are not scanned. ZFS tools are optional. If `df` shows much more space used than the selected live trees, compare the ZFS dataset totals, snapshot accounting, other users' scratch and project usage with the storage administrator. On ZFS a rename on the same filesystem does not free blocks, and snapshots or clones can hold referenced blocks after a file is removed. Do not change pool deduplication or snapshot policy as part of this audit.

## What was multiplied

| Output family | What the code and records establish | Retention question |
|---|---|---|
| Cohort TEDANA PCA | 2,781 runs x 3 criteria = 8,343 completed method/run outputs. Each includes an optcom and a method-specific denoised series. The validator checked equal decoded optcom values across the three methods. | Keep the manifest, validation, mixing matrices, component metrics, decision-tree provenance and historical input dependencies. Check whether any analysis consumes the experiment's denoised images. Compare exact bytes and headers before proposing a shared optcom reference; matching decoded values are not necessarily matching files. |
| 6-mm evaluation | 2,786 completed smoothed 4D series, in a separate evaluation root. The report used measurements, not these volumes as task-model inputs; an out-of-band result is not a failed or disposable run. | Preserve the paired before/after metrics, plans, plots, AFNI inputs and receipts. Check for current image consumers and decide whether to retain or move the validated images after that check. If adoption is planned, reuse them instead of rebuilding them. |
| Pipeline scratch and failed attempts | fMRIPrep, MRIQC, prepdata and other work areas keep cached steps for resumption, often under the shared ZPOOL. TEDANA and smoothing retries retain earlier failed attempts. | First cleanup candidates after confirming jobs are inactive and canonical outputs are validated. Keep error and resume evidence; review failed attempts individually. |
| Source/geometry repairs | Transaction install preserved originals and kept validated staged copies separately. The completed cohort experiment uses pre-repair input lineage mapped into its archive. | Protect originals and transaction manifests. Prune a superseded **staging** tree only after identifying all receipts and products that still point into it. Never treat the historical input archive as temporary. |
| Social Doors, UGR, environmental and psychosocial analyses | Original L1s and age-55 base-only L1s use different nuisance fits, not identical files. The additional all-age base-only run was unnecessary for the existing-fit psychosocial L3 and isn't consumed by it. Group models can already reference common COPE stacks; some paired handoffs also materialized per-subject and merged images. | Keep paper-consumed variants and all active jobs' inputs. Harmless small outputs and references are not a cleanup priority. Review inactive extra FEAT variants and group input stacks only after checking their consumers. |

## Cleanup order

1. Rank actual disk use first. Separate pool/snapshot pressure, inode pressure, mounting a small scratch filesystem, and live RF1 files. Do not size reclamation based on file extensions alone.
2. Keep canonical DICOM/BIDS, production derivatives, active analysis directories, frozen paper inputs, and the authoritative repair archives. Read dependency paths from receipts and selected-input manifests before moving anything. An absent path is not proof a dataset needs to be rebuilt.
3. Prepare a proposed removal list for inactive scratch, failed attempts and superseded stages with verified replacements. For completed experiments, first choose which image evidence remains useful and capture what is retained, where it lives, its fingerprints, and the validation it supports. A cold-storage copy should be verified before considering removal from ZPOOL; moving within the same dataset alone won't reclaim space.
4. For future jobs, key heavy products by input lineage plus model/settings rather than paper or cohort name; have downstream manifests reference them. Store one stack per outcome and ordered cohort, not one per statistical model. Prefer a metrics-only audit where appropriate, explicit retention for expensive intermediates, and estimates of sustained storage as well as temporary headroom before starting a cohort job.

Do not automatically remove optcom files or update old receipts: the existing benchmark checker verifies the original output inventories. A reviewed retention plan needs to preserve historical validation and make any archived or intentionally unretained artifacts explicit.
