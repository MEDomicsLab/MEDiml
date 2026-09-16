import nibabel as nib
import numpy as np
import pytest

from MEDiml.MEDscan import MEDscan
from MEDiml.utils.parse_nifti_name import (is_nifti_file, is_roi_file,
                                           parse_nifti_name,
                                           strip_nifti_extension)


@pytest.mark.parametrize("file_name", [
    "STS-McGill-001__T1(GTV).MRscan.nii",
    "STS-McGill-001__T1(GTV).MRscan.nii.gz",
])
def test_parse_nifti_name_supports_both_extensions(file_name):
    # The ".nii" case used to be parsed as ('STS-McGill-001', ..., 'STS-McGill-001__T1(GTV)')
    assert parse_nifti_name(file_name) == ("STS-McGill-001", "T1", "GTV", "MRscan")


def test_parse_nifti_name_of_a_roi_file():
    assert parse_nifti_name("STS-McGill-001__T1(GTV).ROI.nii.gz") == (
        "STS-McGill-001", "T1", "GTV", "ROI")


def test_parse_nifti_name_without_a_roi_group():
    patient_id, scan_name, roi_name, modality = parse_nifti_name("STS-McGill-001__T1.CTscan.nii")
    assert (patient_id, scan_name, modality) == ("STS-McGill-001", "T1", "CTscan")
    assert roi_name == ""


def test_parse_nifti_name_keeps_underscores_of_the_patient_id():
    assert parse_nifti_name("P_A__T1(ET).MRscan.nii")[0] == "P_A"


def test_parse_nifti_name_keeps_dots_of_the_scan_name():
    assert parse_nifti_name("P1__scan.v2(ET).CTscan.nii")[1] == "scan.v2"


def test_is_nifti_file_and_is_roi_file():
    assert is_nifti_file("P1__T1(ET).ROI.nii")
    assert is_nifti_file("P1__T1(ET).ROI.nii.gz")
    assert not is_nifti_file("P1__T1.MRscan.npy")
    assert is_roi_file("P1__T1(ET).ROI.nii.gz")
    assert not is_roi_file("P1__T1(ET).MRscan.nii.gz")


def test_strip_nifti_extension():
    assert strip_nifti_extension("P1__T1(ET).MRscan.nii.gz") == "P1__T1(ET).MRscan"
    assert strip_nifti_extension("P1__T1(ET).MRscan.nii") == "P1__T1(ET).MRscan"


def _write_mask(path, value_index):
    """Writes a tiny NIfTI mask with a single non-zero voxel."""
    data = np.zeros((2, 2, 2))
    data[value_index] = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(data, np.eye(4)), str(path))


def test_get_roi_from_path_is_recursive_and_reads_both_extensions(tmp_path):
    # One mask at the root, one in a sub-folder, one of each extension.
    _write_mask(tmp_path / "P1__T1(ET).ROI.nii.gz", (0, 0, 0))
    _write_mask(tmp_path / "sub" / "P1__T1(ED).ROI.nii", (1, 1, 1))
    # Must be ignored: another patient, and an image (non-ROI) file.
    _write_mask(tmp_path / "P2__T1(ET).ROI.nii.gz", (0, 0, 1))
    _write_mask(tmp_path / "P1__T1(ET).MRscan.nii.gz", (1, 0, 0))

    roi = MEDscan.data.ROI()
    roi.get_roi_from_path(tmp_path, "P1__T1")

    assert sorted(roi.roi_names.values()) == ["ED", "ET"]
    assert roi.get_roi_names() == ["ET", "ED"]
    assert set(roi.nameSet.values()) == {"T1"}
