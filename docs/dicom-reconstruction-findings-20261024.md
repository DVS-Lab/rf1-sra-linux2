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

## Follow-up: Distortion Mode Interpretation

The exact common field is `ASCCONV.sDistortionCorrFilter.ucMode` in all three
eras. The [sequence-developer VASO FAQ, question 7](https://layerfmri.com/2021/02/22/vaso_ve/)
documents this Siemens field as 1 = no distortion filter, 2 = 2D correction,
4 = 3D correction (3 is redirected to 4). This is direct technical documentation
from sequence developers, not a CMRR-specific enum declaration for every build.
Using that mapping, our samples imply E11 off, XA30 2D, XA60 off. This is the
opposite direction to an accidental XA60 enablement. There is no evidence here
that the enum meaning changed, but exact-build source definitions have not been
obtained, and the same field name alone cannot prove that they did not change.

An independent header observation supports this interpretation: all 28 sampled
XA30 DICOMs report `VolumetricProperties=VOLUME`, versus `DISTORTED` for all 36
XA60 DICOMs; E11 lacks this attribute. This is corroboration, not a standalone
gradient-correction flag. Siemens' [XA60 reference handbook, page 196](https://doclib.siemens-healthineers.com/rest/v1/view?document-id=1069431)
describes geometric 2D/3D Distortion Correction separately from Static Field
Correction for susceptibility distortions. Do not equate this field with the
later WarpKit operation.

The newer ses-02 echo times differ by 0, -0.48, -0.98 and -1.46 ms respectively:
13.80/31.54/49.28/67.02 becomes 13.80/31.06/48.30/65.56 ms. The largest relative
change is approximately -2.18%. Four sampled runs have the newer setting. The
same first echo and approximately 0.49-ms reduction per subsequent echo are
consistent with shorter inter-echo timing, but do not establish why it changed
or whether the operator edited it. The build association is not causal proof.
These changes do not explain the ses-01 comparison, whose TEs all match.

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

The user confirms the smoothness difference is already in raw BIDS. Keep this
investigation strictly to DICOMs and raw BIDS; downstream processing cannot be
its origin. The [isolated pixel-parity test](dicom-bids-pixel-parity.md) compares
independently decoded DICOM volumes with canonical raw BIDS and a scratch
conversion, without registration or interpolation. These sample links started
as metadata candidates, not exact UID-verified conversion links. A unique full
volume pixel match provides additional direct linkage; missing/mismatched
pixels remain unresolved, not automatically evidence of interpolation.
