import os

def create_key(template, outtype=('nii.gz',), annotation_classes=None):
        if template is None or not template:
                raise ValueError('Template must be a valid format string')
        return template, outtype, annotation_classes

def infotodict(seqinfo):
    t1w = create_key('sub-{subject}/{session}/anat/sub-{subject}_{session}_T1w')
    mag = create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-bold_magnitude')
    phase = create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-bold_phasediff')
    t2_flair = create_key('sub-{subject}/{session}/anat/sub-{subject}_{session}_FLAIR')
    trust_mag = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-trust_run-{item:d}_part-mag_bold')
    trust_phase = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-trust_run-{item:d}_part-phase_bold')
    trust_sbref = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-trust_run-{item:d}_sbref')
    sharedreward_mag = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-sharedreward_run-{item:d}_part-mag_bold')
    sharedreward_phase = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-sharedreward_run-{item:d}_part-phase_bold')
    sharedreward_sbref = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-sharedreward_run-{item:d}_sbref')
    srSocial_mag = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-socialdoors_run-{item:d}_part-mag_bold')
    srSocial_phase = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-socialdoors_run-{item:d}_part-phase_bold')
    srSocial_sbref = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-socialdoors_run-{item:d}_sbref')
    srDoors_mag = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-doors_run-{item:d}_part-mag_bold')
    srDoors_phase = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-doors_run-{item:d}_part-phase_bold')
    srDoors_sbref = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-doors_run-{item:d}_sbref')
    UGR_mag = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-ugr_run-{item:d}_part-mag_bold')
    UGR_phase = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-ugr_run-{item:d}_part-phase_bold')
    UGR_sbref = create_key('sub-{subject}/{session}/func/sub-{subject}_{session}_task-ugr_run-{item:d}_sbref')
    dwi = create_key('sub-{subject}/{session}/dwi/sub-{subject}_{session}_dwi')
    dwi_pa = create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-dwi_dir-PA_epi')
    dwi_ap = create_key('sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-dwi_dir-AP_epi')

    info = {t1w: [],
            mag: [], phase: [],
            dwi: [], dwi_pa: [], dwi_ap: [],
            t2_flair: [],
            trust_mag: [], trust_phase: [], trust_sbref: [],
            sharedreward_mag: [], sharedreward_phase: [], sharedreward_sbref: [],
            srSocial_mag: [], srSocial_phase: [], srSocial_sbref: [],
            srDoors_mag: [], srDoors_phase: [], srDoors_sbref: [],
            UGR_mag: [], UGR_phase: [], UGR_sbref: []}
    
    list_of_ids = [s.series_id for s in seqinfo]

    for s in seqinfo:

        # anatomicals and standard fmaps
        if ('T1w-anat_mpg_07sag_iso' in s.protocol_name):
            info[t1w] = [s.series_id]
        if ('gre_field' in s.protocol_name):
            info[mag] = [s.series_id]
        if ('gre_field' in s.protocol_name) and ('P' in s.image_type):
            info[phase] = [s.series_id]
        if ('t2_tse_dark-fluid_tra_p3' in s.protocol_name) and (s.dim3 == 47):
            info[t2_flair] = [s.series_id]

        # diffusion images and se fmaps
        if ('cmrr_fieldmapse_ap' in s.protocol_name) and (s.dim4 == 2):
            info[dwi_ap] = [s.series_id]
        if ('cmrr_fieldmapse_pa' in s.protocol_name) and (s.dim4 == 2):
            info[dwi_pa] = [s.series_id]
        if ('cmrr_mb3hydi_ipat2_64ch' in s.protocol_name) and (s.dim4 == 145):
            info[dwi] = [s.series_id]


        # functionals: mag, phase, and sbref
        if (s.dim4 == 1120) and ('Trust' in s.series_description) and ('_Pha' not in s.series_description):
            info[trust_mag].append(s.series_id)
            idx = list_of_ids.index(s.series_id)
            info[trust_sbref].append(list_of_ids[idx -2])
        if (s.dim4 == 1120) and ('Trust' in s.series_description) and ('TR1615_Pha' in s.series_description):
            info[trust_phase].append(s.series_id)

        if (s.dim4 == 1020) and ('Shared' in s.protocol_name) and ('_Pha' not in s.series_description):
            info[sharedreward_mag].append(s.series_id)
            idx = list_of_ids.index(s.series_id)
            info[sharedreward_sbref].append(list_of_ids[idx -2])
        if (s.dim4 == 1020) and ('Shared' in s.protocol_name) and ('TR1615_Pha' in s.series_description):
            info[sharedreward_phase].append(s.series_id)


        if (s.dim4 == 872) and ('SocialDoors_face' in s.series_description) and ('_Pha' not in s.series_description):
            info[srSocial_mag] = [s.series_id]
            idx = list_of_ids.index(s.series_id)
            info[srSocial_sbref].append(list_of_ids[idx -2])
        if (s.dim4 == 872) and ('SocialDoors_face' in s.series_description) and ('TR1615_Pha' in s.series_description):
            info[srSocial_phase] = [s.series_id]

        if (s.dim4 == 872) and ('SocialDoors_doors' in s.series_description) and ('_Pha' not in s.series_description):
            info[srDoors_mag] = [s.series_id]
            idx = list_of_ids.index(s.series_id)
            info[srDoors_sbref].append(list_of_ids[idx -2])
        if (s.dim4 == 872) and ('SocialDoors_doors' in s.series_description) and ('TR1615_Pha' in s.series_description):
            info[srDoors_phase] = [s.series_id]


        if (s.dim4 == 960) and ('UGR' in s.series_description) and ('_Pha' not in s.series_description):
            info[UGR_mag].append(s.series_id)
            idx = list_of_ids.index(s.series_id)
            info[UGR_sbref].append(list_of_ids[idx -2])
        if (s.dim4 == 960) and ('UGR' in s.series_description) and ('TR1615_Pha' in s.series_description):
            info[UGR_phase].append(s.series_id)



    return info

POPULATE_INTENDED_FOR_OPTS = {
                'matching_parameters': ['ModalityAcquisitionLabel'],
                'criterion': 'Closest'
}

