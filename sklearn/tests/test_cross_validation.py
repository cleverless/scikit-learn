"""Test the cross_validation module"""

import warnings

import numpy as np
from scipy.sparse import coo_matrix

from sklearn.utils.testing import assert_true
from sklearn.utils.testing import assert_equal
from sklearn.utils.testing import assert_almost_equal
from sklearn.utils.testing import assert_raises
from sklearn.utils.testing import assert_greater
from sklearn.utils.testing import assert_less
from sklearn.utils.testing import assert_array_almost_equal
from sklearn.utils.testing import assert_array_equal

from sklearn.utils.fixes import unique

from sklearn import cross_validation as cval
from sklearn.base import BaseEstimator
from sklearn.datasets import make_regression
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score
from sklearn.metrics import f1_score
from sklearn.metrics import explained_variance_score
from sklearn.metrics import fbeta_score
from sklearn.metrics import make_scorer

from sklearn.externals import six
from sklearn.linear_model import Ridge
from sklearn.svm import SVC


class MockListClassifier(BaseEstimator):
    """Dummy classifier to test the cross-validation.

    Checks that GridSearchCV didn't convert X to array.
    """
    def __init__(self, foo_param=0):
        self.foo_param = foo_param

    def fit(self, X, Y):
        assert_true(len(X) == len(Y))
        assert_true(isinstance(X, list))
        return self

    def predict(self, T):
        return T.shape[0]

    def score(self, X=None, Y=None):
        if self.foo_param > 1:
            score = 1.
        else:
            score = 0.
        return score


class MockClassifier(BaseEstimator):
    """Dummy classifier to test the cross-validation"""

    def __init__(self, a=0):
        self.a = a

    def fit(self, X, Y=None, sample_weight=None, class_prior=None):
        if sample_weight is not None:
            assert_true(sample_weight.shape[0] == X.shape[0],
                        'MockClassifier extra fit_param sample_weight.shape[0]'
                        ' is {0}, should be {1}'.format(sample_weight.shape[0],
                                                        X.shape[0]))
        if class_prior is not None:
            assert_true(class_prior.shape[0] == len(np.unique(y)),
                        'MockClassifier extra fit_param class_prior.shape[0]'
                        ' is {0}, should be {1}'.format(class_prior.shape[0],
                                                        len(np.unique(y))))
        return self

    def predict(self, T):
        return T.shape[0]

    def score(self, X=None, Y=None):
        return 1. / (1 + np.abs(self.a))


X = np.ones((10, 2))
X_sparse = coo_matrix(X)
y = np.arange(10) // 2

##############################################################################
# Tests


def test_kfold_valueerrors():
    # Check that errors are raised if there is not enough samples
    assert_raises(ValueError, cval.KFold, 3, 4)

    # Check that a warning is raised if the least populated class has too few
    # members.
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        y = [0, 0, 1, 1, 2]
        cval.StratifiedKFold(y, 3)
        # checking there was only one warning.
        assert_equal(len(w), 1)
        # checking it has the right type
        assert_equal(w[0].category, Warning)
        # checking it's the right warning. This might be a bad test since it's
        # a characteristic of the code and not a behavior
        assert_true("The least populated class" in str(w[0]))

    # Error when number of folds is <= 1
    assert_raises(ValueError, cval.KFold, 2, 0)
    assert_raises(ValueError, cval.KFold, 2, 1)
    assert_raises(ValueError, cval.StratifiedKFold, y, 0)
    assert_raises(ValueError, cval.StratifiedKFold, y, 1)

    # When n is not integer:
    assert_raises(ValueError, cval.KFold, 2.5, 2)

    # When n_folds is not integer:
    assert_raises(ValueError, cval.KFold, 5, 1.5)
    assert_raises(ValueError, cval.StratifiedKFold, y, 1.5)


def test_kfold_indices():
    # Check all indices are returned in the test folds
    kf = cval.KFold(300, 3)
    all_folds = None
    for train, test in kf:
        if all_folds is None:
            all_folds = test.copy()
        else:
            all_folds = np.concatenate((all_folds, test))

    all_folds.sort()
    assert_array_equal(all_folds, np.arange(300))


def test_kfold_balance():
    # Check that KFold returns folds with balanced sizes
    for kf in [cval.KFold(i, 5) for i in range(11, 17)]:
        sizes = []
        for _, test in kf:
            sizes.append(len(test))

        assert_true((np.max(sizes) - np.min(sizes)) <= 1)
        assert_equal(np.sum(sizes), kf.n)


def test_shuffle_kfold():
    # Check the indices are shuffled properly, and that all indices are
    # returned in the different test folds
    kf1 = cval.KFold(300, 3, shuffle=True, random_state=0, indices=True)
    kf2 = cval.KFold(300, 3, shuffle=True, random_state=0, indices=False)
    ind = np.arange(300)

    for kf in (kf1, kf2):
        all_folds = None
        for train, test in kf:
            sorted_array = np.arange(100)
            assert_true(np.any(sorted_array != ind[train]))
            sorted_array = np.arange(101, 200)
            assert_true(np.any(sorted_array != ind[train]))
            sorted_array = np.arange(201, 300)
            assert_true(np.any(sorted_array != ind[train]))
            if all_folds is None:
                all_folds = ind[test].copy()
            else:
                all_folds = np.concatenate((all_folds, ind[test]))

        all_folds.sort()
        assert_array_equal(all_folds, ind)


def test_shuffle_split():
    ss1 = cval.ShuffleSplit(10, test_size=0.2, random_state=0)
    ss2 = cval.ShuffleSplit(10, test_size=2, random_state=0)
    ss3 = cval.ShuffleSplit(10, test_size=np.int32(2), random_state=0)
    for typ in six.integer_types:
        ss4 = cval.ShuffleSplit(10, test_size=typ(2), random_state=0)
    for t1, t2, t3, t4 in zip(ss1, ss2, ss3, ss4):
        assert_array_equal(t1[0], t2[0])
        assert_array_equal(t2[0], t3[0])
        assert_array_equal(t3[0], t4[0])
        assert_array_equal(t1[1], t2[1])
        assert_array_equal(t2[1], t3[1])
        assert_array_equal(t3[1], t4[1])


def test_stratified_shuffle_split_init():
    y = np.asarray([0, 1, 1, 1, 2, 2, 2])
    # Check that error is raised if there is a class with only one sample
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 0.2)

    # Check that error is raised if the test set size is smaller than n_classes
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 2)
    # Check that error is raised if the train set size is smaller than
    # n_classes
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 3, 2)

    y = np.asarray([0, 0, 0, 1, 1, 1, 2, 2, 2])
    # Check that errors are raised if there is not enough samples
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 0.5, 0.6)
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 8, 0.6)
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, 3, 0.6, 8)

    # Train size or test size too small
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, train_size=2)
    assert_raises(ValueError, cval.StratifiedShuffleSplit, y, test_size=2)


def test_stratified_shuffle_split_iter():
    ys = [np.array([1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3]),
          np.array([0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3]),
          np.array([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2]),
          np.array([1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4]),
          np.array([-1] * 800 + [1] * 50)
          ]

    for y in ys:
        sss = cval.StratifiedShuffleSplit(y, 6, test_size=0.33,
                                          random_state=0, indices=True)
        for train, test in sss:
            assert_array_equal(unique(y[train]), unique(y[test]))
            # Checks if folds keep classes proportions
            p_train = (np.bincount(unique(y[train], return_inverse=True)[1]) /
                       float(len(y[train])))
            p_test = (np.bincount(unique(y[test], return_inverse=True)[1]) /
                      float(len(y[test])))
            assert_array_almost_equal(p_train, p_test, 1)
            assert_equal(y[train].size + y[test].size, y.size)
            assert_array_equal(np.lib.arraysetops.intersect1d(train, test), [])


def test_stratified_shuffle_split_iter_no_indices():
    y = np.asarray([0, 1, 2] * 10)

    sss1 = cval.StratifiedShuffleSplit(y, indices=False, random_state=0)
    train_mask, test_mask = next(iter(sss1))

    sss2 = cval.StratifiedShuffleSplit(y, indices=True, random_state=0)
    train_indices, test_indices = next(iter(sss2))

    assert_array_equal(sorted(test_indices), np.where(test_mask)[0])


def test_leave_label_out_changing_labels():
    """Check that LeaveOneLabelOut and LeavePLabelOut work normally if
    the labels variable is changed before calling __iter__"""
    labels = np.array([0, 1, 2, 1, 1, 2, 0, 0])
    labels_changing = np.array(labels, copy=True)
    lolo = cval.LeaveOneLabelOut(labels)
    lolo_changing = cval.LeaveOneLabelOut(labels_changing)
    lplo = cval.LeavePLabelOut(labels, p=2)
    lplo_changing = cval.LeavePLabelOut(labels_changing, p=2)
    labels_changing[:] = 0
    for llo, llo_changing in [(lolo, lolo_changing), (lplo, lplo_changing)]:
        for (train, test), (train_chan, test_chan) in zip(llo, llo_changing):
            assert_array_equal(train, train_chan)
            assert_array_equal(test, test_chan)


def test_cross_val_score():
    clf = MockClassifier()
    for a in range(-10, 10):
        clf.a = a
        # Smoke test
        scores = cval.cross_val_score(clf, X, y)
        assert_array_equal(scores, clf.score(X, y))

        scores = cval.cross_val_score(clf, X_sparse, y)
        assert_array_equal(scores, clf.score(X_sparse, y))

    # test with X as list
    clf = MockListClassifier()
    scores = cval.cross_val_score(clf, X.tolist(), y)

    assert_raises(ValueError, cval.cross_val_score, clf, X, y,
                  scoring="sklearn")


def test_cross_val_score_precomputed():
    # test for svm with precomputed kernel
    svm = SVC(kernel="precomputed")
    iris = load_iris()
    X, y = iris.data, iris.target
    linear_kernel = np.dot(X, X.T)
    score_precomputed = cval.cross_val_score(svm, linear_kernel, y)
    svm = SVC(kernel="linear")
    score_linear = cval.cross_val_score(svm, X, y)
    assert_array_equal(score_precomputed, score_linear)

    # Error raised for non-square X
    svm = SVC(kernel="precomputed")
    assert_raises(ValueError, cval.cross_val_score, svm, X, y)

    # test error is raised when the precomputed kernel is not array-like
    # or sparse
    assert_raises(ValueError, cval.cross_val_score, svm,
                  linear_kernel.tolist(), y)


def test_cross_val_score_fit_params():
    clf = MockClassifier()
    n_samples = X.shape[0]
    n_classes = len(np.unique(y))
    fit_params = {'sample_weight': np.ones(n_samples),
                  'class_prior': np.ones(n_classes) / n_classes}
    cval.cross_val_score(clf, X, y, fit_params=fit_params)


def test_cross_val_score_score_func():
    clf = MockClassifier()
    _score_func_args = []

    def score_func(y_test, y_predict):
        _score_func_args.append((y_test, y_predict))
        return 1.0

    with warnings.catch_warnings(record=True):
        score = cval.cross_val_score(clf, X, y, score_func=score_func)
    assert_array_equal(score, [1.0, 1.0, 1.0])
    assert len(_score_func_args) == 3


def test_cross_val_score_errors():
    class BrokenEstimator:
        pass

    assert_raises(TypeError, cval.cross_val_score, BrokenEstimator(), X)


def test_train_test_split_errors():
    assert_raises(ValueError, cval.train_test_split)
    assert_raises(ValueError, cval.train_test_split, range(3), train_size=1.1)
    assert_raises(ValueError, cval.train_test_split, range(3), test_size=0.6,
                  train_size=0.6)
    assert_raises(ValueError, cval.train_test_split, range(3),
                  test_size=np.float32(0.6), train_size=np.float32(0.6))
    assert_raises(ValueError, cval.train_test_split, range(3),
                  test_size="wrong_type")
    assert_raises(ValueError, cval.train_test_split, range(3), test_size=2,
                  train_size=4)
    assert_raises(TypeError, cval.train_test_split, range(3),
                  some_argument=1.1)
    assert_raises(ValueError, cval.train_test_split, range(3), range(42))


def test_train_test_split():
    X = np.arange(100).reshape((10, 10))
    X_s = coo_matrix(X)
    y = range(10)
    split = cval.train_test_split(X, X_s, y)
    X_train, X_test, X_s_train, X_s_test, y_train, y_test = split
    assert_array_equal(X_train, X_s_train.toarray())
    assert_array_equal(X_test, X_s_test.toarray())
    assert_array_equal(X_train[:, 0], y_train * 10)
    assert_array_equal(X_test[:, 0], y_test * 10)
    split = cval.train_test_split(X, y, test_size=None, train_size=.5)
    X_train, X_test, y_train, y_test = split
    assert_equal(len(y_test), len(y_train))


def test_cross_val_score_with_score_func_classification():
    iris = load_iris()
    clf = SVC(kernel='linear')

    # Default score (should be the accuracy score)
    scores = cval.cross_val_score(clf, iris.data, iris.target, cv=5)
    assert_array_almost_equal(scores, [1., 0.97, 0.90, 0.97, 1.], 2)

    # Correct classification score (aka. zero / one score) - should be the
    # same as the default estimator score
    zo_scores = cval.cross_val_score(clf, iris.data, iris.target,
                                     scoring="accuracy", cv=5)
    assert_array_almost_equal(zo_scores, [1., 0.97, 0.90, 0.97, 1.], 2)

    # F1 score (class are balanced so f1_score should be equal to zero/one
    # score
    f1_scores = cval.cross_val_score(clf, iris.data, iris.target,
                                     scoring="f1", cv=5)
    assert_array_almost_equal(f1_scores, [1., 0.97, 0.90, 0.97, 1.], 2)
    # also test deprecated old way
    with warnings.catch_warnings(record=True):
        f1_scores = cval.cross_val_score(clf, iris.data, iris.target,
                                         score_func=f1_score, cv=5)
    assert_array_almost_equal(f1_scores, [1., 0.97, 0.90, 0.97, 1.], 2)


def test_cross_val_score_with_score_func_regression():
    X, y = make_regression(n_samples=30, n_features=20, n_informative=5,
                           random_state=0)
    reg = Ridge()

    # Default score of the Ridge regression estimator
    scores = cval.cross_val_score(reg, X, y, cv=5)
    assert_array_almost_equal(scores, [0.94, 0.97, 0.97, 0.99, 0.92], 2)

    # R2 score (aka. determination coefficient) - should be the
    # same as the default estimator score
    r2_scores = cval.cross_val_score(reg, X, y, scoring="r2", cv=5)
    assert_array_almost_equal(r2_scores, [0.94, 0.97, 0.97, 0.99, 0.92], 2)

    # Mean squared error; this is a loss function, so "scores" are negative
    mse_scores = cval.cross_val_score(reg, X, y, cv=5, scoring="mse")
    expected_mse = np.array([-763.07, -553.16, -274.38, -273.26, -1681.99])
    assert_array_almost_equal(mse_scores, expected_mse, 2)

    # Explained variance
    with warnings.catch_warnings(record=True):
        ev_scores = cval.cross_val_score(reg, X, y, cv=5,
                                         score_func=explained_variance_score)
    assert_array_almost_equal(ev_scores, [0.94, 0.97, 0.97, 0.99, 0.92], 2)


def test_permutation_score():
    iris = load_iris()
    X = iris.data
    X_sparse = coo_matrix(X)
    y = iris.target
    svm = SVC(kernel='linear')
    cv = cval.StratifiedKFold(y, 2)

    score, scores, pvalue = cval.permutation_test_score(
        svm, X, y, "accuracy", cv)
    assert_greater(score, 0.9)
    assert_almost_equal(pvalue, 0.0, 1)

    score_label, _, pvalue_label = cval.permutation_test_score(
        svm, X, y, "accuracy", cv, labels=np.ones(y.size), random_state=0)
    assert_true(score_label == score)
    assert_true(pvalue_label == pvalue)

    # test with custom scoring object
    scorer = make_scorer(fbeta_score, beta=2)
    score_label, _, pvalue_label = cval.permutation_test_score(
        svm, X, y, scoring=scorer, cv=cv, labels=np.ones(y.size),
        random_state=0)
    assert_almost_equal(score_label, .95, 2)
    assert_almost_equal(pvalue_label, 0.01, 3)

    # check that we obtain the same results with a sparse representation
    svm_sparse = SVC(kernel='linear')
    cv_sparse = cval.StratifiedKFold(y, 2, indices=True)
    score_label, _, pvalue_label = cval.permutation_test_score(
        svm_sparse, X_sparse, y, "accuracy", cv_sparse,
        labels=np.ones(y.size), random_state=0)

    assert_true(score_label == score)
    assert_true(pvalue_label == pvalue)

    # set random y
    y = np.mod(np.arange(len(y)), 3)

    score, scores, pvalue = cval.permutation_test_score(svm, X, y,
                                                        "accuracy", cv)

    assert_less(score, 0.5)
    assert_greater(pvalue, 0.4)

    # test with deprecated interface
    with warnings.catch_warnings(record=True):
        score, scores, pvalue = cval.permutation_test_score(
            svm, X, y, score_func=accuracy_score, cv=cv)
    assert_less(score, 0.5)
    assert_greater(pvalue, 0.4)


def test_cross_val_generator_with_mask():
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([1, 1, 2, 2])
    labels = np.array([1, 2, 3, 4])
    loo = cval.LeaveOneOut(4, indices=False)
    lpo = cval.LeavePOut(4, 2, indices=False)
    kf = cval.KFold(4, 2, indices=False)
    skf = cval.StratifiedKFold(y, 2, indices=False)
    lolo = cval.LeaveOneLabelOut(labels, indices=False)
    lopo = cval.LeavePLabelOut(labels, 2, indices=False)
    ss = cval.ShuffleSplit(4, indices=False)
    for cv in [loo, lpo, kf, skf, lolo, lopo, ss]:
        for train, test in cv:
            X_train, X_test = X[train], X[test]
            y_train, y_test = y[train], y[test]


def test_cross_val_generator_with_indices():
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([1, 1, 2, 2])
    labels = np.array([1, 2, 3, 4])
    loo = cval.LeaveOneOut(4, indices=True)
    lpo = cval.LeavePOut(4, 2, indices=True)
    kf = cval.KFold(4, 2, indices=True)
    skf = cval.StratifiedKFold(y, 2, indices=True)
    lolo = cval.LeaveOneLabelOut(labels, indices=True)
    lopo = cval.LeavePLabelOut(labels, 2, indices=True)
    b = cval.Bootstrap(2)  # only in index mode
    ss = cval.ShuffleSplit(2, indices=True)
    for cv in [loo, lpo, kf, skf, lolo, lopo, b, ss]:
        for train, test in cv:
            X_train, X_test = X[train], X[test]
            y_train, y_test = y[train], y[test]


def test_cross_val_generator_mask_indices_same():
    # Test that the cross validation generators return the same results when
    # indices=True and when indices=False
    y = np.array([0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2])
    labels = np.array([1, 1, 2, 3, 3, 3, 4])

    loo_mask = cval.LeaveOneOut(5, indices=False)
    loo_ind = cval.LeaveOneOut(5, indices=True)
    lpo_mask = cval.LeavePOut(10, 2, indices=False)
    lpo_ind = cval.LeavePOut(10, 2, indices=True)
    kf_mask = cval.KFold(10, 5, indices=False, shuffle=True, random_state=1)
    kf_ind = cval.KFold(10, 5, indices=True, shuffle=True, random_state=1)
    skf_mask = cval.StratifiedKFold(y, 3, indices=False)
    skf_ind = cval.StratifiedKFold(y, 3, indices=True)
    lolo_mask = cval.LeaveOneLabelOut(labels, indices=False)
    lolo_ind = cval.LeaveOneLabelOut(labels, indices=True)
    lopo_mask = cval.LeavePLabelOut(labels, 2, indices=False)
    lopo_ind = cval.LeavePLabelOut(labels, 2, indices=True)

    for cv_mask, cv_ind in [(loo_mask, loo_ind), (lpo_mask, lpo_ind),
                            (kf_mask, kf_ind), (skf_mask, skf_ind),
                            (lolo_mask, lolo_ind), (lopo_mask, lopo_ind)]:
        for (train_mask, test_mask), (train_ind, test_ind) in \
                zip(cv_mask, cv_ind):
            assert_array_equal(np.where(train_mask)[0], train_ind)
            assert_array_equal(np.where(test_mask)[0], test_ind)


def test_bootstrap_errors():
    assert_raises(ValueError, cval.Bootstrap, 10, train_size=100)
    assert_raises(ValueError, cval.Bootstrap, 10, test_size=100)
    assert_raises(ValueError, cval.Bootstrap, 10, train_size=1.1)
    assert_raises(ValueError, cval.Bootstrap, 10, test_size=1.1)


def test_bootstrap_test_sizes():
    assert_equal(cval.Bootstrap(10, test_size=0.2).test_size, 2)
    assert_equal(cval.Bootstrap(10, test_size=2).test_size, 2)
    assert_equal(cval.Bootstrap(10, test_size=None).test_size, 5)


def test_shufflesplit_errors():
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=2.0)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=1.0)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=0.1,
                  train_size=0.95)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=11)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=10)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=8, train_size=3)
    assert_raises(ValueError, cval.ShuffleSplit, 10, train_size=1j)
    assert_raises(ValueError, cval.ShuffleSplit, 10, test_size=None,
                  train_size=None)


def test_shufflesplit_reproducible():
    # Check that iterating twice on the ShuffleSplit gives the same
    # sequence of train-test when the random_state is given
    ss = cval.ShuffleSplit(10, random_state=21)
    assert_array_equal(list(a for a, b in ss), list(a for a, b in ss))


def test_cross_indices_exception():
    X = coo_matrix(np.array([[1, 2], [3, 4], [5, 6], [7, 8]]))
    y = np.array([1, 1, 2, 2])
    labels = np.array([1, 2, 3, 4])
    loo = cval.LeaveOneOut(4, indices=False)
    lpo = cval.LeavePOut(4, 2, indices=False)
    kf = cval.KFold(4, 2, indices=False)
    skf = cval.StratifiedKFold(y, 2, indices=False)
    lolo = cval.LeaveOneLabelOut(labels, indices=False)
    lopo = cval.LeavePLabelOut(labels, 2, indices=False)

    assert_raises(ValueError, cval.check_cv, loo, X, y)
    assert_raises(ValueError, cval.check_cv, lpo, X, y)
    assert_raises(ValueError, cval.check_cv, kf, X, y)
    assert_raises(ValueError, cval.check_cv, skf, X, y)
    assert_raises(ValueError, cval.check_cv, lolo, X, y)
    assert_raises(ValueError, cval.check_cv, lopo, X, y)
