import argparse
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import List, Union

import pydicom
import pydicom.misc
from tqdm import tqdm

# Imaging modalities handled by MEDiml, all the other DICOM files (RTSTRUCT, RTDOSE...)
# are associated to the imaging scan they reference.
IMAGING_MODALITIES = ['MR', 'PT', 'CT', 'ADC']


def sanitize_name(name: str) -> str:
    """Removes the characters that cannot be used in a folder name or in a MEDiml name.

    Args:
        name(str): Name to sanitize.

    Returns:
        str: The sanitized name.
    """
    name = re.sub(r'[\\/:*?"<>|()&_\s]+', '-', str(name).strip())
    return name.strip('-.') or 'Unknown'


def is_organized(path_dataset: Path, dicom_files: List[Path]) -> bool:
    """Checks if the dataset is already organized as "path_dataset/PatientID/ImagingScanName/DICOM files"
    with a single imaging series per scan folder.

    Args:
        path_dataset(Path): Path to the dataset.
        dicom_files(List[Path]): All the DICOM files of the dataset.

    Returns:
        bool: True if the dataset is already organized.
    """
    series_per_folder = defaultdict(set)
    for file in dicom_files:
        # MEDiml only reads the DICOM files with a ".dcm" extension
        if len(file.relative_to(path_dataset).parts) != 3 or file.suffix != '.dcm':
            return False
        header = pydicom.dcmread(str(file), stop_before_pixels=True, force=True)
        if str(getattr(header, 'Modality', '')) in IMAGING_MODALITIES:
            series_per_folder[file.parent].add(header.SeriesInstanceUID)
    return all(len(series) == 1 for series in series_per_folder.values())


def get_referenced_series_uid(header: pydicom.Dataset) -> Union[str, None]:
    """Returns the Series Instance UID of the imaging scan referenced by an RTSTRUCT file.

    Args:
        header(pydicom.Dataset): Header of the RTSTRUCT file.

    Returns:
        Union[str, None]: The referenced Series Instance UID, None if not found.
    """
    try:
        return header.ReferencedFrameOfReferenceSequence[
            0].RTReferencedStudySequence[
            0].RTReferencedSeriesSequence[
            0].SeriesInstanceUID
    except (AttributeError, IndexError):
        return None


def get_frame_of_reference_uid(header: pydicom.Dataset) -> Union[str, None]:
    """Returns the Frame of Reference UID of a DICOM file.

    Args:
        header(pydicom.Dataset): Header of the DICOM file.

    Returns:
        Union[str, None]: The Frame of Reference UID, None if not found.
    """
    if 'FrameOfReferenceUID' in header:
        return header.FrameOfReferenceUID
    try:
        return header.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID
    except (AttributeError, IndexError):
        return None


def organize(path_save: Path, dicom_files: List[Path]) -> None:
    """Copies all the DICOM files of the dataset in "path_save/PatientID/ImagingScanName/",
    one folder per imaging scan (Series Instance UID). The non-imaging files (RTSTRUCT...)
    are copied in the folder of the imaging scan they reference.

    Args:
        path_save(Path): Path where to save the organized dataset.
        dicom_files(List[Path]): All the DICOM files of the dataset.

    Returns:
        None.
    """
    images = defaultdict(list)  # Series Instance UID -> DICOM files
    series_info = {}            # Series Instance UID -> (PatientID, scan name, Frame of Reference UID)
    others = []                 # (DICOM file, header) of the non-imaging files
    print('--> Reading all the DICOM headers')
    for file in tqdm(dicom_files):
        try:
            header = pydicom.dcmread(str(file), stop_before_pixels=True, force=True)
        except Exception as e:
            print(f'Error while reading: {file}, error: {e}')
            continue
        modality = str(getattr(header, 'Modality', ''))
        if modality in IMAGING_MODALITIES:
            series_uid = header.SeriesInstanceUID
            images[series_uid].append(file)
            if series_uid not in series_info:
                scan_name = getattr(header, 'SeriesDescription', '') or modality
                series_info[series_uid] = (
                    sanitize_name(getattr(header, 'PatientID', '') or 'Unknown'),
                    sanitize_name(scan_name),
                    get_frame_of_reference_uid(header)
                )
        else:
            others.append((file, header))

    # Name the scan folders, a number is added if a patient has many scans with the same name
    scan_dirs = {}
    names_used = defaultdict(int)
    for series_uid, (patient_id, scan_name, _) in sorted(series_info.items(), key=lambda x: x[1][:2]):
        names_used[(patient_id, scan_name)] += 1
        count = names_used[(patient_id, scan_name)]
        folder_name = scan_name if count == 1 else f'{scan_name}-{count}'
        scan_dirs[series_uid] = path_save / patient_id / folder_name

    # Associate the non-imaging files to their imaging scan
    files_to_copy = [(file, scan_dirs[uid]) for uid, files in images.items() for file in files]
    for file, header in others:
        series_uid = get_referenced_series_uid(header)
        if series_uid not in scan_dirs:
            # Fall back on the Frame of Reference UID, only if it identifies a single scan
            frame_uid = get_frame_of_reference_uid(header)
            matches = [uid for uid, info in series_info.items() if frame_uid and info[2] == frame_uid]
            series_uid = matches[0] if len(matches) == 1 else None
        if series_uid is None:
            print(f'Could not associate {file} ({getattr(header, "Modality", "Unknown modality")}) '
                  'to a single imaging scan, it will be ignored.')
            continue
        files_to_copy.append((file, scan_dirs[series_uid]))

    # Copy the files, named after their SOP Instance UID with a ".dcm" extension (required by MEDiml)
    print(f'--> Copying the DICOM files of {len(scan_dirs)} imaging scan(s) to {path_save}')
    for file, scan_dir in tqdm(files_to_copy):
        scan_dir.mkdir(parents=True, exist_ok=True)
        header = pydicom.dcmread(str(file), stop_before_pixels=True, force=True)
        name = getattr(header, 'SOPInstanceUID', '') or file.stem
        shutil.copy2(file, scan_dir / f'{name}.dcm')


def update_headers(path_dataset: Path) -> None:
    """Updates the PatientID and the SeriesDescription of all the DICOM files of an organized dataset
    using the names of the patient and imaging scan folders.

    Args:
        path_dataset(Path): Path to the organized dataset.

    Returns:
        None.
    """
    print('--> Updating the DICOM headers')
    for folder_patient_id in sorted(f for f in path_dataset.iterdir() if f.is_dir()):
        for folder_imaging_scan in sorted(f for f in folder_patient_id.iterdir() if f.is_dir()):
            for file in folder_imaging_scan.glob('*.dcm'):
                dicom_header = pydicom.dcmread(str(file))
                dicom_header.PatientID = os.path.basename(folder_patient_id)
                if 'SeriesDescription' in dicom_header:
                    dicom_header.SeriesDescription = os.path.basename(folder_imaging_scan)
                dicom_header.save_as(str(file))


def main(path_dataset: Union[str, Path], path_save: Union[str, Path] = None) -> None:
    """Process the dataset to follow the MEDiml conventions:
    "dataset_folder/PatientID/ImagingScanName/*.dcm".

    If the dataset is not organized yet, the files are copied (the original dataset is not modified)
    in ``path_save`` following this structure. The PatientID and SeriesDescription fields of the
    DICOM headers are then updated using the names of the patient and imaging scan folders.

    Args:
        path_dataset(Union[str, Path]): Path to the dataset.
        path_save(Union[str, Path], optional): Path where to save the organized dataset. Only used if the
            dataset is not organized. Defaults to "<path_dataset>_organized".

    Returns:
        None.
    """
    path_dataset = Path(path_dataset)
    if not path_dataset.is_dir():
        raise ValueError(f'The dataset folder does not exist: {path_dataset}')
    dicom_files = sorted(f for f in path_dataset.rglob('*') if f.is_file() and pydicom.misc.is_dicom(f))
    if not dicom_files:
        raise ValueError(f'No DICOM file was found in: {path_dataset}')

    if is_organized(path_dataset, dicom_files):
        print(f'--> The dataset is already organized: {path_dataset}')
        path_organized = path_dataset
    else:
        path_organized = Path(path_save) if path_save else path_dataset.with_name(path_dataset.name + '_organized')
        if path_organized.exists() and any(path_organized.iterdir()):
            raise ValueError(f'The save folder is not empty: {path_organized}')
        organize(path_organized, dicom_files)

    update_headers(path_organized)
    print(f'DONE, the organized dataset is in: {path_organized}')


if __name__ == "__main__":
    # setting up arguments:
    parser = argparse.ArgumentParser(description='Re-organize dataset to follow MEDiml package conventions.')
    parser.add_argument("--path-dataset", required=True, help="Path to your dataset folder.")
    parser.add_argument("--path-save", required=False, default=None,
                        help="Path where to save the organized dataset (if not organized yet). "
                             "Defaults to '<path-dataset>_organized'.")
    args = parser.parse_args()

    # main
    main(args.path_dataset, args.path_save)
