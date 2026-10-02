# Run Record: socdoors-source-followup

- Timestamp: 20261001-200328
- Branch: main
- Commit: a383631d
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261001-200328_socdoors-source-followup.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: requested evidence collected; missing-task explanations remain to be reviewed.

## Command

```bash
/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python code/audit_socdoors_sources.py --private-output work/socdoors-source-followup-20261001-200328
```

## Full Log

```text
RUN START: 20261001-200328
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main a383631d
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2
COMMAND: /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python code/audit_socdoors_sources.py --private-output work/socdoors-source-followup-20261001-200328

# Missing Doors follow-up: read-only evidence, not recovery approval

## Behavioral sources (not proof of corresponding MRI acquisition)
subject | session | task | source status | trials | missed | last event end (s)
---|---|---|---|---|---|---
11083 | 01 | doors | missing | - | - | -
11083 | 01 | socialdoors | missing | - | - | -
11083 | 02 | doors | available | 40 | 1 | 330.959
11083 | 02 | socialdoors | available | 40 | 3 | 333.091
11085 | 01 | doors | missing | - | - | -
11085 | 01 | socialdoors | missing | - | - | -
11085 | 02 | doors | missing | - | - | -
11085 | 02 | socialdoors | missing | - | - | -
11110 | 01 | doors | missing | - | - | -
11110 | 01 | socialdoors | missing | - | - | -
11110 | 02 | doors | missing | - | - | -
11110 | 02 | socialdoors | missing | - | - | -
11128 | 01 | doors | missing | - | - | -
11128 | 01 | socialdoors | missing | - | - | -
11128 | 02 | doors | missing | - | - | -
11128 | 02 | socialdoors | missing | - | - | -
11145 | 01 | doors | missing | - | - | -
11145 | 01 | socialdoors | missing | - | - | -
11145 | 02 | doors | missing | - | - | -
11145 | 02 | socialdoors | missing | - | - | -
11171 | 01 | doors | available | 40 | 1 | 330.217
11171 | 01 | socialdoors | available | 40 | 0 | 331.376
11171 | 02 | doors | missing | - | - | -
11171 | 02 | socialdoors | missing | - | - | -
11203 | 01 | doors | available | 1 | 1 | 5.190
11203 | 01 | socialdoors | available | 35 | 1 | 289.765
11203 | 02 | doors | missing | - | - | -
11203 | 02 | socialdoors | missing | - | - | -
11317 | 01 | doors | missing | - | - | -
11317 | 01 | socialdoors | missing | - | - | -
11317 | 02 | doors | missing | - | - | -
11317 | 02 | socialdoors | missing | - | - | -
11364 | 01 | doors | missing | - | - | -
11364 | 01 | socialdoors | missing | - | - | -
11364 | 02 | doors | missing | - | - | -
11364 | 02 | socialdoors | missing | - | - | -
11396 | 01 | doors | missing | - | - | -
11396 | 01 | socialdoors | missing | - | - | -
11396 | 02 | doors | missing | - | - | -
11396 | 02 | socialdoors | missing | - | - | -
11443 | 01 | doors | missing | - | - | -
11443 | 01 | socialdoors | missing | - | - | -
11443 | 02 | doors | missing | - | - | -
11443 | 02 | socialdoors | missing | - | - | -

## sub-11083: all saved series, including non-Doors labels
ses-01: 34 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / ugr / 8 / False / False
8 / ugr / 960 / False / False
9 / ugr / 960 / False / False
10 / ugr / 8 / False / False
11 / ugr / 960 / False / False
12 / ugr / 960 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / trust / 8 / False / False
20 / trust / 1120 / False / False
21 / trust / 1120 / False / False
22 / trust / 8 / False / False
23 / trust / 1120 / False / False
24 / trust / 1120 / False / False
25 / anatomical / 1 / False / False
26 / diffusion / 1 / False / False
27 / diffusion / 1 / False / False
28 / diffusion / 1 / False / False
29 / diffusion / 145 / False / False
30 / diffusion / 1 / False / False
31 / fieldmap / 1 / False / False
32 / fieldmap / 2 / False / False
33 / fieldmap / 1 / False / False
34 / fieldmap / 2 / False / False
99 / scanner-report / 15 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11085: all saved series, including non-Doors labels
ses-01: 27 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / anatomical / 1 / False / False
20 / diffusion / 1 / False / False
21 / diffusion / 1 / False / False
22 / diffusion / 1 / False / False
23 / diffusion / 145 / False / False
24 / diffusion / 1 / False / False
25 / fieldmap / 1 / False / False
26 / fieldmap / 2 / False / False
27 / fieldmap / 1 / False / False
28 / fieldmap / 2 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11110: all saved series, including non-Doors labels
ses-01: 29 series; series / hint / dim4 / RF1-label / XA30-label
1 / localizer / 1 / False / False
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / sharedreward / 8 / False / False
8 / sharedreward / 1020 / False / False
9 / sharedreward / 1020 / False / False
10 / sharedreward / 8 / False / False
11 / sharedreward / 1020 / False / False
12 / sharedreward / 1020 / False / False
13 / ugr / 8 / False / False
14 / ugr / 960 / False / False
15 / ugr / 960 / False / False
16 / ugr / 8 / False / False
17 / ugr / 960 / False / False
18 / ugr / 960 / False / False
19 / anatomical / 1 / False / False
20 / diffusion / 1 / False / False
21 / diffusion / 1 / False / False
22 / diffusion / 1 / False / False
23 / diffusion / 145 / False / False
24 / diffusion / 1 / False / False
25 / fieldmap / 1 / False / False
26 / fieldmap / 2 / False / False
27 / fieldmap / 1 / False / False
28 / fieldmap / 2 / False / False
99 / scanner-report / 13 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11128: all saved series, including non-Doors labels
ses-01: 35 series; series / hint / dim4 / RF1-label / XA30-label
1 / localizer / 1 / False / False
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / ugr / 8 / False / False
20 / ugr / 960 / False / False
21 / ugr / 960 / False / False
22 / ugr / 8 / False / False
23 / ugr / 960 / False / False
24 / ugr / 960 / False / False
25 / anatomical / 1 / False / False
26 / diffusion / 1 / False / False
27 / diffusion / 1 / False / False
28 / diffusion / 1 / False / False
29 / diffusion / 145 / False / False
30 / diffusion / 1 / False / False
31 / fieldmap / 1 / False / False
32 / fieldmap / 2 / False / False
33 / fieldmap / 1 / False / False
34 / fieldmap / 2 / False / False
99 / scanner-report / 15 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11145: all saved series, including non-Doors labels
ses-01: 32 series; series / hint / dim4 / RF1-label / XA30-label
1 / localizer / 1 / False / False
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / ugr / 8 / False / False
8 / ugr / 336 / False / False
9 / ugr / 336 / False / False
10 / ugr / 8 / False / False
11 / ugr / 960 / False / False
12 / ugr / 960 / False / False
13 / ugr / 8 / False / False
14 / ugr / 960 / False / False
15 / ugr / 960 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / sharedreward / 8 / False / False
20 / sharedreward / 1020 / False / False
21 / sharedreward / 1020 / False / False
22 / anatomical / 1 / False / False
23 / diffusion / 1 / False / False
24 / diffusion / 1 / False / False
25 / diffusion / 1 / False / False
26 / diffusion / 145 / False / False
27 / diffusion / 1 / False / False
28 / fieldmap / 1 / False / False
29 / fieldmap / 2 / False / False
30 / fieldmap / 1 / False / False
31 / fieldmap / 2 / False / False
99 / scanner-report / 13 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11171: all saved series, including non-Doors labels
ses-01: 19 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / socialdoors / 8 / True / True
20 / socialdoors / 635 / True / True
Matching source folders: 1 (not an archive-wide search)
Reading 9889 headers, no pixels.

## sub-11171: header-level inventory; 0 unreadable/conflicting files
series | task hint | kind | unique instances by echo | temporal positions by echo | frame tags | TR (ms)
---|---|---|---|---|---|---
10 | trust | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
11 | trust | magnitude | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
12 | trust | phase | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
13 | sharedreward | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
14 | sharedreward | magnitude | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
15 | sharedreward | phase | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
16 | sharedreward | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
17 | sharedreward | magnitude | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
18 | sharedreward | phase | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
19 | socialdoors | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
2 | anatomical | magnitude | 1:192 | unavailable | absent:192 | 2400
20 | socialdoors | magnitude | 1:158,2:159,3:159,4:159 | unavailable | absent:635 | 1615
3 | anatomical | magnitude | 1:192 | unavailable | absent:192 | 2400
4 | fieldmap | magnitude | 1:54,2:54 | unavailable | absent:108 | 645
5 | fieldmap | magnitude | 1:54,2:54 | unavailable | absent:108 | 645
6 | fieldmap | phase | 2:54 | unavailable | absent:54 | 645
7 | trust | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
8 | trust | magnitude | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
9 | trust | phase | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
Duplicate copies: 0; header warnings: 0
Instance/echo counts are NOT volume counts. Enhanced multiframe headers may lack per-frame echo/position tags.
Matching counts alone do not prove complete, correctly paired magnitude/phase acquisitions.

## sub-11203: all saved series, including non-Doors labels
ses-01: 33 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / socialdoors / 8 / True / True
20 / socialdoors / 748 / True / True
21 / socialdoors / 748 / True / True
22 / doors / 8 / True / True
23 / doors / 48 / True / True
24 / doors / 48 / True / True
25 / anatomical / 1 / False / False
26 / diffusion / 1 / False / False
27 / diffusion / 1 / False / False
28 / diffusion / 1 / False / False
29 / diffusion / 145 / False / False
30 / diffusion / 1 / False / False
31 / fieldmap / 1 / False / False
32 / fieldmap / 2 / False / False
33 / fieldmap / 1 / False / False
34 / fieldmap / 2 / False / False
Matching source folders: 1 (not an archive-wide search)
Reading 12307 headers, no pixels.

## sub-11203: header-level inventory; 0 unreadable/conflicting files
series | task hint | kind | unique instances by echo | temporal positions by echo | frame tags | TR (ms)
---|---|---|---|---|---|---
10 | trust | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
11 | trust | magnitude | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
12 | trust | phase | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
13 | sharedreward | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
14 | sharedreward | magnitude | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
15 | sharedreward | phase | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
16 | sharedreward | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
17 | sharedreward | magnitude | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
18 | sharedreward | phase | 1:255,2:255,3:255,4:255 | unavailable | absent:1020 | 1615
19 | socialdoors | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
2 | anatomical | magnitude | 1:192 | unavailable | absent:192 | 2400
20 | socialdoors | magnitude | 1:187,2:187,3:187,4:187 | unavailable | absent:748 | 1615
21 | socialdoors | phase | 1:187,2:187,3:187,4:187 | unavailable | absent:748 | 1615
22 | doors | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
23 | doors | magnitude | 1:12,2:12,3:12,4:12 | unavailable | absent:48 | 1615
24 | doors | phase | 1:12,2:12,3:12,4:12 | unavailable | absent:48 | 1615
25 | anatomical | magnitude | 1:47 | unavailable | absent:47 | 9000
26 | diffusion | SBRef | 1:69 | unavailable | absent:69 | 2710
27 | diffusion | unknown | 1:69 | unavailable | absent:69 | 2710
28 | diffusion | SBRef | 1:1 | unavailable | absent:1 | 2710
29 | diffusion | unknown | 1:145 | unavailable | absent:145 | 2710
3 | anatomical | magnitude | 1:192 | unavailable | absent:192 | 2400
30 | diffusion | unknown | 1:1104 | unavailable | absent:1104 | 2710
31 | fieldmap | SBRef | 1:1 | unavailable | absent:1 | 2710
32 | fieldmap | magnitude | 1:2 | unavailable | absent:2 | 2710
33 | fieldmap | SBRef | 1:1 | unavailable | absent:1 | 2710
34 | fieldmap | magnitude | 1:2 | unavailable | absent:2 | 2710
4 | fieldmap | magnitude | 1:54,2:54 | unavailable | absent:108 | 645
5 | fieldmap | magnitude | 1:54,2:54 | unavailable | absent:108 | 645
6 | fieldmap | phase | 2:54 | unavailable | absent:54 | 645
7 | trust | SBRef | 1:2,2:2,3:2,4:2 | unavailable | absent:8 | 1615
8 | trust | magnitude | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
9 | trust | phase | 1:280,2:280,3:280,4:280 | unavailable | absent:1120 | 1615
99 | scanner-report | unknown | unknown:12 | unavailable | absent:12 | unknown
Duplicate copies: 0; header warnings: 0
Instance/echo counts are NOT volume counts. Enhanced multiframe headers may lack per-frame echo/position tags.
Matching counts alone do not prove complete, correctly paired magnitude/phase acquisitions.

## sub-11317: all saved series, including non-Doors labels
ses-01: 13 series; series / hint / dim4 / RF1-label / XA30-label
1 / localizer / 1 / False / False
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / ugr / 8 / False / False
8 / ugr / 960 / False / False
9 / ugr / 960 / False / False
10 / ugr / 8 / False / False
11 / ugr / 960 / False / False
12 / ugr / 960 / False / False
99 / scanner-report / 5 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11364: all saved series, including non-Doors labels
ses-01: 34 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 1020 / False / False
15 / sharedreward / 1020 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / ugr / 8 / False / False
20 / ugr / 960 / False / False
21 / ugr / 960 / False / False
22 / ugr / 8 / False / False
23 / ugr / 960 / False / False
24 / ugr / 960 / False / False
25 / anatomical / 1 / False / False
26 / diffusion / 1 / False / False
27 / diffusion / 1 / False / False
28 / diffusion / 1 / False / False
29 / diffusion / 145 / False / False
30 / diffusion / 1 / False / False
31 / fieldmap / 1 / False / False
32 / fieldmap / 2 / False / False
33 / fieldmap / 1 / False / False
34 / fieldmap / 2 / False / False
99 / scanner-report / 15 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11396: all saved series, including non-Doors labels
ses-01: 19 series; series / hint / dim4 / RF1-label / XA30-label
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
11 / fieldmap / 1 / False / False
12 / fieldmap / 1 / False / False
13 / fieldmap / 1 / False / False
14 / trust / 8 / False / False
15 / trust / 1120 / False / False
16 / trust / 1120 / False / False
17 / anatomical / 1 / False / False
18 / diffusion / 1 / False / False
19 / diffusion / 1 / False / False
20 / diffusion / 1 / False / False
21 / diffusion / 110 / False / False
Matching source folders: 1 (not an archive-wide search)

## sub-11443: all saved series, including non-Doors labels
ses-01: 22 series; series / hint / dim4 / RF1-label / XA30-label
1 / localizer / 1 / False / False
2 / anatomical / 1 / False / False
3 / anatomical / 1 / False / False
4 / fieldmap / 1 / False / False
5 / fieldmap / 1 / False / False
6 / fieldmap / 1 / False / False
7 / trust / 8 / False / False
8 / trust / 1120 / False / False
9 / trust / 1120 / False / False
10 / trust / 8 / False / False
11 / trust / 1120 / False / False
12 / trust / 1120 / False / False
13 / sharedreward / 8 / False / False
14 / sharedreward / 92 / False / False
15 / sharedreward / 92 / False / False
16 / sharedreward / 8 / False / False
17 / sharedreward / 1020 / False / False
18 / sharedreward / 1020 / False / False
19 / ugr / 8 / False / False
20 / ugr / 960 / False / False
21 / ugr / 960 / False / False
99 / scanner-report / 7 / False / False
Matching source folders: 1 (not an archive-wide search)

Exact metadata saved only in ignored work/. Do not commit that directory.
Session notes were not located/read by this utility. Behavioral completion does not prove MRI coverage.
No data, conversions, or exclusions changed.
Collection errors/missing required inputs: 0
CHECK PASSED: requested evidence collected; missing-task explanations remain to be reviewed.

COMMAND EXIT: 0
```
