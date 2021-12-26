# -*- coding: utf-8 -*-
"""Tests for pybaselines._banded_utils.

@author: Donald Erb
Created on Dec. 11, 2021

"""

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
import pytest
from scipy.sparse import diags, identity, spdiags

from pybaselines import _banded_utils, _spline_utils


@pytest.mark.parametrize('data_size', (10, 1001))
@pytest.mark.parametrize('lower_only', (True, False))
def test_diff_2_diags(data_size, lower_only):
    """Ensures the output of _diff_2_diags is the correct shape and values."""
    diagonal_data = _banded_utils._diff_2_diags(data_size, lower_only)

    diff_matrix = _banded_utils.difference_matrix(data_size, 2)
    diag_matrix = (diff_matrix.T @ diff_matrix).todia()
    actual_diagonal_data = diag_matrix.data[::-1]
    if lower_only:
        actual_diagonal_data = actual_diagonal_data[2:]

    assert_array_equal(diagonal_data, actual_diagonal_data)


@pytest.mark.parametrize('data_size', (10, 1001))
@pytest.mark.parametrize('lower_only', (True, False))
def test_diff_1_diags(data_size, lower_only):
    """Ensures the output of _diff_1_diags is the correct shape and values."""
    diagonal_data = _banded_utils._diff_1_diags(data_size, lower_only)

    diff_matrix = _banded_utils.difference_matrix(data_size, 1)
    diag_matrix = (diff_matrix.T @ diff_matrix).todia()
    actual_diagonal_data = diag_matrix.data[::-1]
    if lower_only:
        actual_diagonal_data = actual_diagonal_data[1:]

    assert_array_equal(diagonal_data, actual_diagonal_data)


@pytest.mark.parametrize('data_size', (10, 1001))
@pytest.mark.parametrize('lower_only', (True, False))
def test_diff_3_diags(data_size, lower_only):
    """Ensures the output of _diff_3_diags is the correct shape and values."""
    diagonal_data = _banded_utils._diff_3_diags(data_size, lower_only)

    diff_matrix = _banded_utils.difference_matrix(data_size, 3)
    diag_matrix = (diff_matrix.T @ diff_matrix).todia()
    actual_diagonal_data = diag_matrix.data[::-1]
    if lower_only:
        actual_diagonal_data = actual_diagonal_data[3:]

    assert_array_equal(diagonal_data, actual_diagonal_data)


@pytest.mark.parametrize('data_size', (10, 1001))
@pytest.mark.parametrize('diff_order', (0, 1, 2, 3, 4, 5))
@pytest.mark.parametrize('lower_only', (True, False))
@pytest.mark.parametrize('padding', (-1, 0, 1, 2))
def test_diff_penalty_diagonals(data_size, diff_order, lower_only, padding):
    """
    Ensures the penalty matrix (squared finite difference matrix) diagonals are correct.

    Also tests the condition for when `data_size` < 2 * `diff_order` + 1 to ensure
    the slower, sparse route is taken.

    """
    diagonal_data = _banded_utils.diff_penalty_diagonals(
        data_size, diff_order, lower_only, padding
    )

    diff_matrix = _banded_utils.difference_matrix(data_size, diff_order)
    diag_matrix = (diff_matrix.T @ diff_matrix).todia()
    actual_diagonal_data = diag_matrix.data[::-1]
    if lower_only:
        actual_diagonal_data = actual_diagonal_data[diff_order:]
    if padding > 0:
        pad_layers = np.repeat(np.zeros((1, data_size)), padding, axis=0)
        if lower_only:
            actual_diagonal_data = np.concatenate((actual_diagonal_data, pad_layers))
        else:
            actual_diagonal_data = np.concatenate((pad_layers, actual_diagonal_data, pad_layers))

    assert_array_equal(diagonal_data, actual_diagonal_data)


def test_diff_penalty_diagonals_order_neg():
    """Ensures penalty matrix fails for negative order."""
    with pytest.raises(ValueError):
        _banded_utils.diff_penalty_diagonals(10, -1)


def test_diff_penalty_diagonals_datasize_too_small():
    """Ensures penalty matrix fails for data size <= 0."""
    with pytest.raises(ValueError):
        _banded_utils.diff_penalty_diagonals(0)
    with pytest.raises(ValueError):
        _banded_utils.diff_penalty_diagonals(-1)


def test_shift_rows_2_diags():
    """Ensures rows are correctly shifted for a matrix with two off-diagonals on either side."""
    matrix = np.array([
        [1, 2, 9, 0, 0],
        [1, 2, 3, 4, 0],
        [1, 2, 3, 4, 5],
        [0, 1, 2, 3, 8],
        [0, 0, 1, 2, 3]
    ])
    expected = np.array([
        [0, 0, 1, 2, 9],
        [0, 1, 2, 3, 4],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 8, 0],
        [1, 2, 3, 0, 0]
    ])
    output = _banded_utils._shift_rows(matrix, 2, 2)

    assert_array_equal(expected, output)
    # matrix should also be shifted since the changes are done in-place
    assert_array_equal(expected, matrix)


def test_shift_rows_1_diag():
    """Ensures rows are correctly shifted for a matrix with one off-diagonal on either side."""
    matrix = np.array([
        [1, 2, 3, 8, 0],
        [1, 2, 3, 4, 5],
        [0, 1, 2, 3, 4],
    ])
    expected = np.array([
        [0, 1, 2, 3, 8],
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 0],
    ])
    output = _banded_utils._shift_rows(matrix, 1, 1)

    assert_array_equal(expected, output)
    # matrix should also be shifted since the changes are done in-place
    assert_array_equal(expected, matrix)


def test_shift_rows_2_1_diags():
    """Tests shifting 2 upper diagonals and 1 lower diagonal."""
    matrix = np.array([
        [1, 2, 9, 0, 0],
        [1, 2, 3, 4, 0],
        [1, 2, 3, 4, 5],
        [0, 1, 2, 3, 8],
        [0, 0, 1, 2, 3]
    ])
    expected = np.array([
        [0, 0, 1, 2, 9],
        [0, 1, 2, 3, 4],
        [1, 2, 3, 4, 5],
        [0, 1, 2, 3, 8],
        [0, 1, 2, 3, 0]
    ])
    output = _banded_utils._shift_rows(matrix, 2, 1)

    assert_array_equal(expected, output)
    # matrix should also be shifted since the changes are done in-place
    assert_array_equal(expected, matrix)


def test_lower_to_full_simple():
    """Simple test for _lower_to_full."""
    lower = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 0],
        [8, 9, 0, 0]
    ])
    expected_full = np.array([
        [0, 0, 8, 9],
        [0, 5, 6, 7],
        [1, 2, 3, 4],
        [5, 6, 7, 0],
        [8, 9, 0, 0]
    ])

    output = _banded_utils._lower_to_full(lower)

    assert_array_equal(expected_full, output)


@pytest.mark.parametrize('num_knots', (100, 1000))
@pytest.mark.parametrize('spline_degree', (0, 1, 2, 3, 4, 5))
def test_lower_to_full(data_fixture, num_knots, spline_degree):
    """
    Ensures _lower_to_full correctly makes a full banded matrix from a lower banded matrix.

    Use ``B.T @ W @ B`` since most of the diagonals are different, so any issue in the
    calculation should show.

    """
    x, y = data_fixture
    # ensure x is a float
    x = x.astype(float, copy=False)
    # TODO replace with np.random.default_rng when min numpy version is >= 1.17
    weights = np.random.RandomState(0).normal(0.8, 0.05, x.size)
    weights = np.clip(weights, 0, 1)

    knots = _spline_utils._spline_knots(x, num_knots, spline_degree, True)
    basis = _spline_utils._spline_basis(x, knots, spline_degree)

    BTWB_full = (basis.T @ diags(weights, format='csr') @ basis).todia().data[::-1]
    BTWB_lower = BTWB_full[len(BTWB_full) // 2:]

    assert_allclose(_banded_utils._lower_to_full(BTWB_lower), BTWB_full, 1e-10, 1e-14)


@pytest.mark.parametrize('padding', (-1, 0, 1, 2))
@pytest.mark.parametrize('lower_only', (True, False))
def test_pad_diagonals(padding, lower_only):
    """Ensures padding is correctly applied to banded matrices."""
    array = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 0],
        [8, 9, 0, 0]
    ])
    output = _banded_utils._pad_diagonals(array, padding=padding, lower_only=lower_only)
    if padding < 1:
        expected_output = array
    else:
        layers = np.zeros((padding, array.shape[1]))
        if lower_only:
            expected_output = np.concatenate((array, layers))
        else:
            expected_output = np.concatenate((layers, array, layers))
    assert_array_equal(output, expected_output)


def test_add_diagonals_simple():
    """Basis example for _add_diagonals."""
    a = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [1, 2, 3, 4]
    ])
    b = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 8]
    ])
    expected_output = np.array([
        [2, 4, 6, 8],
        [10, 12, 14, 16],
        [1, 2, 3, 4]
    ])
    output = _banded_utils._add_diagonals(a, b)

    assert_array_equal(output, expected_output)


@pytest.mark.parametrize('diff_order_1', (0, 1, 2, 3, 4))
@pytest.mark.parametrize('diff_order_2', (0, 1, 2, 3, 4))
@pytest.mark.parametrize('lower_only', (True, False))
def test_add_diagonals(diff_order_1, diff_order_2, lower_only):
    """Ensure _add_diagonals works for a broad range of matrices."""
    points = 100
    a = _banded_utils.diff_penalty_diagonals(points, diff_order_1, lower_only)
    b = _banded_utils.diff_penalty_diagonals(points, diff_order_2, lower_only)

    output = _banded_utils._add_diagonals(a, b, lower_only)

    a_offsets = np.arange(diff_order_1, -diff_order_1 - 1, -1)
    b_offsets = np.arange(diff_order_2, -diff_order_2 - 1, -1)
    a_matrix = spdiags(
        _banded_utils.diff_penalty_diagonals(points, diff_order_1, False),
        a_offsets, points, points, 'csr'
    )
    b_matrix = spdiags(
        _banded_utils.diff_penalty_diagonals(points, diff_order_2, False),
        b_offsets, points, points, 'csr'
    )
    expected_output = (a_matrix + b_matrix).todia().data[::-1]
    if lower_only:
        expected_output = expected_output[len(expected_output) // 2:]

    assert_allclose(output, expected_output, 0, 1e-10)


def test_add_diagonals_fails():
    """Ensure _add_diagonals properly raises errors."""
    a = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [1, 2, 3, 4]
    ])
    b = np.array([
        [1, 2, 3, 4],
        [5, 6, 7, 8]
    ])

    # row mismatch is not a multiple of 2 when lower_only=False
    with pytest.raises(ValueError):
        _banded_utils._add_diagonals(a, b, lower_only=False)

    # mismatched number of columns
    with pytest.raises(ValueError):
        _banded_utils._add_diagonals(a[:, 1:], b)


@pytest.mark.parametrize('diff_order', (0, 1, 2, 3, 4, 5))
def test_difference_matrix(diff_order):
    """Tests common differential matrices."""
    diff_matrix = _banded_utils.difference_matrix(10, diff_order).toarray()
    numpy_diff = np.diff(np.eye(10), diff_order, axis=0)

    assert_array_equal(diff_matrix, numpy_diff)


def test_difference_matrix_order_2():
    """
    Tests the 2nd order differential matrix against the actual representation.

    The 2nd order differential matrix is most commonly used,
    so double-check that it is correct.
    """
    diff_matrix = _banded_utils.difference_matrix(8, 2).toarray()
    actual_matrix = np.array([
        [1, -2, 1, 0, 0, 0, 0, 0],
        [0, 1, -2, 1, 0, 0, 0, 0],
        [0, 0, 1, -2, 1, 0, 0, 0],
        [0, 0, 0, 1, -2, 1, 0, 0],
        [0, 0, 0, 0, 1, -2, 1, 0],
        [0, 0, 0, 0, 0, 1, -2, 1]
    ])

    assert_array_equal(diff_matrix, actual_matrix)


def test_difference_matrix_order_0():
    """
    Tests the 0th order differential matrix against the actual representation.

    The 0th order differential matrix should be the same as the identity matrix,
    so double-check that it is correct.
    """
    diff_matrix = _banded_utils.difference_matrix(10, 0).toarray()
    actual_matrix = identity(10).toarray()

    assert_array_equal(diff_matrix, actual_matrix)


def test_difference_matrix_order_neg():
    """Ensures differential matrix fails for negative order."""
    with pytest.raises(ValueError):
        _banded_utils.difference_matrix(10, diff_order=-2)


def test_difference_matrix_order_over():
    """
    Tests the (n + 1)th order differential matrix against the actual representation.

    If n is the number of data points and the difference order is greater than n,
    then differential matrix should have a shape of (0, n) with 0 stored elements,
    following a similar logic as np.diff.

    """
    diff_matrix = _banded_utils.difference_matrix(10, 11).toarray()
    actual_matrix = np.empty(shape=(0, 10))

    assert_array_equal(diff_matrix, actual_matrix)


def test_difference_matrix_size_neg():
    """Ensures differential matrix fails for negative data size."""
    with pytest.raises(ValueError):
        _banded_utils.difference_matrix(-1)


@pytest.mark.parametrize('form', ('dia', 'csc', 'csr'))
def test_difference_matrix_formats(form):
    """
    Ensures that the sparse format is correctly passed to the constructor.

    Tests both 0-order and 2-order, since 0-order uses a different constructor.
    """
    assert _banded_utils.difference_matrix(10, 2, form).format == form
    assert _banded_utils.difference_matrix(10, 0, form).format == form
