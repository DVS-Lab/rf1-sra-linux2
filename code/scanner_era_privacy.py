"""Privacy-safe parameter allowlists for tracked scanner-era QC outputs."""

from __future__ import annotations


DICOM_SAFE_KEYWORDS = frozenset(
    {
        "AcquisitionContrast", "AcquisitionDuration", "AcquisitionMatrix", "AngioFlag",
        "BitsAllocated", "BitsStored", "BloodSignalNulling", "Columns",
        "ComplexImageComponent", "EchoNumbers", "EchoPlanarPulseSequence",
        "EchoPulseSequence", "EchoTime", "EchoTrainLength", "FlipAngle",
        "FlowCompensation", "FrameAcquisitionDuration", "FrameType",
        "GeometryOfKSpaceTraversal", "GradientEchoTrainLength", "HighBit", "ImageType",
        "ImagedNucleus", "ImagingFrequency", "InPlanePhaseEncodingDirection",
        "InversionRecovery", "KSpaceFiltering", "LossyImageCompression",
        "MRAcquisitionFrequencyEncodingSteps", "MRAcquisitionPhaseEncodingStepsInPlane",
        "MRAcquisitionType", "MagneticFieldStrength", "MagnetizationTransfer",
        "Manufacturer", "ManufacturerModelName", "Modality", "MultiPlanarExcitation",
        "NumberOfAverages", "NumberOfFrames", "NumberOfKSpaceTrajectories",
        "NumberOfPhaseEncodingSteps", "NumberOfTemporalPositions", "OperatingMode",
        "OperatingModeType", "OversamplingPhase", "ParallelAcquisition",
        "ParallelAcquisitionTechnique", "ParallelReductionFactorInPlane",
        "ParallelReductionFactorOutOfPlane", "PartialFourier", "PartialFourierDirection",
        "PercentPhaseFieldOfView", "PercentSampling", "PhaseContrast",
        "PhotometricInterpretation", "PixelBandwidth", "PixelRepresentation",
        "PixelSpacing", "PulseSequenceName", "RFEchoTrainLength",
        "RectilinearPhaseEncodeReordering", "RepetitionTime", "RescaleIntercept",
        "RescaleSlope", "RescaleType", "Rows", "SAR", "SamplesPerPixel",
        "SaturationRecovery", "ScanOptions", "ScanningSequence",
        "SegmentedKSpaceTraversal", "SequenceName", "SequenceVariant", "SliceThickness",
        "SoftwareVersions", "SpacingBetweenSlices", "SpatialPresaturation",
        "SpectrallySelectedExcitation", "SpectrallySelectedSuppression", "Spoiling",
        "SteadyStatePulseSequence", "T2Preparation", "Tagging", "TransmitterFrequency",
        "VariableFlipAngleFlag", "VolumeBasedCalculationTechnique",
        "VolumetricProperties",
    }
)

PROTOCOL_EXCEPTION_PARAMETERS = frozenset(
    {
        "AcquisitionMatrixPE", "EchoTime", "EffectiveEchoSpacing", "FlipAngle",
        "ImageType", "ImageTypeText", "MagneticFieldStrength",
        "ManufacturersModelName", "MultibandAccelerationFactor",
        "NonlinearGradientCorrection", "PhaseEncodingDirection", "PhaseEncodingSteps",
        "ReconMatrixPE", "RepetitionTime", "SliceThickness", "SoftwareVersions",
        "SpacingBetweenSlices", "TotalReadoutTime",
    }
)
