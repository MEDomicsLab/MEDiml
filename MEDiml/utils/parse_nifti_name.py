#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import Tuple, Union

NIFTI_EXTENSIONS = ('.nii.gz', '.nii')


def strip_nifti_extension(file_name: Union[Path, str]) -> str:
    """Removes the NIfTI extension from a file name.

    Handles both ``.nii`` and ``.nii.gz``. Any other name is returned unchanged.

    Args:
        file_name(Union[Path, str]): Name or path of a NIfTI file.

    Returns:
        str: The file name without its directory and without the NIfTI extension.

    Examples:
        >>> strip_nifti_extension('STS-McGill-001__T1(GTV).MRscan.nii.gz')
        'STS-McGill-001__T1(GTV).MRscan'
        >>> strip_nifti_extension('STS-McGill-001__T1(GTV).MRscan.nii')
        'STS-McGill-001__T1(GTV).MRscan'
    """
    name = Path(file_name).name
    for extension in NIFTI_EXTENSIONS:
        if name.endswith(extension):
            return name[:-len(extension)]

    return name


def is_nifti_file(file_name: Union[Path, str]) -> bool:
    """Checks whether the given name is a NIfTI file name (``.nii`` or ``.nii.gz``).

    Args:
        file_name(Union[Path, str]): Name or path of a file.

    Returns:
        bool: True if the name ends with a NIfTI extension.
    """
    return Path(file_name).name.endswith(NIFTI_EXTENSIONS)


def is_roi_file(file_name: Union[Path, str]) -> bool:
    """Checks whether the given NIfTI file is an ROI mask file.

    A mask file is identified by a ``ROI`` component in the dot-separated name,
    e.g. ``STS-McGill-001__T1(GTV).ROI.nii.gz``.

    Args:
        file_name(Union[Path, str]): Name or path of a NIfTI file.

    Returns:
        bool: True if the file is an ROI mask file.
    """
    return 'ROI' in Path(file_name).name.split('.')


def parse_nifti_name(file_name: Union[Path, str]) -> Tuple[str, str, str, str]:
    """Splits a MEDiml NIfTI file name into its components.

    The expected naming convention is
    ``{PatientID}__{ImagingScanName}({ROIname}).{ImagingModality}.nii[.gz]`` for an
    imaging volume and ``{PatientID}__{ImagingScanName}({ROIname}).ROI.nii[.gz]`` for
    the associated mask.

    Args:
        file_name(Union[Path, str]): Name or path of a NIfTI file.

    Returns:
        4-element tuple containing

        - str: patient_id, empty if the name has no ``__`` separator.
        - str: scan_name (the imaging scan name), empty if the name has no ``__`` separator.
        - str: roi_name, empty if the name carries no ``(...)`` group.
        - str: modality, ``'ROI'`` for a mask file and empty if the name has no \
            modality component.

    Examples:
        >>> parse_nifti_name('STS-McGill-001__T1(GTV).MRscan.nii')
        ('STS-McGill-001', 'T1', 'GTV', 'MRscan')
        >>> parse_nifti_name('STS-McGill-001__T1(GTV).ROI.nii.gz')
        ('STS-McGill-001', 'T1', 'GTV', 'ROI')
        >>> parse_nifti_name('STS-McGill-001__T1.CTscan.nii')
        ('STS-McGill-001', 'T1', '', 'CTscan')
    """
    stem = strip_nifti_extension(file_name)

    # The modality is the last dot-separated component. `rsplit` (and not `split`) is
    # used because an imaging scan name may itself contain a dot.
    if '.' in stem:
        head, modality = stem.rsplit('.', 1)
    else:
        head, modality = stem, ''

    # The ROI name is the text between the first "(" and the first ")".
    ind_start = head.find('(')
    ind_stop = head.find(')')
    if ind_start != -1 and ind_stop > ind_start:
        roi_name = head[ind_start + 1: ind_stop]
    else:
        roi_name = ''

    # The patient ID and the scan name are separated by "__". Note that the patient ID
    # itself may contain single underscores, hence the use of `partition('__')`.
    base = head[:ind_start] if ind_start != -1 else head
    patient_id, separator, scan_name = base.partition('__')
    if not separator:
        patient_id, scan_name = '', base

    return patient_id, scan_name, roi_name, modality
