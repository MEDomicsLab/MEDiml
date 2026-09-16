<div align="center">

<img src="https://github.com/MEDomicsLab/MEDiml/blob/main/docs/figures/MEDimlLogo150.png?raw=true" style="width:150px;"/>

[![PyPI - Python Version](https://img.shields.io/badge/python-3.8%20|%203.9%20|%203.10-blue)](https://www.python.org/downloads/release/python-380/)
[![PyPI - version](https://img.shields.io/badge/pypi-v0.11-blue)](https://pypi.org/project/mediml/)
[![Continuous Integration](https://github.com/MEDomicsLab/MEDiml/actions/workflows/python-app.yml/badge.svg)](https://github.com/MEDomicsLab/MEDiml/actions/workflows/python-app.yml)
[![Documentation Status](https://readthedocs.org/projects/mediml/badge/?version=latest)](https://mediml.readthedocs.io/en/latest/?badge=latest)
[![License: GPL-3](https://img.shields.io/badge/license-GPLv3-blue)](LICENSE)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MEDomicsLab/MEDiml/blob/main/notebooks/tutorial/DataManager-Tutorial.ipynb)

</div>

## Table of Contents
  * [1. Introduction](#1-introduction)
  * [2. Installation](#2-installation)
  * [3. Using MEDiml](#3-using-mediml)
    * [3.1 Using MEDiml through the command line](#31-using-mediml-through-the-command-line)
    * [3.2 Using MEDiml through code](#32-using-mediml-through-code)
  * [4. Tutorials](#4-tutorials)
  * [5. IBSI Standardization](#5-ibsi-standardization)
    * [IBSI Chapter 1](#ibsi-chapter-1)
    * [IBSI Chapter 2](#ibsi-chapter-2)
  * [6. Acknowledgement](#6-acknowledgement)
  * [7. Authors](#7-authors)
  * [8. Statement](#8-statement)

## 1. Introduction
MEDiml is an open-source Python package that can be used for processing multi-modal medical images (MRI, CT or PET) and for extracting their radiomic features. This package is meant to facilitate the processing of medical images and the subsequent computation of all types of radiomic features while maintaining the reproducibility of analyses. This package has been standardized with the [IBSI](https://theibsi.github.io/) norms.

![MEDiml overview](https://raw.githubusercontent.com/MEDomicsLab/MEDiml/main/docs/figures/pakcage-overview.png)


## 2. Installation

### Python installation
The MEDiml package requires *Python 3.8* or more. If you don't have it installed on your machine, follow the instructions [here](https://github.com/MEDomicsLab/MEDiml/blob/main/python.md) to install it.

### Package installation
You can easily install the ``MEDiml`` package from PyPI using:
```
pip install MEDiml
```

For more installation options (Conda, Poetry...) check out the [installation documentation](https://mediml.readthedocs.io/en/latest/Installation.html).

## 3. Using MEDiml
MEDiml can be used either as a command line tool for batch radiomics extraction, or as a Python package that you import directly into your own scripts and notebooks for finer-grained control over the processing and feature extraction pipeline.

### 3.1 Using MEDiml through the command line
After installation, you can launch radiomics extraction directly from the terminal:

```bash
radiomics <path/to/input> <path/to/settings_file> <path/save> --use-niftis --n-batch 4 --skip-existing
```

By default, every scan found in the input folder is processed, and all the ROIs of a scan are
combined into a single region (i.e. `{ROI_1}+{ROI_2}`). To process a specific list of scans and
ROIs instead, pass a [CSV file](https://mediml.readthedocs.io/en/latest/csv_file.html) with the
optional `--path-csv` argument:

```bash
radiomics <path/to/input> <path/to/settings_file> <path/save> --path-csv <path/to/csv_file>
```

The command wraps the existing `BatchExtractor` workflow and selects the appropriate input format automatically. The full list of arguments, required ones first, is described below:

| Argument | Required | Description |
| --- | --- | --- |
| `path_input` | Yes | Path to the [input dataset](https://mediml.readthedocs.io/en/latest/input_data.html) folder containing the scans to process. |
| `path_settings` | Yes | Path to the radiomics [extraction settings file](https://mediml.readthedocs.io/en/latest/configurations_file.html#features-extraction). |
| `path_save` | Yes | Path to the folder where the extracted feature files will be written. |
| `--path-csv` | No | Path to a [CSV file](https://mediml.readthedocs.io/en/latest/csv_file.html) mapping specific scans to specific ROIs (columns: `PatientID`, `ImagingScanName`, `ImagingModality`, `ROIname`). If omitted, every scan found in the input folder is processed and all of its ROIs are combined into a single region. |
| `--use-niftis` | No | Process NIfTI files instead of DICOM files. This is the default behavior and is mutually exclusive with `--use-dicoms`. |
| `--use-dicoms` | No | Process DICOM files instead of NIfTI files. Mutually exclusive with `--use-niftis`. |
| `--n-batch` | No | Number of CPU cores to use for extraction. Defaults to `4`. |
| `--skip-existing` | No | Skip scans whose features already exist in the output folder. |

### 3.2 Using MEDiml through code
```python
import os
import pickle

import MEDiml

# Load MEDiml DataManager
dm = MEDiml.DataManager(path_dicoms=os.getcwd())

# Process the DICOM files and retrieve the MEDiml object
med_obj = dm.process_all_dicoms()[0]

# Extract ROI mask from the object. `name_roi` is optional: when it is omitted,
# the union of all the ROIs found in the object is used.
vol_obj_init, roi_obj_init = MEDiml.processing.get_roi_from_indexes(
            med_obj,
            name_roi='{ED}+{ET}+{NET}',
            box_string='full')

# Extract features from the imaging data
local_intensity = MEDiml.biomarkers.local_intensity.extract_all(
                img_obj=vol_obj_init.data,
                roi_obj=roi_obj_init.data,
                res=[1, 1, 1]
            )

# Update radiomics results class
med_obj.update_radiomics(loc_int_features=local_intensity)

# Saving radiomics results
med_obj.save_radiomics(
                scan_file_name='STS-UdS-001__T1.MRscan.npy',
                path_save=os.getcwd(),
                roi_type='GrossTumorVolume',
                roi_type_label='GTV',
            )
```

## 4. Tutorials

We have created many [tutorial notebooks](https://github.com/MEDomicsLab/MEDiml/tree/main/notebooks) to assist you in learning how to use the different parts of the package. More details can be found in the [documentation](https://mediml.readthedocs.io/en/latest/tutorials.html).

## 5. IBSI Standardization
The image biomarker standardization initiative ([IBSI](https://theibsi.github.io)) is an independent international collaboration that aims to standardize the extraction of image biomarkers from acquired imaging. The IBSI therefore seeks to provide image biomarker nomenclature and definitions, benchmark datasets, and benchmark values to verify image processing and image biomarker calculations, as well as reporting guidelines, for high-throughput image analysis. We participate in this collaboration with our package to make sure it respects international nomenclatures and definitions. The participation was separated into two chapters:

  - ### IBSI Chapter 1
      [The IBSI chapter 1](https://theibsi.github.io/ibsi1/) is dedicated to the standardization of commonly used radiomic features. It was initiated in September 2016 and reached completion in March 2020. We have created two [jupyter notebooks](https://github.com/MEDomicsLab/MEDiml/tree/main/notebooks/ibsi) for each phase of the chapter and made them available for the users to run the IBSI tests for themselves. The tests can also be explored in interactive Colab notebooks that are directly accessible here:
      
      - **Phase 1**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MEDomicsLab/MEDiml/blob/main/notebooks/ibsi/ibsi1p1.ipynb)
      - **Phase 2**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MEDomicsLab/MEDiml/blob/main/notebooks/ibsi/ibsi1p2.ipynb)

  - ### IBSI Chapter 2
      [The IBSI chapter 2](https://theibsi.github.io/ibsi2/) was launched in June 2020 and reached completion in February 2024. It is dedicated to the standardization of commonly used imaging filters in radiomic studies. We have created two [jupyter notebooks](https://github.com/MEDomicsLab/MEDiml/tree/main/notebooks/ibsi) for each phase of the chapter and made them available for the users to run the IBSI tests for themselves and validate image filtering and image biomarker calculations from filter response maps. The tests can also be explored in interactive Colab notebooks that are directly accessible here: 
      
      - **Phase 1**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MEDomicsLab/MEDiml/blob/main/notebooks/ibsi/ibsi2p1.ipynb)
      - **Phase 2**: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MEDomicsLab/MEDiml/blob/main/notebooks/ibsi/ibsi2p2.ipynb)

      Our team named *UdeS* (a.k.a. Université de Sherbrooke) has already submitted the benchmarked values to the [IBSI uploading website](https://ibsi.radiomics.hevs.ch/).

---
**Miscellaneous**

You can avoid the next steps (Jupyter installation) if you already have a Jupyter Notebook setup available.

---

You can view and run the tests locally by installing the [Jupyter Notebook](https://jupyter.org/) application on your machine:
```
python -m pip install jupyter
```

Then access the IBSI tests folder using:

```
cd notebooks/ibsi/
```

Finally, launch Jupyter Notebook to navigate through the IBSI notebooks using:

```
jupyter notebook
```

Make sure to run the notebooks with a Jupyter kernel that has `MEDiml` installed. If that's not the case, you can simply install it from within the notebook by running the following in a code cell:

```
! pip install MEDiml
```

## 6. Acknowledgement
MEDiml is an open-source package developed at the [MEDomicsLab](https://www.medomicslab.com/en/) laboratory with the collaboration of the international consortium [MEDomics](https://www.medomics.ai/). We welcome any contribution and feedback. Furthermore, we wish that this package could serve the growing radiomics research community by providing a flexible as well as [IBSI](https://theibsi.github.io/) standardized tool to reimplement existing methods and develop new ones.

## 7. Authors
* [MEDomicsLab](https://www.medomicslab.com/en/): Research laboratory at Université de Sherbrooke & McGill University.
* [MEDomics](https://github.com/medomics/): MEDomics consortium.

## 8. Statement

This package is part of https://github.com/medomics, a package providing research utility tools for developing precision medicine applications.

```
Copyright (C) 2024 MEDomics consortium

GPL3 LICENSE SYNOPSIS

Here's what the license entails:

1. Anyone can copy, modify and distribute this software.
2. You have to include the license and copyright notice with each and every distribution.
3. You can use this software privately.
4. You can use this software for commercial purposes.
5. If you dare build your business solely from this code, you risk open-sourcing the whole code base.
6. If you modify it, you have to indicate changes made to the code.
7. Any modifications of this code base MUST be distributed with the same license, GPLv3.
8. This software is provided without warranty.
9. The software author or license can not be held liable for any damages inflicted by the software.
```

More information on about the [LICENSE can be found here](https://github.com/MEDomicsLab/MEDiml/blob/main/LICENSE.md)
