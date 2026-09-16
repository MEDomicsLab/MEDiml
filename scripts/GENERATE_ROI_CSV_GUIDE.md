# ROI CSV Generator - User Guide

## Overview

> **The ROI CSV file is optional.** MEDiml processes every scan found in a dataset folder by
> default, combining all the ROIs of a scan into a single region (`{ROI_1}+{ROI_2}`). Use this
> script when you want to analyze a specific subset of the scans, or a specific ROI (or
> combination of ROIs) of each scan.

The `generate_roi_csv.py` script automates the creation of ROI (Region of Interest) CSV files for MEDiml's feature extraction pipeline. It intelligently reads DICOM files from your dataset, extracts available ROI names, and generates multiple CSV options with different ROI combinations.

## Quick Start

### Prerequisites

```bash
pip install pydicom pandas tqdm
```

### Basic Usage

```bash
python scripts/generate_roi_csv.py --dataset-path /path/to/your/dataset
```

The script will:
1. ✅ Scan your dataset for DICOM files
2. ✅ Extract all available ROI names
3. ✅ Display available options
4. ✅ Prompt you to select which options to generate
5. ✅ Create CSV files in `dataset_path/roi_csv/`

## Dataset Structure Requirements

Your dataset must be organized as follows:

```
your_dataset/
├── PatientID_001/
│   ├── CT/
│   │   ├── image.dcm
│   │   └── rtstruct.dcm          # DICOM RT Structure Set (contains ROI info)
│   └── MR_T1/
│       └── rtstruct.dcm
├── PatientID_002/
│   ├── CT/
│   │   └── rtstruct.dcm
│   └── PT/
│       └── rtstruct.dcm
└── PatientID_003/
    └── MR_T2/
        └── rtstruct.dcm
```

**Key Points:**
- Top level: Patient IDs (e.g., `BrainMets-UCSF-00017`, `STS-McGill-001`)
- Second level: Imaging scan names (e.g., `CT`, `PT`, `MR_T1`, `MR_T2`, `Dose`)
- DICOM RT Structure Set files contain the ROI information

## Generation Options

The script generates up to 4 different CSV options based on your dataset:

### Option A: Single ROI per Patient ✅ *Always Available*

**What it does:**
- Assigns the same ROI to all patients
- Useful for single-ROI analysis

**Example Output:**
```csv
PatientID,ImagingScanName,ImagingModality,ROIname
BrainMets-UCSF-00017,Dose,MRscan,{target1}
BrainMets-UCSF-00019,Dose,MRscan,{target1}
BrainMets-UCSF-00035,Dose,MRscan,{target1}
```

**Use Case:** When you want to analyze a single consistent ROI across all patients (e.g., all tumor masses)

---

### Option B: All Possible ROI Combinations ✅ *Available if < 10 Unique ROIs*

**What it does:**
- Generates all possible combinations where each patient can have a different ROI
- Useful for exploring different ROI selections
- Only generated if dataset has fewer than 10 unique ROI names

**Example Scenario:**
- Patient 1: has `{GTV_Mass}` and `{GTV_Edema}`
- Patient 2: has `{GTV_Mass}` only

**Example Output (Combination 1):**
```csv
PatientID,ImagingScanName,ImagingModality,ROIname
PatientID_001,CT,CTscan,{GTV_Mass}
PatientID_002,CT,CTscan,{GTV_Mass}
```

**Example Output (Combination 2):**
```csv
PatientID,ImagingScanName,ImagingModality,ROIname
PatientID_001,CT,CTscan,{GTV_Edema}
PatientID_002,CT,CTscan,{GTV_Mass}
```

**Use Case:** When exploring which ROI combinations yield the best predictive power; you can generate separate models for each combination

---

### Option C: All ROIs Combined ✅ *Available if Multiple ROIs Found*

**What it does:**
- For each patient with multiple ROIs, combines all ROIs using the `+` operator
- Creates a single analysis that includes all available structures

**Example Output:**
```csv
PatientID,ImagingScanName,ImagingModality,ROIname
PatientID_001,CT,CTscan,{GTV_Mass}+{GTV_Edema}
PatientID_002,CT,CTscan,{GTV_Mass}
PatientID_003,CT,CTscan,{GTV_Mass}+{GTV_Edema}+{Necrosis}
```

**Semantics:** Each ROI inside `{}` is treated independently:
- `{GTV_Mass}+{GTV_Edema}` means analyze all voxels in BOTH structures
- Useful for comprehensive tumor characterization

**Use Case:** When you want to capture all available anatomical information in a single radiomic feature set

---

### Option D: All Possible Subtractions ✅ *Available if Multiple ROIs Found*

**What it does:**
- For patients with multiple ROIs, generates all pairwise subtractions
- Creates separate analysis variants for each subtraction direction

**Example Output:**
```csv
subtract_GTV_Edema_minus_GTV_Mass:
PatientID,ImagingScanName,ImagingModality,ROIname
PatientID_001,CT,CTscan,{GTV_Edema}-{GTV_Mass}
PatientID_002,CT,CTscan,{GTV_Mass}
PatientID_003,CT,CTscan,{GTV_Edema}-{GTV_Mass}

subtract_GTV_Mass_minus_GTV_Edema:
PatientID,ImagingScanName,ImagingModality,ROIname
PatientID_001,CT,CTscan,{GTV_Mass}-{GTV_Edema}
PatientID_002,CT,CTscan,{GTV_Mass}
PatientID_003,CT,CTscan,{GTV_Mass}-{GTV_Edema}
```

**Semantics:** Subtraction extracts the "ring" region:
- `{GTV_Edema}-{GTV_Mass}` analyzes voxels in GTV_Edema but NOT in GTV_Mass
- Useful for analyzing edema around tumor margin

**Use Case:** When you want to separately analyze anatomical regions and their boundaries (e.g., tumor vs. surrounding edema)

---

## Advanced Usage

### Non-Interactive Mode

Generate specific options without prompts:

```bash
python scripts/generate_roi_csv.py \
    --dataset-path /path/to/dataset \
    --options A C D \
    --roi-label Tumor
```

**Arguments:**
- `--options`: Space-separated list (A, B, C, D) to generate
- `--roi-label`: Label used in output filenames (e.g., `Tumor`, `Brain`, `Lung`)

**Output files:**
- `roiNames_Tumor.csv` (Option A)
- `roiNames_Tumor_combined.csv` (Option C)
- `roiNames_Tumor_subtract_*.csv` (Option D)

### Custom Output Directory

```bash
python scripts/generate_roi_csv.py \
    --dataset-path /path/to/dataset \
    --output-dir /custom/output/path
```

## Output Files

### Main CSV Files

Generated CSV files follow MEDiml conventions:
- `roiNames_{roi_label}.csv` - Option A (single ROI)
- `roiNames_{roi_label}_combo{i}.csv` - Option B combinations
- `roiNames_{roi_label}_combined.csv` - Option C (combined)
- `roiNames_{roi_label}_subtract_{sub_type}.csv` - Option D (subtractions)

### Summary File

A JSON summary is automatically generated:
```json
{
  "dataset_path": "/path/to/dataset",
  "roi_label": "Tumor",
  "total_patients": 35,
  "unique_rois": ["GTV_Mass", "GTV_Edema", "target1", "target3"],
  "options_generated": ["A", "C", "D"],
  "files_saved": [
    "/path/to/dataset/roi_csv/roiNames_Tumor.csv",
    "/path/to/dataset/roi_csv/roiNames_Tumor_combined.csv",
    "/path/to/dataset/roi_csv/roiNames_Tumor_subtract_GTV_Edema_minus_GTV_Mass.csv",
    ...
  ]
}
```

## CSV Format Details

All generated CSV files follow the MEDiml standard format with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| `PatientID` | Patient identifier | `BrainMets-UCSF-00017` |
| `ImagingScanName` | Imaging sequence/type | `Dose`, `CT`, `MR_T1` |
| `ImagingModality` | Modality code | `MRscan`, `CTscan`, `PTscan` |
| `ROIname` | ROI specification | `{target1}`, `{GTV_Mass}+{Edema}` |

**Important Notes:**
- ROI names must be enclosed in curly braces: `{ROIname}`
- Multiple ROIs are combined with `+` for union and `-` for subtraction
- The `ImagingModality` column is set to `UnknownModality` by default—**you should update this** based on your actual imaging modalities

### Updating ImagingModality

After generation, update the `ImagingModality` column in each CSV:

```python
import pandas as pd

df = pd.read_csv('roiNames_Tumor.csv')

# Map scan names to modalities
modality_map = {
    'CT': 'CTscan',
    'PT': 'PTscan',
    'MR_T1': 'MRscan',
    'MR_T2': 'MRscan',
    'Dose': 'MRscan'
}

df['ImagingModality'] = df['ImagingScanName'].map(modality_map)
df.to_csv('roiNames_Tumor.csv', index=False)
```

## Workflow Example

### Scenario: Brain Metastases Dataset

**Dataset Structure:**
```
brain_mets_dataset/
├── BrainMets-UCSF-00017/
│   └── Dose/
│       └── rtstruct.dcm (contains: {target1}, {target2}, {target3})
├── BrainMets-UCSF-00019/
│   └── Dose/
│       └── rtstruct.dcm (contains: {target1})
└── BrainMets-UCSF-00035/
    └── Dose/
        └── rtstruct.dcm (contains: {target1}, {target2})
```

**Step 1: Run Generator**
```bash
python scripts/generate_roi_csv.py --dataset-path brain_mets_dataset
```

**Step 2: Interactive Prompts**
```
ROI CSV GENERATION OPTIONS
================================================================================

📋 OPTION A: Single ROI per Patient
- Each patient/scan gets a single ROI (the first alphabetically).
Number of rows: 3

📋 OPTION C: All ROIs Combined
- For patients with multiple ROIs, all ROIs are combined using (+) operator.
Number of rows: 3

📋 OPTION D: All Possible Subtractions
- For patients with multiple ROIs, all pairwise subtractions are generated.
Number of subtraction variants: 2

================================================================================

🔧 SELECT OPTIONS TO SAVE
Save OPTION A? [y/n]: y
Save OPTION C? [y/n]: y
Save OPTION D? [y/n]: y
Enter ROI label: Targets
```

**Step 3: Review Generated Files**
```
brain_mets_dataset/roi_csv/
├── roiNames_Targets.csv                          # Option A: single target per patient
├── roiNames_Targets_combined.csv                 # Option C: all targets combined
├── roiNames_Targets_subtract_target1_minus_target2.csv
├── roiNames_Targets_subtract_target2_minus_target1.csv
└── generation_summary_Targets.json
```

**Step 4: Use in MEDiml**
```python
from MEDiml.wrangling import DataManager

# Option A: Single target analysis
dm_single = DataManager(
    config_path='config.yml',
    roi_csv='brain_mets_dataset/roi_csv/roiNames_Targets.csv'
)

# Option C: Combined targets analysis
dm_combined = DataManager(
    config_path='config.yml',
    roi_csv='brain_mets_dataset/roi_csv/roiNames_Targets_combined.csv'
)

# Option D: Edge analysis
dm_edge = DataManager(
    config_path='config.yml',
    roi_csv='brain_mets_dataset/roi_csv/roiNames_Targets_subtract_target1_minus_target2.csv'
)
```

## Troubleshooting

### Issue: No ROIs Found

**Problem:** Script reports "Found 0 unique ROI names"

**Solutions:**
1. Verify DICOM files are in correct format (RT Structure Sets)
2. Check that files are readable: `python -c "import pydicom; pydicom.dcmread('file.dcm')"`
3. Ensure file structure follows expected hierarchy

### Issue: Too Many Combinations (Option B)

**Problem:** Dataset has 15+ unique ROI names, Option B not generated

**Solution:** This is by design—too many combinations would create an unwieldy number of CSVs. Consider:
- Filtering to most clinically relevant ROIs
- Using Option A or C instead
- Splitting dataset by ROI type

### Issue: ImagingModality Shows "UnknownModality"

**Problem:** ImagingModality column not automatically detected

**Solution:** Manually update CSV files using scan names:
```python
df['ImagingModality'] = df['ImagingScanName'].map({
    'CT': 'CTscan',
    'MR_T1': 'MRscan',
    'PET': 'PTscan'
})
df.to_csv('roiNames_*.csv', index=False)
```

## API Reference

### ROICSVGenerator Class

```python
from generate_roi_csv import ROICSVGenerator

# Initialize
generator = ROICSVGenerator(
    dataset_path='/path/to/dataset',
    output_dir='/path/to/output'
)

# Scan and extract ROIs
generator.scan_dataset()

# Generate individual options
option_a_df = generator.generate_single_roi_option()
option_b_dict = generator.generate_roi_combinations()
option_c_df = generator.generate_combined_roi_option()
option_d_dict = generator.generate_subtraction_options()

# Save selected options
generator.save_csv_files(['A', 'C', 'D'], roi_label='Tumor')
```

## Performance Notes

- **Dataset Scanning:** ~1-5 seconds per 100 DICOM files
- **Option Generation:** Instantaneous for A, C, D; ~1 second for B with 10 unique ROIs
- **Memory:** Depends on patient count; typically <500 MB for datasets with <1000 patients

## Citation

If you use this script in your research, please cite MEDiml:

```bibtex
@software{mediml2024,
  title={MEDiml: Medical Image Radiomics Analysis},
  url={https://github.com/MEDiml/MEDiml}
}
```

## Support

For issues or feature requests, please open an issue on the MEDiml GitHub repository.
