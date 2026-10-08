import logging
import os
import time
from contextlib import contextmanager
from copy import deepcopy

import numpy as np
import pandas as pd
from pycaret.classification import *
from sklearn import metrics
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from ..learning.ml_utils import finalize_rad_table, intersect_var_tables

logger = logging.getLogger(__name__)


class PyCaretEstimator(BaseEstimator, ClassifierMixin):
    def __init__(
            self,
            algorithm='best',
            optimization_metric='MCC',
            n_features_to_select=0.05,
            internal_cv_folds=5,
            optimize_threshold=None,
            use_gpu=False,
            seed=None,
            feature_selection_estimator='lightgbm',
            create_model_kwargs=None,
            best_include=None,
            best_exclude=None,
            log_file=None
        ):
        """
        Args:
            log_file (str or Path, optional): Log file of the current split/run. If given, all training steps
                are appended to it; otherwise, messages go through the standard ``logging`` configuration.
        """
        # Store all parameters as attributes
        self.algorithm = algorithm
        self.optimization_metric = optimization_metric
        self.n_features_to_select = n_features_to_select
        self.internal_cv_folds = internal_cv_folds
        self.optimize_threshold = optimize_threshold
        self.use_gpu = use_gpu
        self.seed = seed
        self.feature_selection_estimator = feature_selection_estimator
        self.create_model_kwargs = create_model_kwargs
        self.best_include = best_include
        self.best_exclude = best_exclude
        self.log_file = log_file

        # This will hold the "model_info" dictionary result
        self.model_info_ = None
        self.pipeline_ = None
        self.classifier_ = None
        self.input_features_ = None
        self.selected_features_ = None
        self.selected_features_definitions_ = None

    def fit(self, X, y):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # Ensure y is a DataFrame for merging in PyCaret logic
        if not isinstance(y, pd.DataFrame):
            y = pd.DataFrame(y)

        with self._logging_to_file():
            results, self.pipeline_ = self._train_logic(X, y)

        # The final estimator of the pipeline (used e.g. for feature importances)
        self.classifier_ = self.pipeline_.steps[-1][1]
        self.model_info_ = results
        self.input_features_ = results['input_var_names']
        self.selected_features_ = results['var_names']
        self.selected_features_definitions_ = results.get('var_def')
        self.classes_ = np.unique(y)

        return self

    def predict(self, X):
        if self.pipeline_ is None:
            raise ValueError("Model has not been fitted yet.")

        probas = self.predict_proba(X)
        threshold = self.model_info_.get('threshold', 0.5)
        return (probas >= threshold).astype(int)

    def predict_proba(self, X):
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        # The PyCaret pipeline (preprocessing + feature selection + model) expects all training input features
        return self.pipeline_.predict_proba(X[self.input_features_])[:, 1]

    @contextmanager
    def _logging_to_file(self):
        """
        Routes this module's log messages to ``self.log_file`` while fitting. If a handler already
        writes to that file (e.g. the split's batch log set up by RadiomicsLearner), it is reused so
        that both writers share the same file position.
        """
        if self.log_file is None:
            yield
            return

        path_log = os.path.abspath(str(self.log_file))
        handler = next((h for h in logging.getLogger().handlers
                        if isinstance(h, logging.FileHandler) and h.baseFilename == path_log), None)
        own_handler = handler is None
        if own_handler:
            handler = logging.FileHandler(path_log, mode='a')
            handler.setFormatter(logging.Formatter('%(message)s'))

        previous_level, previous_propagate = logger.level, logger.propagate
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        try:
            yield
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
            logger.propagate = previous_propagate
            if own_handler:
                handler.close()

    def _train_logic(self, var_table_train, outcome_table_binary_train):
        """
        Trains a PyCaret classification model for the given machine learning test.

        Args:
            var_table_train (pd.DataFrame): Radiomics table for the training/learning set.
            outcome_table_binary_train (pd.DataFrame): Outcome table with binary labels for the training/learning set.

        Returns:
            Dict: Dictionary containing info about the trained model.
        """
        # Safety check (make sure that the outcome table and the variable table have the same patients)
        var_table_train, outcome_table_binary_train = intersect_var_tables(var_table_train, outcome_table_binary_train)

        # Finalize the new radiomics table with the remaining variables
        var_table_train = finalize_rad_table(var_table_train)

        # Set up data for PyCaret
        temp_data = pd.merge(var_table_train, outcome_table_binary_train, left_index=True, right_index=True)
        target_col = outcome_table_binary_train.columns[0]

        logger.info(f"{' ' * 4}--> ESTIMATOR ({self.algorithm})")
        logger.info(f"{' ' * 8}...Training data: {var_table_train.shape[0]} patients, {var_table_train.shape[1]} features, "
                    f"class counts: {outcome_table_binary_train.iloc[:, 0].value_counts().sort_index().to_dict()}")

        # PyCaret setup
        tstart = time.time()
        logger.info(f"{' ' * 8}...PyCaret setup and feature selection "
                    f"(estimator: {self.feature_selection_estimator}, n_features_to_select: {self.n_features_to_select}, "
                    f"internal CV folds: {self.internal_cv_folds}, seed: {self.seed})")
        setup(
            data=temp_data,
            target=target_col,
            feature_selection=True,
            n_features_to_select=self.n_features_to_select,
            fold=self.internal_cv_folds,
            use_gpu=self.use_gpu,
            feature_selection_estimator=self.feature_selection_estimator,
            session_id=self.seed,
            html=False,
            verbose=False
        )

        from sklearn.metrics import recall_score

        add_metric('sensitivity', 'Sensitivity', recall_score, greater_is_better=True, needs_proba=False)

        # Set seed
        if self.seed is not None:
            set_config('seed', self.seed)
        logger.info(f"{' ' * 8}...Done in {time.time() - tstart:.2f} sec")

        # Creating the model using PyCaret
        tstart = time.time()
        if self.algorithm == 'best':
            logger.info(f"{' ' * 8}...Comparing models (sort: {self.optimization_metric}, "
                        f"include: {self.best_include}, exclude: {self.best_exclude})")
            classifier = compare_models(
                include=self.best_include,
                exclude=self.best_exclude,
                sort=self.optimization_metric,
                fold=self.internal_cv_folds,
                verbose=False
            )
            resolved_algo = classifier.__class__.__name__
            logger.info(f"{' ' * 8}...Best model: {resolved_algo}")
        else:
            logger.info(f"{' ' * 8}...Creating model '{self.algorithm}' "
                        f"(create_model_kwargs: {self.create_model_kwargs or {}})")
            classifier = create_model(self.algorithm, **(self.create_model_kwargs or {}), verbose=False)
            resolved_algo = self.algorithm
        logger.info(f"{' ' * 8}...Done in {time.time() - tstart:.2f} sec")

        # Tuning the model using PyCaret
        tstart = time.time()
        logger.info(f"{' ' * 8}...Tuning hyperparameters (optimize: {self.optimization_metric})")
        classifier = tune_model(classifier, optimize=self.optimization_metric, verbose=False)
        logger.info(f"{' ' * 8}...Tuned parameters: {classifier.get_params()}")
        logger.info(f"{' ' * 8}...Done in {time.time() - tstart:.2f} sec")

        # MEDiml relies on predict_proba for AUC/threshold-based evaluation, but some PyCaret
        # models don't natively support it (e.g. 'svm' -> SGDClassifier with hinge loss, 'ridge'
        # -> RidgeClassifier). Calibrate those so they still produce probability estimates.
        if not hasattr(classifier, 'predict_proba'):
            logger.info(f"{' ' * 8}...Model has no predict_proba, calibrating probabilities")
            classifier = calibrate_model(classifier, verbose=False)

        # PyCaret fits models on its internal train split only (train_size=0.7 by default), so the whole
        # tuned pipeline (preprocessing, feature selection and model) is re-fitted on all the given training data.
        # The same pipeline is then used for predictions, so test data goes through the exact same steps.
        input_features = list(var_table_train.columns)
        X_train = var_table_train[input_features]
        y_train = outcome_table_binary_train.iloc[:, 0]

        tstart = time.time()
        pipeline = finalize_model(classifier)
        classifier = pipeline.steps[-1][1]
        selected_features = list(classifier.feature_names_in_)
        logger.info(f"{' ' * 8}...Selected features ({len(selected_features)}): {selected_features}")
        logger.info(f"{' ' * 8}...Final fit on all {X_train.shape[0]} training patients "
                    f"done in {time.time() - tstart:.2f} sec")

        # Find threshold (on out-of-fold predictions of the full pipeline)
        if self.optimize_threshold:
            tstart = time.time()
            try:
                threshold = self.__find_balanced_threshold(pipeline, X_train, y_train)
                logger.info(f"{' ' * 8}...Optimized decision threshold: {threshold:.4f} "
                            f"(done in {time.time() - tstart:.2f} sec)")
            except Exception as e:
                logger.warning(f"{' ' * 8}...Error in finding optimal threshold, it will be set to 0.5: {e}")
                threshold = 0.5
        else:
            threshold = 0.5
            logger.info(f"{' ' * 8}...Threshold optimization disabled, using 0.5")

        # Saving the information of the model in a dictionary
        model_info = dict()
        model_info['algo'] = resolved_algo
        model_info['type'] = 'binary'

        model_info['threshold'] = threshold

        user_data = var_table_train.Properties.get('userData', {}) if hasattr(var_table_train, 'Properties') else {}
        model_info['var_info'] = deepcopy(user_data)
        model_info['var_def'] = deepcopy(user_data.get('variables', {}).get('var_def'))
        model_info['input_var_names'] = input_features
        model_info['var_names'] = selected_features
        model_info['optimization'] = self.__make_json_safe(classifier.get_params())

        return model_info, pipeline

    @staticmethod
    def __make_json_safe(value):
        """Recursively sanitizes get_params() output for JSON serialization.

        Some PyCaret models (e.g. calibrated models, ensembles) nest actual estimator
        objects in their params (e.g. CalibratedClassifierCV's 'estimator' key); those
        aren't JSON-serializable, so they're replaced with their repr() instead of
        crashing the results save step.
        """
        if isinstance(value, dict):
            return {k: PyCaretEstimator.__make_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [PyCaretEstimator.__make_json_safe(v) for v in value]
        if value is None or isinstance(value, (str, int, float, bool, np.generic, np.ndarray)):
            return value
        return repr(value)

    def __find_balanced_threshold(self, model, variable_table, outcome_binary) -> float:
        # Out-of-fold probabilities: in-sample predictions of a tuned model are over-confident
        n_splits = min(self.internal_cv_folds, int(outcome_binary.value_counts().min()))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.seed)
        logger.info(f"{' ' * 8}...Optimizing decision threshold on {n_splits}-fold out-of-fold predictions")
        y_probs = cross_val_predict(clone(model), variable_table, outcome_binary, cv=cv, method='predict_proba')[:, 1]

        # ROC Calculation
        fpr, tpr, thresholds = metrics.roc_curve(outcome_binary, y_probs)
        logger.info(f"{' ' * 8}...Out-of-fold AUC: {metrics.auc(fpr, tpr):.4f}")

        # Geometric optimization (closest to top-left corner)
        # Distance = sqrt( fpr^2 + (1-tpr)^2 )
        dist = np.sqrt(np.power(fpr, 2) + np.power(1 - tpr, 2))
        best_idx = np.argmin(dist)

        return thresholds[best_idx]
