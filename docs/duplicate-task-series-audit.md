# Cohort-wide duplicate task-series audit

## Scope and safeguards

`code/audit_duplicate_task_series.py` reads every saved
`bids/.heudiconv/**/dicominfo*.tsv` inventory and its saved `.auto.txt` and
`.edit.txt` conversion mappings. There is no age, paper, task, session, or QC
eligibility filter. Every live BIDS subject/session must have a successfully
audited inventory; missing or unreadable evidence makes collection incomplete.

The audit replays prefixes of each inventory through the current trusted RF1
and XA30 heuristics. This exposes full-length matches that a later assignment
overwrites. Normal multi-run matches retained by append rules are not flagged
merely for being multiple. It also checks repeated/cross-task series assignments,
references to absent inventory series, and magnitude/phase/SBRef count mismatches.
Saved mappings are parsed as literals, never executed. Cached heuristic files
are never executed.

**This is a candidate review, not a new exclusion policy.** It does not change
BIDS, source data, manifests, settled source-validity decisions, QC thresholds,
analysis eligibility, or any derivative. Previously repaired cases may retain
historical mappings that differ from the current production data. Reconcile
those against repair provenance instead of reversing an approved repair.

Both current heuristic views are deliberately reported; neither establishes
which historical heuristic was used. Alternative-view mismatches may be benign.
A count mismatch does not prove that fMRIPrep used the wrong SBRef. A protocol
label does not establish the task actually presented. No anatomical coverage
failure is attributed to a mapping solely from this audit.

Scope limits: this is not a raw-download census, duplicate-DICOM-byte check,
live BIDS-to-UID verification, or behavioral synchronization audit. Partial
acquisitions that do not match the current full-length rules remain outside the
duplicate-match test. Those already documented in the
[unselected-run reconciliation](no-tedana-unselected-reconciliation.md) retain
their existing status. An inventory absent for a source-only, never-converted
session cannot be discovered from BIDS evidence alone.

## Linux2 execution

After the code is published, run from the project root. Standard-library Python
is sufficient; no imaging jobs are launched. Use a new output directory each time.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
STAMP=duplicate-task-series-$(date +%Y%m%d-%H%M%S)
OUT="$PWD/logs/reviews/$STAMP"

bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 python3 code/audit_duplicate_task_series.py build \
    --output-dir "$OUT" \
  --check python3 code/audit_duplicate_task_series.py check \
    --output-dir "$OUT"
```

The report includes `findings.tsv`, `inventory_checks.tsv`, `summary.json`, and
`provenance.json`. All findings and collection errors are also printed into the
shareable Markdown run record under `logs/records/`; no terminal scrolling is
needed. Exact raw series labels are represented by series number plus a short
hash. Full raw DICOM headers, dates, and UIDs are not copied into the findings.

Build exits zero when collection succeeds, **even if there are findings**.
The check verifies unchanged input/output hashes and inventory/mapping/session
sets, and refuses incomplete collection. It does not adjudicate the findings.
Review `errors`, `finding_sessions`, and `findings_by_type`, then reconcile each
flagged session against saved edits, prior repair decisions, live conversion
provenance, and behavior as needed. Do not reprocess automatically.

## Exact question for Ryan: 11935

> For **11935 ses-01**, can you check the session/acquisition notes for the
> actual order of **Social Doors faces versus Doors**? We found two full-length
> acquisitions, but both are scanner-labeled "SocialDoors_face": the first is
> series **25/26**, and the second is **29/30**. Which task was presented during
> each acquisition, and was either a restart or affected by a task/scanner
> synchronization problem? Our current Social Doors BOLD comes from the second
> acquisition. We have complete behavioral files for both tasks, but they do not
> independently establish that mapping. If the notes do not establish the order,
> please say so rather than inferring it from the usual task order.

No relabeling is authorized by this question. Correct task identities and
acquisition-specific SBRefs must be established before any recovery/rebuild.
