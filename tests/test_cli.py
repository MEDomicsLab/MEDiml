from unittest.mock import patch

import pytest

from radiomics import build_parser, main


def test_cli_defaults_to_niftis_and_forwards_arguments_to_batch_extractor():
    with patch("radiomics._get_batch_extractor") as get_batch_extractor_mock:
        batch_extractor_mock = get_batch_extractor_mock.return_value
        instance = batch_extractor_mock.return_value

        main([
            "input_dir",
            "settings.json",
            "output_dir",
            "--n-batch",
            "8",
            "--skip-existing",
        ])

        get_batch_extractor_mock.assert_called_once()
        batch_extractor_mock.assert_called_once()
        _, kwargs = batch_extractor_mock.call_args
        assert str(kwargs["path_read"]) == "input_dir"
        assert kwargs["path_csv"] is None
        assert str(kwargs["path_params"]) == "settings.json"
        assert str(kwargs["path_save"]) == "output_dir"
        assert kwargs["n_batch"] == 8
        assert kwargs["use_niftis"] is True
        assert kwargs["use_dicoms"] is False
        assert kwargs["skip_existing"] is True
        instance.compute_radiomics.assert_called_once()


def test_cli_forwards_dicom_selection_to_batch_extractor():
    with patch("radiomics._get_batch_extractor") as get_batch_extractor_mock:
        batch_extractor_mock = get_batch_extractor_mock.return_value
        instance = batch_extractor_mock.return_value

        main([
            "input_dir",
            "settings.json",
            "output_dir",
            "--use-dicoms",
        ])

        batch_extractor_mock.assert_called_once()
        _, kwargs = batch_extractor_mock.call_args
        assert kwargs["use_niftis"] is False
        assert kwargs["use_dicoms"] is True
        instance.compute_radiomics.assert_called_once()


def test_cli_forwards_optional_path_csv():
    with patch("radiomics._get_batch_extractor") as get_batch_extractor_mock:
        batch_extractor_mock = get_batch_extractor_mock.return_value

        main([
            "input_dir",
            "settings.json",
            "output_dir",
            "--path-csv",
            "roi_mapping.csv",
        ])

        _, kwargs = batch_extractor_mock.call_args
        assert str(kwargs["path_csv"]) == "roi_mapping.csv"


def test_cli_rejects_legacy_positional_csv():
    # The ROI CSV file used to be the second positional argument, it is now a flag.
    with pytest.raises(SystemExit):
        build_parser().parse_args([
            "input_dir",
            "roi_mapping.csv",
            "settings.json",
            "output_dir",
        ])
