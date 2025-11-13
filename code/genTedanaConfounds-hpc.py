#!/usr/bin/env python

import matplotlib.pyplot as plt
import os
import pandas as pd
from natsort import natsorted
import re
import numpy as np

# Comment out fmriprep and tedana 24 or 25, depending on what to run

fmriprep_dir = '../derivatives/fmriprep-24/'
tedana_dir = '../derivatives/tedana-24/'

#fmriprep_dir = '../derivatives/fmriprep-25/'
#tedana_dir = '../derivatives/tedana-25/'

metric_files = natsorted([
    os.path.join(root, f)
    for root, dirs, files in os.walk(tedana_dir)
    for f in files
    if f.endswith("tedana_metrics.tsv")
])

for file in metric_files:
    base = re.search("(.*)tedana_metrics", file).group(1)
    run = re.search("run-(.*)_desc-tedana", file).group(1)
    sub = re.search(r"/(sub-\d{5})/ses-\d{2}/", file).group(1)
    task = re.search(r"_task-(.*?)_", file).group(1)
    ses = re.search(r"_ses-(\d{2})_", file).group(1)

    fmriprep_fname = (
        f"{fmriprep_dir}{sub}/ses-{ses}/func/"
        f"{sub}_ses-{ses}_task-{task}_run-{run}_part-mag_desc-confounds_timeseries.tsv"
    )

    if os.path.exists(fmriprep_fname):
        print(f"Making Confounds: {sub} ses-{ses} run-{run} task-{task}")
        fmriprep_confounds = pd.read_csv(fmriprep_fname, sep='\t')
        ICA_mixing = pd.read_csv(f'{base}ICA_mixing.tsv', sep='\t')
        metrics = pd.read_csv(f'{base}tedana_metrics.tsv', sep='\t')

        try:
            rejected_components = metrics.loc[metrics['classification'] == 'rejected', 'Component']
            rejected_indices = rejected_components.str.replace('ICA_', '', regex=False).astype(int)
            bad_components = ICA_mixing.iloc[:, rejected_indices]
        except Exception as e:
            print(f"Warning: could not extract rejected components for {sub} ses-{ses} run-{run} — {e}")
            bad_components = pd.DataFrame()

        aCompCor = [
            'a_comp_cor_00',
            'a_comp_cor_01',
            'a_comp_cor_02',
            'a_comp_cor_03',
            'a_comp_cor_04',
            'a_comp_cor_05'
        ]
        cosine = [col for col in fmriprep_confounds if col.startswith('cosine')]
        NSS = [col for col in fmriprep_confounds if col.startswith('non_steady_state')]
        motion = ['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z']
        fd = ['framewise_displacement']

        desired_cols = np.concatenate([aCompCor, cosine, NSS, motion, fd])
        filter_col = [c for c in desired_cols if c in fmriprep_confounds.columns]
        fmriprep_confounds = fmriprep_confounds[filter_col]

        fmriprep_confounds.fillna(0, inplace=True)

        tedana_confounds = pd.concat([bad_components], axis=1)
        confounds_df = pd.concat([fmriprep_confounds, tedana_confounds], axis=1)

        outdir = (
            f"{tedana_dir}../fsl/"
            f"confounds_{os.path.basename(os.path.normpath(tedana_dir))}/{sub}"
        )
        os.makedirs(outdir, exist_ok=True)
        outfname = (
            f"{outdir}/"
            f"{sub}_ses-{ses}_task-{task}_run-{run}_desc-TedanaPlusConfounds.tsv"
        )
        confounds_df.to_csv(outfname, index=False, header=False, sep='\t')
    else:
        print(f"fmriprep failed for {sub} ses-{ses} run-{run} task-{task}")

