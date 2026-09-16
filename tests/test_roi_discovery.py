import pickle
from pathlib import Path

import numpy as np
import pytest

import MEDiml
from MEDiml.biomarkers.BatchExtractor import BatchExtractor
from MEDiml.MEDscan import MEDscan

DEMO_NPY = Path("notebooks/demo/data/Glioma-TCGA-02-0003__T1.MRscan.npy")
DEMO_SETTINGS = Path("notebooks/demo/settings/Extraction_Glioma.json")

pytestmark = pytest.mark.skipif(
    not DEMO_NPY.exists(), reason="the demo MEDscan fixture is not available")


def load_demo_medscan() -> MEDscan:
    with open(DEMO_NPY, "rb") as f:
        return MEDiml.MEDscan(pickle.load(f))


def init_demo_medscan() -> MEDscan:
    medscan = load_demo_medscan()
    medscan.init_params(MEDiml.utils.json_utils.load_json(DEMO_SETTINGS))
    return medscan


# --------------------------------------------------------------------------------------
# MEDscan.data.ROI helpers
# --------------------------------------------------------------------------------------

def test_get_roi_names_is_ordered_by_key():
    assert load_demo_medscan().data.ROI.get_roi_names() == ["ET", "ED", "NET"]


def test_get_union_roi_name():
    assert load_demo_medscan().data.ROI.get_union_roi_name() == "{ET}+{ED}+{NET}"


def test_rois_without_valid_indexes_are_excluded():
    # A failed DICOM rasterization is stored as NaN, such ROIs must not be used.
    medscan = load_demo_medscan()
    medscan.data.ROI.update_indexes(key=1, indexes=np.NaN)

    assert medscan.data.ROI.get_roi_names() == ["ET", "NET"]
    assert medscan.data.ROI.get_union_roi_name() == "{ET}+{NET}"
    assert medscan.data.ROI.get_roi_names(exclude_invalid=False) == ["ET", "ED", "NET"]


def test_roi_names_are_sorted_numerically():
    roi = MEDscan.data.ROI()
    for key in [0, 1, 2, 10]:
        roi.update_roi_name(key=key, roi_name=f"R{key}")
        roi.update_indexes(key=key, indexes=(np.array([key]),))

    # Sorting the stringified keys as text would give R0, R1, R10, R2.
    assert roi.get_roi_names() == ["R0", "R1", "R2", "R10"]


def test_name_set_does_not_alias_roi_names():
    roi = MEDscan.data.ROI(roi_names={"0": "ET"})
    roi.update_name_set(key=0, name_set="T1")

    assert roi.roi_names == {"0": "ET"}


def test_get_roi_names_of_a_scan_without_roi():
    assert MEDscan.data.ROI().get_roi_names() == []
    assert MEDscan.data.ROI().get_union_roi_name() == ""


# --------------------------------------------------------------------------------------
# get_roi_from_indexes
# --------------------------------------------------------------------------------------

def test_auto_union_matches_the_explicit_union():
    vol_auto, roi_auto = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi=None, box_string="full")
    vol_explicit, roi_explicit = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi="{ET}+{ED}+{NET}", box_string="full")

    assert np.array_equal(roi_auto.data, roi_explicit.data)
    assert np.array_equal(vol_auto.data, vol_explicit.data)


def test_auto_union_is_larger_than_a_single_roi():
    _, roi_union = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi=None, box_string="full")
    _, roi_single = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi="{ET}", box_string="full")

    assert roi_union.data.sum() > roi_single.data.sum()


def test_an_empty_roi_name_also_triggers_the_union():
    _, roi_empty = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi="  ", box_string="full")
    _, roi_auto = MEDiml.processing.get_roi_from_indexes(
        init_demo_medscan(), name_roi=None, box_string="full")

    assert np.array_equal(roi_empty.data, roi_auto.data)


def test_an_unknown_roi_name_raises():
    # It used to silently fall back on the first ROI of the scan.
    with pytest.raises(ValueError, match="was not found"):
        MEDiml.processing.get_roi_from_indexes(
            init_demo_medscan(), name_roi="{DOES_NOT_EXIST}", box_string="full")


def test_a_scan_without_roi_raises():
    medscan = init_demo_medscan()
    medscan.data.ROI.roi_names = {}

    with pytest.raises(ValueError, match="no usable ROI"):
        MEDiml.processing.get_roi_from_indexes(medscan, name_roi=None, box_string="full")


# --------------------------------------------------------------------------------------
# BatchExtractor scan discovery
# --------------------------------------------------------------------------------------

def make_extractor(path_read, **kwargs) -> BatchExtractor:
    return BatchExtractor(
        path_read=path_read,
        path_params=DEMO_SETTINGS,
        path_save=path_read,
        **kwargs)


def discover(extractor) -> list:
    scans = extractor._BatchExtractor__discover_scans()
    return sorted(zip(scans["patient_ids"], scans["sequences"], scans["modalities"]))


def test_discover_npy_scans(tmp_path):
    for name in ["P1__T1.MRscan.npy", "P2__CT.CTscan.npy"]:
        (tmp_path / name).touch()
    # Must be ignored: the tables saved by a previous extraction.
    (tmp_path / "radiomics__T1(GTV)__image.npy").touch()
    (tmp_path / "features(GTV)").mkdir()
    (tmp_path / "features(GTV)" / "P1__T1.MRscan.npy").touch()

    assert discover(make_extractor(tmp_path)) == [
        ("P1", "T1", "MRscan"), ("P2", "CT", "CTscan")]


def test_discover_npy_scans_is_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "P1__T1.MRscan.npy").touch()

    assert discover(make_extractor(tmp_path)) == [("P1", "T1", "MRscan")]


def test_discover_nifti_scans_deduplicates_the_roi_copies(tmp_path):
    # The image is duplicated once per ROI, only one scan must be discovered.
    for roi in ["ET", "ED"]:
        (tmp_path / f"P1__T1({roi}).MRscan.nii.gz").touch()
        (tmp_path / f"P1__T1({roi}).ROI.nii.gz").touch()

    assert discover(make_extractor(tmp_path, use_niftis=True)) == [("P1", "T1", "MRscan")]


def test_discover_nifti_scans_reads_plain_nii(tmp_path):
    (tmp_path / "P1__T1(ET).MRscan.nii").touch()
    (tmp_path / "P1__T1(ET).ROI.nii").touch()

    assert discover(make_extractor(tmp_path, use_niftis=True)) == [("P1", "T1", "MRscan")]


def test_discover_raises_when_nothing_is_found(tmp_path):
    with pytest.raises(ValueError, match="No scan was found"):
        discover(make_extractor(tmp_path))


def test_batch_extractor_rejects_the_legacy_argument_order(tmp_path):
    # path_csv used to be the second positional argument.
    with pytest.raises(ValueError, match="arguments order has changed"):
        BatchExtractor(tmp_path, tmp_path / "roiNames_GTV.csv", tmp_path)


def test_roi_types_default_when_missing_from_the_settings(tmp_path):
    (tmp_path / "P1__T1.MRscan.npy").touch()
    extractor = make_extractor(tmp_path)
    extractor._BatchExtractor__load_and_process_params()

    assert extractor.roi_types == ["all"]
    assert extractor.roi_type_labels == ["ROI"]
