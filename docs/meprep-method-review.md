# MEPrep and sequential-regression review

Status: research review only. No production or cohort-wide MEPrep execution.
Reviewed 2026-10-21 using the supplied Wang et al. article (Imaging Neuroscience
4, 2026, DOI 10.1162/IMAG.a.1198), the supplied Lindquist et al. preprint
(DOI 10.1101/407676, version posted 2018-09-04), and MEPrep source commit
`c16de3143eff7ed5e475a810adc5ca7a3a541ff5`.

## What MEPrep changes

The paper's Methods 2.2 describes spatial concatenation of the echo images,
FSL MELODIC probabilistic ICA, and an extended ICA-AROMA classifier. Classified
motion components are removed from echoes before optimal combination and
optional TEDANA. Figure 1 places preICA after slice-timing and rigid-motion
correction, not before all preprocessing. Its four comparisons are OptCom,
ME-ICA, preICA+OptCom, and preICA+ME-ICA.

The inspected source supports that sequence:

- `MEPrep_Source/meprep/src/workflows/bold/meprep_t2s.py` creates the spatially
  concatenated preICA node with `denoising_type='nonaggr'`, then connects its
  denoised echo files to the TEDANA node.
- `MEPrep_Source/MEPrep_ICA-AROMA/ICA_AROMA_functions_preICA.py::denoising`
  invokes `fsl_regfilt` with the complete mixing matrix and selected noise
  indices. The selected nonaggressive branch is partial regression, not an
  ordinary rejected-only orthogonal residual projection.
- `MEPrep_Source/meprep/src/interfaces/meprep_multiecho.py` invokes TEDANA on
  those echoes. The inspected connection/call does not pass the first-stage
  mixing matrix into a joint regression with subsequent nuisance/task EVs.
- `MEPrep_Source/requirements.txt` pins TEDANA 25.0.1, unlike RF1's 26.0.3.
  The README uses a mutable container `latest` tag. A replication must pin a
  container digest and record actual installed versions, not assume parity.

Source links (pinned for reproducibility):

- [Workflow](https://github.com/zswang-brainimaging/MEPrep/blob/c16de3143eff7ed5e475a810adc5ca7a3a541ff5/MEPrep_Source/meprep/src/workflows/bold/meprep_t2s.py)
- [PreICA regression](https://github.com/zswang-brainimaging/MEPrep/blob/c16de3143eff7ed5e475a810adc5ca7a3a541ff5/MEPrep_Source/MEPrep_ICA-AROMA/ICA_AROMA_functions_preICA.py)
- [TEDANA interface](https://github.com/zswang-brainimaging/MEPrep/blob/c16de3143eff7ed5e475a810adc5ca7a3a541ff5/MEPrep_Source/meprep/src/interfaces/meprep_multiecho.py)
- [Dependencies](https://github.com/zswang-brainimaging/MEPrep/blob/c16de3143eff7ed5e475a810adc5ca7a3a541ff5/MEPrep_Source/requirements.txt)

The discussion sometimes calls preICA independent per-echo ICA, whereas Methods
2.2 describes spatial concatenation and the README selects `preICA_scme`. Use the
explicit mode/source as the replication contract rather than treating these
descriptions as interchangeable.

## How Lindquist applies

For ordinary least-squares nuisance residual makers R_A and R_B, sequential
cleaning gives R_B R_A y. This generally differs from jointly removing the union
of the two nuisance spaces. A later regression or temporal filter can restore
association with an earlier removed nuisance space. Joint modeling or correctly
residualizing subsequent designs/filters can avoid this issue. Software being
"modular" is not itself the problem; the temporal operators are.

This establishes a risk to test, not proof that MEPrep reintroduces artifacts.
For example, second-stage regressors derived wholly within a residual subspace
can preserve earlier constraints under appropriate operations. Moreover,
MEPrep's nonaggressive first-stage operation is not the simple orthogonal
projection in the introductory example, so zero correlation with every original
noise IC is not the right universal success criterion.

Section 4.3 of the MEPrep paper asserts that the stages remove orthogonal noise.
Different intended artifact targets, increased entropy, and improved tSNR do
not by themselves demonstrate that the actual fitted temporal operators
preserve that orthogonality. The inspected workflow does not explicitly enforce
a joint first-stage/second-stage/downstream task nuisance model. We need saved
mixing matrices, classifications, and intermediates to test the claim, including
whatever temporal filtering and additional regression follows MEPrep.

RF1 currently fits task EVs, standard nuisance EVs, and rejected TEDANA ICs
together against full-length fMRIPrep BOLD. Preserve that architecture. Audit
filtered/whitened task and nuisance designs consistently; simultaneous modeling
does not excuse mismatched filtering. Replacing this input with precleaned
MEPrep BOLD would change the analysis, not merely reduce the number of confound
columns. Extracting preICA components without applying preICA to the echoes and
using them jointly as nuisance EVs would be a different method, not a faithful
replication of the published preICA benefit to echo combination.

## Strength and limits of the evidence

Methods 2.3-2.4 validate on 32 healthy participants, one resting-state run each,
four echoes, Siemens Trio, TR 2.47 s, 239 volumes. Reported outcomes include T2*
fit residuals, DVARS, tSNR, network-map similarity, within-run connectivity
stability, and entropy. These offer convergent evidence worth testing, not a
clean-signal gold standard or direct validation of RF1 event-related contrasts.

The described temporal reliability analysis compares partial windows with the
full run containing those windows. It is not independent repeated-scan or
held-out task-effect validation. The authors explicitly identify single-dataset
generalization, short/noisy scans, computational cost, and task-evoked designs
as limitations/future work (Section 4.4).

A smaller *final* TEDANA component count after preICA would not establish lower
total model cost: preICA has already removed variation upstream. Account for
both stages' effective temporal transformations, not just their final IC counts.

## Proposed separate experiment

First run the matched cohort-wide AIC/KIC/MDL experiment described in
`tedana-cohort-pca.md`. MEPrep should not delay that run or replace it.

For an explicitly labeled MEPrep feasibility study, predefine ordinary and
high-dimensional runs across task, session, and scanner era, including low and
high motion. Retain original inputs and all intermediates. Use version-matched
no-preICA controls to separate algorithm changes from package-version changes.

1. Save every first-stage and TEDANA mixing matrix, classification, transform,
   echo/optcom intermediate, temporal filter, and downstream design.
2. Measure changes in motion association and first-stage removed-variance
   association after each later stage; distinguish intended nonaggressive
   shared variance from genuine reintroduction by reconstructing the operator.
3. Check task signal preservation with predefined contrasts, realistic signal
   injection before processing, and held-out/repeated-run agreement where
   available. Do not tune to the largest activation or retained N.
4. Account for total effective model cost, task-estimation efficiency, and
   matched signal scale alongside DVARS/motion coupling and T2* fit quality.
5. Only after these checks decide whether a larger MEPrep comparison is useful.
   A pilot is not cohort validation and must never be reported as such.

No claim is made that MEPrep is invalid. No claim is made that its paper proves
compatibility with RF1's simultaneous task GLM. The unresolved question is
measurable, not a reason to adopt or reject the pipeline by its architecture name.

## References

- [Wang et al., MEPrep](https://doi.org/10.1162/IMAG.a.1198)
- [Lindquist et al., supplied preprint](https://doi.org/10.1101/407676)
- [MEPrep repository](https://github.com/zswang-brainimaging/MEPrep)
