# Private-header review: scanner-era reconstruction

Read-only review of the 88-header package collected October 24. Package checksums
matched its provenance manifest. Raw headers, identifiers and participant-level
comparisons remain outside Git. This is a sampled metadata comparison, not a
cohort-wide causal analysis or a change to eligibility.

## Decoder correction

All 88 headers contain decodable ASCCONV protocol text: E11 24/24, XA30 28/28,
XA60 36/36. The original zero-block result was a decoder limitation, not missing
scanner metadata. Siemens array-size declarations caused NiBabel's parser to
construct dictionaries where subsequent indexed values required lists. The
inspector now preserves declarations separately and parses the remaining values.
E11 uses CSA protocol storage; the sampled XA headers carry protocol text in a
different private element. No new source-data collection was required.

## Findings

- Session 01 contains 24 sampled runs per era, spanning Doors, Social Doors,
  Shared Reward, Trust and UGR. Each task/run has three samples per era. There
  are 10 distinct E11 participants, three XA30 and seven XA60. These are not 72
  independent participants or a balanced longitudinal sample.
- Session 02 has four XA30 samples from one participant and 12 XA60 samples from
  four participants. Do not treat this as a well-powered era comparison.
- Session-01 XA30 and XA60 match on TR (1.615 s), four TEs
  (13.8/31.54/49.28/67.02 ms), flip angle (50 degrees), base resolution and phase
  lines (80), FOV (216 mm), slice count (51), thickness (2.7 mm), bandwidth
  (2500 Hz/pixel), in-plane acceleration (2), and reference lines (58).
- E11 is not entirely identical: eight sampled runs have a 20-degree rather
  than 50-degree flip angle, corroborated by both standard and protocol headers.
- CMRR build identifiers differ: E11 R016 `434b28f1`; XA30 R017 `d8d65e45a`;
  XA60 R017 `452845729`. Four newer XA60 session-02 samples use R017 `bec5d13e2`
  and TEs 13.8/31.06/48.30/65.56 ms. Thus XA60 is not a single sequence build.
- The distortion-correction mode is 2 in all 28 XA30 samples versus 1 in all
  24 E11 and 36 XA60 samples. This is a reproducible configuration difference;
  do not infer the meaning of undocumented enums or attribute smoothness to it
  without the matching vendor/sequence definition.
- Both XA eras explicitly report `KSpaceFiltering=NONE`. Coil-combination mode
  (1), reconstruction mode (8), prescan-normalization fields (mode 2/on 1), and
  noise-decorrelation mode (1) match across the sampled eras. This is not proof
  that every internal reconstruction operation is identical.
- XA60 adds `MrAdvancedReconstruction.sDeepResolveBoost` and
  `sDeepResolveGain` parameter branches where XA30 has `sIterativeDenoising`.
  Advanced-reconstruction mode is 1 in both XA eras, and XA60 denoising-method
  is 0. **The presence of stored strength/edge-enhancement defaults does not
  establish that Deep Resolve or smoothing was enabled for CMRR BOLD.**
- Several CMRR WIP slots differ, including `adFree[6]`, `adFree[8]`, and
  `alFree[10]`. Slot meanings must be obtained for the exact builds; a raw number
  is not an interpretable denoising or smoothing setting by itself.

## Interpretation and next useful evidence

The headers identify real version/configuration differences, but do not yet
identify the cause of higher XA60 estimated smoothness. The shorter TEs belong
to a newer session-02 build and cannot explain a session-01 XA60 difference.
It would be incorrect to announce that XA60 enabled Deep Resolve based on this
evidence alone.

Ask scanner/CMRR support to compare the exact XA30 `d8d65e45a` and XA60
`452845729` BOLD reconstruction builds and exported protocols, particularly the
active ICE reconstruction chain, distortion correction, interpolation,
coil-combination and denoising/filter enable flags. CMRR's [official support
guidance](https://downloads.cmrr.umn.edu/software/package/multiband/) requests
the sequence version, variant and scanner model for technical reports. Share
only suitably reviewed protocol metadata, not complete participant headers.

Separately, compare spatial smoothness at raw/native magnitude and successive
processing stages within task/session to localize when the difference appears.
These sample links were metadata candidates, not exact UID-verified conversion
links; that limitation remains when attributing a particular BIDS run to a source.
