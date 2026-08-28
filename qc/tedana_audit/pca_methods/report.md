# TEDANA PCA-Method Sensitivity Report

This is an audit-only matched comparison. It does not modify production TEDANA or authorize a method change.

## Coverage

- Target runs: 20
- Validated method/run outputs: 60
- Methods: NSS-aware FastICA with AIC, KIC, and MDL; all other explicit settings are identical.
- Optimally combined inputs were required to be exactly identical across criteria.

## Model Order And Design Cost

### KIC minus AIC

- PCA components: -17.000 (IQR -22.000 to -11.000)
- Rejected components: -15.000 (IQR -20.250 to -3.000)
- Nuisance rank with intercept: -15.000 (IQR -20.250 to -3.000)
- Residual df before task regressors: 15.000 (IQR 3.000 to 20.250)

### MDL minus AIC

- PCA components: -55.500 (IQR -63.250 to -42.000)
- Rejected components: -48.000 (IQR -57.250 to -8.250)
- Nuisance rank with intercept: -48.000 (IQR -57.250 to -8.250)
- Residual df before task regressors: 48.000 (IQR 8.250 to 57.250)

## Denoising Proxies

### KIC versus AIC

- Denoised tSNR change (%): -4.768 (IQR -9.386 to 0.223)
- Denoised DVARS change (%): 6.019 (IQR 2.584 to 12.236)
- Variance-removed fraction change: -0.024 (IQR -0.035 to 0.002)
- FD-versus-denoised-DVARS Spearman change: 0.029 (IQR -0.015 to 0.166)
- AIC/candidate voxelwise temporal correlation: 0.879966 (IQR 0.783276 to 0.911453)
- AIC/candidate normalized RMSE: 0.010863 (IQR 0.008889 to 0.014975)

### MDL versus AIC

- Denoised tSNR change (%): -10.131 (IQR -19.831 to -2.874)
- Denoised DVARS change (%): 26.356 (IQR 10.388 to 31.384)
- Variance-removed fraction change: -0.062 (IQR -0.110 to -0.020)
- FD-versus-denoised-DVARS Spearman change: 0.155 (IQR 0.077 to 0.477)
- AIC/candidate voxelwise temporal correlation: 0.713259 (IQR 0.657477 to 0.831361)
- AIC/candidate normalized RMSE: 0.019776 (IQR 0.014451 to 0.022153)

## Interpretation Boundary

There is no gold-standard clean fMRI series. Higher tSNR and lower DVARS may reflect artifact attenuation, but can also accompany removal of neural signal. Lower nuisance rank preserves degrees of freedom, but underestimating model order can merge signal and noise sources. Selection therefore requires convergent evidence: reasonable dimensionality, reduced motion coupling, preserved signal scale, acceptable image similarity, and targeted component review.

The TEDANA documentation identifies AIC as least aggressive, KIC as intermediate, and MDL as most aggressive, and recommends considering KIC/MDL when AIC retains more than half the time points or explains over 98% of variance. Li et al. (2007) showed that overestimated ICA order reduces component stability and can degrade task activation estimates; underestimation can merge distinct sources. ME-ICA validation supports TE-dependence as a physically motivated classifier, but does not make any PCA criterion a universal ground truth.

## Decision Gate

Do not choose a criterion from tSNR or component count alone. Review `paired_methods.tsv`, the largest rejected components in `review_manifest.tsv`, and task-model safety checks before changing production. A cohort-wide change should use one prespecified rule rather than choosing a different criterion after inspecting each run.

## Primary References

- [TEDANA denoising approach and PCA criteria](https://tedana.readthedocs.io/en/26.0.3/approach.html)
- [Li, Adalı, and Calhoun (2007), model-order estimation](https://doi.org/10.1002/hbm.20359)
- [Kundu et al. (2013), integrated multi-echo denoising](https://doi.org/10.1073/pnas.1301725110)
- [Gonzalez-Castillo et al. (2016), task ME-ICA evaluation](https://doi.org/10.1016/j.neuroimage.2016.07.039)
- [Ciric et al. (2017), denoising benchmarks and degrees-of-freedom trade-offs](https://doi.org/10.1016/j.neuroimage.2017.03.020)
