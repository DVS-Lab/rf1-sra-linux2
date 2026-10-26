# Methods

Raw BIDS filenames were indexed with PyBIDS. Scanner metadata was read from per-build cached JSON sidecars following BIDS ancestor-directory inheritance, without building a full metadata database. Multiple applicable sidecars at one directory level are flagged as ambiguous rather than selected arbitrarily. BOLD, T1w and T2w magnitude images were matched to MRIQC IQM JSONs by exact BIDS entities. Sessions and run numbers were never inferred. Each echo remains a separate image. Phase/real/imaginary images are listed but not used for these IQMs.

MRIQC values retain their own processing-stage meaning; they are not metrics of final fMRIPrep/FEAT images. FWHM is converted from voxel units independently for each axis using MRIQC spacing, then averaged arithmetically in mm (not geometric combined FWHM). Missing spacing produces missing mm FWHM, not a guessed conversion.

Review fences use linear quartiles and 1.5 times the IQR, with at least 5 valid observations. All metrics are evaluated independently in one pass; flagged images are not removed before estimating another fence. Groups with zero IQR or insufficient observations are not classified. Smoothness is descriptive by default. No participant exclusions or selected-cohort files are generated.

Software labels default to exact header strings. User-supplied exact aliases, additional grouping fields and metric directions are saved in config.json. No scanner-era inference from acquisition dates is performed. Unknown metadata remains visible.

References: [MRIQC IQMs](https://mriqc.readthedocs.io/en/stable/iqms/bold.html); [MRIQC](https://doi.org/10.1371/journal.pone.0184661); [PyBIDS](https://bids-standard.github.io/pybids/).

## Presentation-only refresh

Plots were regenerated from the verified saved tables, showing smoothness, tSNR and mean FD where applicable. Tables, thresholds, flags and validation state were copied unchanged. Live imaging inputs were not checked again. Original analysis provenance is saved in source_provenance.json.
