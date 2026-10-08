import numpy as np
import pandas as pd
from neuroCombat import neuroCombat, neuroCombatFromTraining
from sklearn.base import BaseEstimator, TransformerMixin

from ..utils.get_institutions_from_ids import get_institutions_from_ids


class CombatNormalization(BaseEstimator, TransformerMixin):
    """
    Sklearn-compatible Transformer for ComBat Normalization.
    
    This transformer assumes the input X (DataFrame) contains both the features 
    to be normalized and the column identifying the institution/batch.
    """
    def __init__(
            self,
            institution_col: str = None,
            covariates: list = None,
            drop_institution: bool = True
        ):
        """
        Args:
            institution_col (str): Name of the column in X containing the institution/batch IDs.
                                   If None, tries to derive from Index using util.
            covariates (list): List of column names in X to treat as covariates (biological retention).
            drop_institution (bool): If True, removes the institution column from output.
        """
        self.institution_col = institution_col
        self.covariates = covariates if covariates is not None else []
        self.drop_institution = drop_institution

    def fit(self, X):
        """
        Estimates the ComBat parameters on X (training data only), so that the same
        harmonization can later be applied to test/holdout data without refitting on it.
        """
        X_df, institutions, covars_df = self._prepare(X)

        # Encode institutions to integers (1, 2, 3...) required by logic
        unique_inst = pd.Series(institutions).unique()
        self.institution_mapping_ = {inst: i+1 for i, inst in enumerate(unique_inst)}
        covars_df['institution'] = pd.Series(institutions, index=X_df.index).map(self.institution_mapping_)
        self.estimates_ = None

        # Check: If < 2 institutions, ComBat fails. Transform will return original.
        if len(unique_inst) < 2:
            print("Warning: Less than 2 institutions detected. Skipping ComBat.")
            return self

        # neuroCombat expects: data (Features x Samples), covars (Samples x Covars)
        try:
            results = neuroCombat(
                dat=X_df.T,
                covars=covars_df,
                batch_col='institution'
            )
            self.estimates_ = results['estimates']
        except Exception as e:
            print(f"ComBat failed: {e}. Data will be returned unharmonized.")

        return self

    def transform(self, X):
        """
        Applies ComBat Normalization using the estimates learned in fit.
        """
        if not hasattr(self, 'estimates_'):
            raise RuntimeError("You must fit the transformer before transforming data.")

        X_df, institutions, covars_df = self._prepare(X)

        # ComBat was skipped or failed during fit
        if self.estimates_ is None:
            return X_df if len(self.institution_mapping_) < 2 else X

        # ComBat cannot harmonize institutions that were not seen during fit (no batch estimates exist
        # for them, and estimating them from the test data would leak). Their samples are left unharmonized.
        seen_mask = pd.Series(institutions, index=X_df.index).isin(list(self.institution_mapping_)).values
        unseen = sorted(set(np.asarray(institutions)[~seen_mask]))
        if unseen:
            print(f"Warning: ComBat: institutions {unseen} were not present in the training data. "
                  "Their samples are left unharmonized.")

        harmonized_data = X_df.astype(float)
        if seen_mask.any():
            # Map to the batch labels stored in the estimates (neuroCombatFromTraining compares them as strings)
            batch_levels = {float(level): level for level in np.asarray(self.estimates_['batches'])}
            batch = [batch_levels[float(self.institution_mapping_[inst])]
                     for inst, seen in zip(institutions, seen_mask) if seen]

            results = neuroCombatFromTraining(
                dat=X_df.loc[seen_mask].T.values,
                batch=np.asarray(batch),
                estimates=self.estimates_
            )

            # Result 'data' is Features x Samples
            harmonized_data.loc[seen_mask] = np.asarray(results['data']).T

        # Remove temp columns if any
        if 'temp_ones' in harmonized_data.columns:
            harmonized_data = harmonized_data.drop(columns=['temp_ones'])

        # Re-attach Covariates if they were stripped
        for cov in covars_df.columns.drop('institution'):
            harmonized_data[cov] = covars_df[cov]

        return harmonized_data

    def _prepare(self, X):
        """
        Splits X into the feature matrix to harmonize, the institution of each sample and the covariates.
        """
        # Validate Input
        if not isinstance(X, pd.DataFrame):
            raise ValueError("Input X must be a pandas DataFrame.")

        # Avoid modifying the original input
        X_df = X.copy()

        # 1. Identify Institutions
        if self.institution_col and self.institution_col in X_df.columns:
            institutions = X_df[self.institution_col]
            # If we plan to drop it later, we don't include it in features matrix
            if self.drop_institution:
                X_df = X_df.drop(columns=[self.institution_col])
        else:
            # Fallback to index-based logic from original code
            institutions = get_institutions_from_ids(pd.Series(X_df.index))
        institutions = list(institutions)

        # 2. Prepare Covariates (standard combat expects data to ONLY be the features)
        covars_df = pd.DataFrame({'institution': institutions}, index=X_df.index)
        for cov in self.covariates:
            if cov in X_df.columns:
                covars_df[cov] = X_df[cov]
                X_df = X_df.drop(columns=[cov])

        # 3. Handle Single Feature Edge Case (from original code)
        if X_df.shape[1] == 1:
            X_df['temp_ones'] = 1

        return X_df, institutions, covars_df
