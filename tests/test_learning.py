import json
import os
import sys

import numpy as np
import pandas as pd
import pytest
from numpyencoder import NumpyEncoder
from sklearn.datasets import make_classification

MODULE_DIR = os.path.dirname(os.path.abspath('./MEDiml/'))
sys.path.append(MODULE_DIR)

from MEDiml.learning.Estimator import Estimator
from MEDiml.utils.rf_learner import RandomForestEstimator
from MEDiml.utils.xgboost_learner import XGBoostEstimator


def _make_radiomics_style_data(n_samples=60, n_features=6, seed=54288):
    """Builds a small synthetic dataset shaped like a MEDiml radiomics table, with the
    `Properties` metadata that PyCaretEstimator._train_logic expects (var_def, userData)."""
    X, y = make_classification(
        n_samples=n_samples, n_features=n_features, n_informative=4,
        n_redundant=0, random_state=seed
    )
    columns = [f'radVar{i + 1}' for i in range(n_features)]
    index = [f'patient_{i}' for i in range(n_samples)]

    var_def = '||'
    for col in columns:
        var_def += f'{col}:feature_{col}||'

    X_df = pd.DataFrame(X, columns=columns, index=index)
    X_df._metadata += ['Properties']
    X_df.Properties = {
        'userData': {'variables': {'var_def': var_def, 'continuous': np.array(columns)}},
        'VariableNames': columns,
        'Description': 'synthetic'
    }

    y_df = pd.DataFrame({'outcome': y}, index=index)

    return X_df, y_df


def _ml_config(**overrides):
    config = dict(
        optimization_metric='MCC',
        n_features_to_select=0.5,
        internal_cv_folds=3,
        optimize_threshold=False,
        use_gpu=False,
        seed=54288
    )
    config.update(overrides)
    return config


@pytest.mark.parametrize('algorithm', ['lr', 'dt'])
def test_estimator_supports_any_pycaret_algorithm(algorithm):
    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm=algorithm, ml_config=_ml_config())
    estimator.fit(X, y)

    proba = estimator.predict_proba(X)
    preds = estimator.predict(X)

    assert proba.shape[0] == len(X)
    assert set(np.unique(preds)).issubset({0, 1})
    assert estimator.estimator_.model_info_['algo'] == algorithm


def test_estimator_best_mode_runs_compare_models():
    X, y = _make_radiomics_style_data()
    estimator = Estimator(
        algorithm='best',
        ml_config=_ml_config(best_include=['lr', 'dt'])
    )
    estimator.fit(X, y)

    proba = estimator.predict_proba(X)
    assert proba.shape[0] == len(X)
    # The winning model's actual class name should be recorded, not the literal "best"
    assert estimator.estimator_.model_info_['algo'] != 'best'
    json.dumps(estimator.estimator_.model_info_['optimization'], cls=NumpyEncoder)


def test_estimator_calibrates_models_without_predict_proba():
    # PyCaret's 'svm' id maps to SGDClassifier(loss='hinge'), which has no predict_proba.
    # PyCaretEstimator must calibrate it so downstream AUC/threshold logic still works.
    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm='svm', ml_config=_ml_config())
    estimator.fit(X, y)

    proba = estimator.predict_proba(X)
    assert proba.shape[0] == len(X)
    assert np.all((proba >= 0) & (proba <= 1))

    # Calibrated models nest the raw wrapped estimator in get_params() (e.g. the
    # CalibratedClassifierCV's 'estimator' key); model_info['optimization'] must stay
    # JSON-serializable (as saved via save_json(..., cls=NumpyEncoder) in RadiomicsLearner).
    json.dumps(estimator.estimator_.model_info_['optimization'], cls=NumpyEncoder)


def test_estimator_invalid_algorithm_raises():
    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm='not_a_real_model', ml_config=_ml_config())

    with pytest.raises(Exception):
        estimator.fit(X, y)


def test_estimator_final_classifier_uses_all_training_rows():
    # PyCaret fits on an internal 70% split; the returned classifier must be re-fitted on all rows
    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm='dt', ml_config=_ml_config())
    estimator.fit(X, y)

    assert estimator.estimator_.classifier_.tree_.n_node_samples[0] == len(X)


def test_estimator_predicts_with_full_pycaret_pipeline():
    # Test data must go through the same PyCaret preprocessing as during tuning (e.g. imputation)
    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm='lr', ml_config=_ml_config())
    estimator.fit(X, y)
    pce = estimator.estimator_

    assert pce.input_features_ == list(X.columns)
    assert set(pce.selected_features_).issubset(X.columns)

    X_missing = X.copy()
    X_missing.iloc[:5, :] = np.nan
    proba = estimator.predict_proba(X_missing)
    assert not np.isnan(proba).any()
    np.testing.assert_allclose(proba, pce.pipeline_.predict_proba(X_missing)[:, 1])


def test_estimator_threshold_from_out_of_fold_predictions():
    from sklearn import metrics
    from sklearn.base import clone
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    X, y = _make_radiomics_style_data()
    estimator = Estimator(algorithm='lr', ml_config=_ml_config(optimize_threshold=True))
    estimator.fit(X, y)

    pce = estimator.estimator_
    cv = StratifiedKFold(n_splits=pce.internal_cv_folds, shuffle=True, random_state=pce.seed)
    y_probs = cross_val_predict(clone(pce.pipeline_), X[pce.input_features_], y['outcome'],
                                cv=cv, method='predict_proba')[:, 1]
    fpr, tpr, thresholds = metrics.roc_curve(y['outcome'], y_probs)
    expected = thresholds[np.argmin(np.sqrt(fpr ** 2 + (1 - tpr) ** 2))]

    assert pce.model_info_['threshold'] == pytest.approx(expected)


def _make_multi_institution_data(n_per_inst=20, n_features=4, seed=0):
    rng = np.random.default_rng(seed)
    frames = []
    for shift, inst in enumerate(['AAA', 'BBB', 'CCC']):
        index = [f'Study-{inst}-{i:03d}' for i in range(n_per_inst)]
        frames.append(pd.DataFrame(rng.normal(shift, 1 + shift, (n_per_inst, n_features)),
                                   index=index, columns=[f'f{j}' for j in range(n_features)]))
    return pd.concat(frames)


def test_combat_estimates_are_not_affected_by_test_data():
    from MEDiml.learning.Normalization import CombatNormalization

    X = _make_multi_institution_data()
    train_ids, test_ids = X.index[::2], X.index[1::2]

    X_perturbed = X.copy()
    X_perturbed.loc[test_ids] += 100

    out = CombatNormalization().fit(X.loc[train_ids]).transform(X)
    out_perturbed = CombatNormalization().fit(X_perturbed.loc[train_ids]).transform(X_perturbed)

    # Training rows are harmonized identically whatever the test rows contain
    pd.testing.assert_frame_equal(out.loc[train_ids], out_perturbed.loc[train_ids])

    # On training rows, the result equals a plain neuroCombat run on those rows
    from neuroCombat import neuroCombat
    batch = pd.Series(train_ids).str.split('-').str[1].values
    ref = neuroCombat(dat=X.loc[train_ids].T, covars=pd.DataFrame({'institution': batch}), batch_col='institution')
    np.testing.assert_allclose(out.loc[train_ids].values, ref['data'].T, rtol=1e-5, atol=1e-6)


def test_combat_removes_batch_effect_on_test_data():
    from MEDiml.learning.Normalization import CombatNormalization

    X = _make_multi_institution_data(n_per_inst=400)
    train_ids, test_ids = X.index[::2], X.index[1::2]
    out = CombatNormalization().fit(X.loc[train_ids]).transform(X)

    by_inst = lambda pid: pid.split('-')[1]
    assert out.loc[test_ids].groupby(by_inst).mean().std().max() < 0.5
    assert X.loc[test_ids].groupby(by_inst).mean().std().min() > 0.7


def test_combat_unseen_institution_left_unharmonized():
    from MEDiml.learning.Normalization import CombatNormalization

    X = _make_multi_institution_data()
    is_unseen = X.index.str.contains('-CCC-')
    train = X[~is_unseen]

    combat = CombatNormalization().fit(train)
    out = combat.transform(X)

    # Unseen institution passes through unchanged, seen institutions are harmonized as usual
    pd.testing.assert_frame_equal(out.loc[is_unseen], X.loc[is_unseen].astype(float))
    pd.testing.assert_frame_equal(out.loc[~is_unseen], combat.transform(train))


def test_datacleaner_random_imputation_uses_training_values():
    from MEDiml.learning.DataCleaner import DataCleaner

    rng = np.random.default_rng(0)
    train = pd.DataFrame({'f0': rng.uniform(1, 2, 50), 'f1': rng.uniform(1, 2, 50)})
    test = pd.DataFrame({'f0': [np.nan, 100., np.nan, 100.], 'f1': [100., 100., 100., 100.]})

    cleaner = DataCleaner(imputation='random', missingCutoffps=0.5, random_state=0).fit(train)
    out = cleaner.transform(test)
    out_again = DataCleaner(imputation='random', missingCutoffps=0.5, random_state=0).fit(train).transform(test)

    # Imputed values come from the training data (not from the test values), reproducibly
    assert out.loc[[0, 2], 'f0'].isin(train['f0']).all()
    pd.testing.assert_frame_equal(out, out_again)


def test_datacleaner_records_dropped_samples():
    from MEDiml.learning.DataCleaner import DataCleaner

    train = pd.DataFrame({'f0': [1., 2., 3., 4.], 'f1': [4., 3., 2., 1.]})
    test = pd.DataFrame({'f0': [1., np.nan], 'f1': [2., np.nan]}, index=['keep', 'drop'])

    cleaner = DataCleaner().fit(train)
    out = cleaner.transform(test)

    assert list(out.index) == ['keep']
    assert cleaner.dropped_samples_ == ['drop']


def test_final_model_preprocessing_excludes_holdout(tmp_path, monkeypatch):
    from MEDiml.learning.RadiomicsLearner import RadiomicsLearner

    learn, holdout = ['p1', 'p2', 'p3'], ['h1', 'h2']
    path_learn = tmp_path / 'learn__exp'
    (path_learn / 'test__001').mkdir(parents=True)
    (tmp_path / 'patientsLearn.json').write_text(json.dumps(learn))
    (tmp_path / 'patientsHoldOut.json').write_text(json.dumps(holdout))
    pd.DataFrame({'outcome': [0, 1, 0, 1, 0]}, index=learn + holdout).to_csv(tmp_path / 'outcomes.csv')
    (tmp_path / 'ml.json').write_text(json.dumps({'variables': {'varStudy': 'var1'}, 'modeling': {}}))
    (path_learn / 'test__001' / 'paths_ml.json').write_text(json.dumps({'ml': str(tmp_path / 'ml.json')}))

    seen = {}
    def fake_pre_process(self, ml, var_id, outcome_table_binary, patients_train):
        seen['patients_train'] = list(patients_train)
        raise RuntimeError('stop')
    monkeypatch.setattr(RadiomicsLearner, 'pre_process_radiomics_table', fake_pre_process)

    learner = RadiomicsLearner(tmp_path, tmp_path, tmp_path, 'exp')
    with pytest.raises(ValueError, match='stop'):
        learner.train_final_model()

    assert sorted(seen['patients_train']) == learn


def test_estimator_logs_training_steps_to_log_file(tmp_path):
    log_file = tmp_path / 'batch.log'
    X, y = _make_radiomics_style_data()
    Estimator(algorithm='lr', ml_config=_ml_config(optimize_threshold=True), log_file=log_file).fit(X, y)

    content = log_file.read_text()
    for step in ['PyCaret setup', 'Creating model', 'Tuning hyperparameters', 'Selected features',
                 'Optimized decision threshold', 'Final fit on all 60 training patients']:
        assert step in content
    # The handler is released after fitting (file can be removed, e.g. on Windows)
    log_file.unlink()


def test_estimator_reuses_existing_split_log_handler(tmp_path):
    import logging

    log_file = tmp_path / 'batch.log'
    logging.basicConfig(filename=str(log_file), level=logging.INFO, format='%(message)s', filemode='w', force=True)
    try:
        logging.info('SPLIT START')
        X, y = _make_radiomics_style_data()
        Estimator(algorithm='lr', ml_config=_ml_config(), log_file=log_file).fit(X, y)
        logging.info('SPLIT END')
        for handler in logging.getLogger().handlers:
            handler.flush()

        lines = log_file.read_text().splitlines()
        # Estimator lines are written between the split's own lines, none of them overwritten
        assert lines[0] == 'SPLIT START' and lines[-1] == 'SPLIT END'
        assert any('Tuning hyperparameters' in line for line in lines[1:-1])
        assert sum('Tuning hyperparameters' in line for line in lines) == 1
    finally:
        logging.basicConfig(force=True, handlers=[logging.NullHandler()])


def test_backward_compatible_wrappers_force_algorithm():
    xgb = XGBoostEstimator(**_ml_config())
    rf = RandomForestEstimator(**_ml_config())

    assert xgb.algorithm == 'xgboost'
    assert rf.algorithm == 'rf'
    assert rf.create_model_kwargs == {'class_weight': 'balanced'}
