# RF1 Wave 1 Shared Reward ratings

Pari and Shenghan can start with
`derivatives/behavioral/sharedreward/ses-01/ratings_summary.tsv` in the
`rf1-sra-linux2` checkout. The table has one row per baseline participant.
Join on the BIDS `participant_id` (e.g. `sub-10317`) and `session_id`
(`ses-01`). A person contributes one set of ratings across both scan runs.
The summary preserves original scale points and signed differences.

| Fields | Meaning |
| --- | --- |
| `friend_win`, `friend_loss`, `stranger_win`, `stranger_loss`, `computer_win`, `computer_loss` | Post-task experience on the original −5 to +5 scale. Zero is neutral. |
| `friend_win_minus_loss`, `stranger_win_minus_loss`, `computer_win_minus_loss` | Win rating minus loss rating for the named partner. |
| `X_FS` | Friend win-minus-loss minus stranger win-minus-loss. Positive values indicate a larger win–loss difference with the friend. |
| `X_FC` | Friend win-minus-loss minus computer win-minus-loss. |
| `ratings_status`, `n_responses` | Availability of the six ratings. Missing values use `n/a`; a contrast requires all its component values. |
| `ratings_qc_pass`, `ratings_qc_reason` | The existing primary behavioral rule requires all six responses, variation across the six, and loss ≤ win for **each** partner. A tie within a partner is allowed. Reasons for multiple reversals are separated by semicolons. |

For the behavioral model, select `ratings_qc_pass == true` and then merge
the measures required by that model. The ratings flag covers sharing
experience only. Friend/stranger IOS measures closeness and must be joined
separately, as must cognition and FEVS. Imaging eligibility is a separate
decision. All observed ratings, including behaviorally flagged responses,
remain available in the BIDS files and summary.

## Source and coverage

The input is the private `DVS-Lab/rf1-sra` Git tree at
`9b9cf69348adcd6ec0b19861b637f1a63d1129cb`, which contains the restored
sub-10803 source. There were no subsequent changes to these Wave 1 rating
CSVs through `cf46557b895f662c5bd730d420fafda2c34e4c91`. Use
`stimuli/Scan-Card_Guessing_Game/card_guessing_ratings.py` and
`SRratings.csv` at the source revision for the prompt, scale and code mapping.
The prompt asks how it felt to win or lose money with the displayed partner.
Partner 1/2/3 denotes computer/stranger/friend. Trait 0/1 denotes win/loss.

One file per participant goes to
`bids/sub-<id>/ses-01/beh/sub-<id>_ses-01_task-sharedreward_acq-post_beh.tsv`.
The task-level dictionary is `bids/task-sharedreward_acq-post_beh.json`.
The four columns match the [SRNDNA export](https://github.com/DVS-Lab/srndna-datapaper/blob/main/bids/task-sharedreward_beh.json).
Ratings have item order and no recorded onsets or durations.
[BIDS behavioral recordings](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/behavioral-experiments.html)
describe this representation.

RF1 Shared Reward was acquired at Wave 1. The operator-entered source
filename suffix (blank, 1, or 2) is a ratings label, not an MRI wave or run.
The [reviewed RF1 file selection](https://github.com/DVS-Lab/sharedreward-aging/blob/main/docs/ratings_source_resolutions.tsv)
chooses the suffix-2 file for sub-10369. Four other files have a repeated
header marking another administration. The last complete block from the
selected file supplies the six items in source order. Earlier blocks remain
traceable. When only partial data exist, the final nonempty block is retained
and flagged. A missing file produces a summary row with missing responses.

In the verified local build, 330 of the 352 baseline BIDS participants had
all six ratings (1,980 responses). Twenty-two had no linked source. Of the 330,
36 had a loss above a win for at least one partner and eight rated all six
items identically. **286 passed ratings QC** before model-specific joins.
All 1,980 raw values agree with the previous Linux2 subject-level ratings
audit. The participant roster is independent of imaging QC, the older
ds003745 cohort, and the manuscript's survey export.

Three additional non-excluded source IDs had no matching BIDS participant.
They are preserved for identity review in the private `sources.tsv` beside
the summary, using `selection=unlinked_to_roster`. Use that table to trace
source paths, SHA-256 digests, selected blocks and earlier attempts. Treat
confirmed identity corrections as upstream source changes. The accompanying
`provenance.json` records the source revision, input and output hashes and
aggregate coverage. Individual outputs live in the Git-ignored `bids/` and
`derivatives/` trees.

## Reproduce on Linux2

With the sibling private `rf1-sra` clone present, use Python 3.9 or newer.
The default reads the live source exclusions and canonical `bids/participants.tsv`.
The command below works even if the preprocessing checkout must stay frozen.
It fetches the exporter into a fresh private working directory, records its
revision in the log label and installs only the ratings products.

```bash
(
  set -e -o pipefail
  cd /ZPOOL/data/projects/rf1-sra-linux2
  umask 0000
  git fetch origin main
  ratings_ref=$(git rev-parse FETCH_HEAD)
  mkdir -p work
  ratings_tools=$(mktemp -d "$PWD/work/sharedreward-ratings.XXXXXX")
  git archive "$ratings_ref" code/{sharedreward_ratings.py,participants.py,pipeline_utils.py,task-sharedreward_acq-post_beh.json} |
    tar -x -C "$ratings_tools"
  ratings=(python3 "$ratings_tools/code/sharedreward_ratings.py" --project-root "$PWD")
  bash code/run_logged.sh --label "sharedreward-wave1-ratings-${ratings_ref:0:8}" --include-full-log -- \
    "${ratings[@]}" --apply --check "${ratings[@]}" --check
)
```

Running the exporter without a mode flag previews the inventory. Installation
creates missing files and verifies existing ones. A differing or stale
output stops the export for review. On a local checkout, `--local-snapshot`
uses the roster and exclusion fingerprints from the verified Linux2 participant
build. The same acquisition revision and inputs produce byte-identical outputs.
Completed Linux2 run records can be shared using the
[append-only log publisher](publish-run-logs.md).
