# -*- coding: utf-8 -*-
"""Techniques that rely on classifying peak and/or baseline segments for fitting baselines.

Created on July 3, 2021
@author: Donald Erb

"""

from math import ceil
import warnings

import numpy as np
from scipy.ndimage import (
    binary_dilation, binary_erosion, grey_dilation, grey_erosion, uniform_filter1d
)
from scipy.optimize import curve_fit
from scipy.signal import cwt, ricker

from ._algorithm_setup import _get_vander, _setup_classification, _whittaker_smooth
from ._compat import jit
from .utils import (
    _MIN_FLOAT, ParameterWarning, _convert_coef, _interp_inplace, gaussian, optimize_window,
    pad_edges, relative_difference
)


def _remove_single_points(mask):
    """
    Removes lone True or False values from a boolean mask.

    Parameters
    ----------
    mask : numpy.ndarray
        The boolean array designating baseline points as True and peak points as False.

    Returns
    -------
    numpy.ndarray
        The input mask after removing lone True and False values.

    Notes
    -----
    Removes the lone True values first since True values designate the baseline.
    That way, the approach is more conservative with assigning baseline points.

    """
    # convert lone True values to False
    # same (check) as baseline_mask ^ binary_erosion(~baseline_mask, [1, 0, 1], border_value=1)
    temp = binary_erosion(mask, [1, 1, 0]) | binary_erosion(mask, [0, 1, 1])
    # convert lone False values to True
    return temp | binary_erosion(temp, [1, 0, 1])


def _find_peak_segments(mask):
    """
    Identifies the peak starts and ends from a boolean mask.

    Parameters
    ----------
    mask : numpy.ndarray
        The boolean mask with peak points as 0 or False and baseline points
        as 1 or True.

    Returns
    -------
    peak_starts : numpy.ndarray
        The array identifying the indices where each peak begins.
    peak_ends : numpy.ndarray
        The array identifying the indices where each peak ends.

    """
    extended_mask = np.concatenate(([True], mask, [True]))
    peak_starts = extended_mask[1:-1] < extended_mask[:-2]
    peak_starts = np.flatnonzero(peak_starts)
    if peak_starts.size:
        peak_starts[1 if peak_starts[0] == 0 else 0:] -= 1

    peak_ends = extended_mask[1:-1] < extended_mask[2:]
    peak_ends = np.flatnonzero(peak_ends)
    if peak_ends.size:
        peak_ends[:-1 if peak_ends[-1] == mask.shape[0] - 1 else None] += 1

    return peak_starts, peak_ends


def _averaged_interp(x, y, mask, interp_half_window=0):
    """
    Averages each anchor point and then interpolates between segments.

    Parameters
    ----------
    x : numpy.ndarray
        The x-values.
    y : numpy.ndarray
        The y-values.
    mask : numpy.ndarray
        A boolean array with 0 or False designating peak points and 1 or True
        designating baseline points.
    interp_half_window : int, optional
        The half-window to use for averaging around the anchor points before interpolating.
        Default is 0, which uses just the anchor point value.

    Returns
    -------
    output : numpy.ndarray
        A copy of the input `y` array with peak values in `mask` calulcated using linear
        interpolation.

    """
    output = y.copy()
    mask_sum = mask.sum()
    if not mask_sum:  # all points belong to peaks
        # will just interpolate between first and last points
        warnings.warn('there were no baseline points found', ParameterWarning)
    elif mask_sum == mask.shape[0]:  # all points belong to baseline
        warnings.warn('there were no peak points found', ParameterWarning)
        return output

    peak_starts, peak_ends = _find_peak_segments(mask)
    num_y = y.shape[0]
    for start, end in zip(peak_starts, peak_ends):
        left_mean = np.mean(
            y[max(0, start - interp_half_window):min(start + interp_half_window + 1, num_y)]
        )
        right_mean = np.mean(
            y[max(0, end - interp_half_window):min(end + interp_half_window + 1, num_y)]
        )
        _interp_inplace(x[start:end + 1], output[start:end + 1], left_mean, right_mean)

    return output


def golotvin(data, x_data=None, half_window=None, num_std=2.0, sections=32,
             smooth_half_window=None, interp_half_window=5, weights=None, **pad_kwargs):
    """
    Golotvin's method for identifying baseline regions.

    Divides the data into sections and takes the minimum standard deviation of all
    sections as the noise standard deviation for the entire data. Then classifies any point
    where the rolling max minus min is less than ``num_std * noise standard deviation``
    as belonging to the baseline.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    x_data : array-like, shape (N,), optional
        The x-values of the measured data. Default is None, which will create an
        array from -1 to 1 with N points.
    half_window : int, optional
        The half-window to use for the rolling maximum and rolling minimum calculations.
        Should be approximately equal to the full-width-at-half-maximum of the peaks or
        features in the data. Default is None, which will use half of the value from
        :func:`.optimize_window`, which is not always a good value, but at least scales
        with the number of data points and gives a starting point for tuning the parameter.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Higher values
        will assign more points as baseline. Default is 3.0.
    sections : int, optional
        The number of sections to divide the input data into for finding the minimum
        standard deviation.
    smooth_half_window : int, optional
        The half window to use for smoothing the interpolated baseline with a moving average.
        Default is None, which will use `half_window`. Set to 0 to not smooth the baseline.
    interp_half_window : int, optional
        When interpolating between baseline segments, will use the average of
        ``data[i-interp_half_window:i+interp_half_window+1]``, where `i` is
        the index of the peak start or end, to fit the linear segment. Default is 5.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from the moving average smoothing.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.

    References
    ----------
    Golotvin, S., et al. Improved Baseline Recognition and Modeling of
    FT NMR Spectra. Journal of Magnetic Resonance. 2000, 146, 122-125.

    """
    y, x, weight_array, *_ = _setup_classification(data, x_data, weights)
    if half_window is None:
        # optimize_window(y) / 2 gives an "okay" estimate that at least scales
        # with data size
        half_window = ceil(optimize_window(y) / 2)
    if smooth_half_window is None:
        smooth_half_window = half_window
    num_y = y.shape[0]
    min_sigma = np.inf
    for i in range(sections):
        # use ddof=1 since sampling subsets of the data
        min_sigma = min(
            min_sigma,
            np.std(y[i * num_y // sections:((i + 1) * num_y) // sections], ddof=1)
        )

    mask = (
        grey_dilation(y, 2 * half_window + 1) - grey_erosion(y, 2 * half_window + 1)
    ) < num_std * min_sigma
    mask = _remove_single_points(mask) & weight_array

    rough_baseline = _averaged_interp(x, y, mask, interp_half_window)
    baseline = uniform_filter1d(
        pad_edges(rough_baseline, smooth_half_window, **pad_kwargs),
        2 * smooth_half_window + 1
    )[smooth_half_window:num_y + smooth_half_window]

    return baseline, {'mask': mask}


def _iter_threshold(power, num_std=3.0):
    """
    Iteratively thresholds a power spectrum based on the mean and standard deviation.

    Any values greater than the mean of the power spectrum plus a multiple of the
    standard deviation are masked out to create a new power spectrum. The process
    is performed iteratively until no further points are masked out.

    Parameters
    ----------
    power : numpy.ndarray, shape (N,)
        The power spectrum to threshold.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Default is 3.0.

    Returns
    -------
    mask : numpy.ndarray, shape (N,)
        The boolean mask with True values where any point in the input power spectrum
        was less than

    References
    ----------
    Dietrich, W., et al. Fast and Precise Automatic Baseline Correction of One- and
    Two-Dimensional NMR Spectra. Journal of Magnetic Resonance. 1991, 91, 1-11.

    """
    mask = power < np.mean(power) + num_std * np.std(power, ddof=1)
    old_mask = np.ones_like(mask)
    while not np.array_equal(mask, old_mask):
        old_mask = mask
        masked_power = power[mask]
        if masked_power.size < 2:  # need at least 2 points for std calculation
            warnings.warn(
                'not enough baseline points found; "num_std" is likely too low',
                ParameterWarning
            )
            break
        mask = power < np.mean(masked_power) + num_std * np.std(masked_power, ddof=1)

    return mask


def dietrich(data, x_data=None, smooth_half_window=None, num_std=3.0,
             interp_half_window=5, poly_order=5, max_iter=50, tol=1e-3, weights=None,
             return_coef=False, **pad_kwargs):
    """
    Dietrich's method for identifying baseline regions.

    Calculates the power spectrum of the data as the squared derivative of the data.
    Then baseline points are identified by iteratively removing points where the mean
    of the power spectrum is less than `num_std` times the standard deviation of the
    power spectrum.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    x_data : array-like, shape (N,), optional
        The x-values of the measured data. Default is None, which will create an
        array from -1 to 1 with N points.
    smooth_half_window : int, optional
        The half window to use for smoothing the input data with a moving average.
        Default is None, which will use N / 256. Set to 0 to not smooth the data.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Higher values
        will assign more points as baseline. Default is 3.0.
    interp_half_window : int, optional
        When interpolating between baseline segments, will use the average of
        ``data[i-interp_half_window:i+interp_half_window+1]``, where `i` is
        the index of the peak start or end, to fit the linear segment. Default is 5.
    poly_order : int, optional
        The polynomial order for fitting the identified baseline. Default is 5.
    max_iter : int, optional
        The maximum number of iterations for fitting a polynomial to the identified
        baseline. If `max_iter` is 0, the returned baseline will be just the linear
        interpolation of the baseline segments. Default is 50.
    tol : float, optional
        The exit criteria for fitting a polynomial to the identified baseline points.
        Default is 1e-3.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    return_coef : bool, optional
        If True, will convert the polynomial coefficients for the fit baseline to
        a form that fits the input `x_data` and return them in the params dictionary.
        Default is False, since the conversion takes time.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from smoothing.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.
        * 'coef': numpy.ndarray, shape (poly_order,)
            Only if `return_coef` is True and `max_iter` is greater than 0. The array
            of polynomial coefficients for the baseline, in increasing order. Can be
            used to create a polynomial using numpy.polynomial.polynomial.Polynomial().
        * 'tol_history': numpy.ndarray
            Only if `max_iter` is greater than 1. An array containing the calculated
            tolerance values for each iteration. The length of the array is the number
            of iterations completed. If the last value in the array is greater than
            the input `tol` value, then the function did not converge.

    Notes
    -----
    When choosing parameters, first choose a `smooth_half_window` that appropriately
    smooths the data, and then reduce `num_std` until no peak regions are included in
    the baseline. If no value of `num_std` works, change `smooth_half_window` and repeat.

    If `max_iter` is 0, the baseline is simply a linear interpolation of the identified
    baseline points. Otherwise, a polynomial is iteratively fit through the baseline
    points, and the interpolated sections are replaced each iteration with the polynomial
    fit.

    References
    ----------
    Dietrich, W., et al. Fast and Precise Automatic Baseline Correction of One- and
    Two-Dimensional NMR Spectra. Journal of Magnetic Resonance. 1991, 91, 1-11.

    """
    y, x, weight_array, original_domain = _setup_classification(data, x_data, weights)
    num_y = y.shape[0]

    if smooth_half_window is None:
        smooth_half_window = ceil(num_y / 256)
    smooth_y = uniform_filter1d(
        pad_edges(y, smooth_half_window, **pad_kwargs),
        2 * smooth_half_window + 1
    )[smooth_half_window:num_y + smooth_half_window]
    power = np.diff(np.concatenate((smooth_y[:1], smooth_y)))**2
    mask = _iter_threshold(power, num_std)
    mask = _remove_single_points(mask) & weight_array
    rough_baseline = _averaged_interp(x, y, mask, interp_half_window)

    params = {'mask': mask}
    baseline = rough_baseline
    if max_iter > 0:
        vander, pseudo_inverse = _get_vander(x, poly_order)
        old_coef = coef = np.dot(pseudo_inverse, rough_baseline)
        baseline = np.dot(vander, coef)
        if max_iter > 1:
            tol_history = np.empty(max_iter - 1)
            for i in range(max_iter - 1):
                rough_baseline[mask] = baseline[mask]
                coef = np.dot(pseudo_inverse, rough_baseline)
                baseline = np.dot(vander, coef)
                calc_difference = relative_difference(old_coef, coef)
                tol_history[i] = calc_difference
                if calc_difference < tol:
                    break
                old_coef = coef
            params['tol_history'] = tol_history[:i + 1]

        if return_coef:
            params['coef'] = _convert_coef(coef, original_domain)

    return baseline, params


@jit(nopython=True, cache=True)
def _rolling_std(data, half_window, ddof=0):
    """
    Computes the rolling standard deviation of an array.

    Parameters
    ----------
    data : numpy.ndarray
        The array for the calculation. Should be padded on the left and right
        edges by `half_window`.
    half_window : int
        The half-window the rolling calculation. The full number of points for each
        window is ``half_window * 2 + 1``.
    ddof : int, optional
        The delta degrees of freedom for the calculation. Default is 0.

    Returns
    -------
    numpy.ndarray
        The array of the rolling standard deviation for each window.

    Notes
    -----
    This implementation is a version of Welford's method [1]_, modified for a
    fixed-length window [2]_. It is slightly modified from the version in [2]_
    in that it assumes the data is padded on the left and right. Other deviations
    from [2]_ are noted within the function.

    References
    ----------
    .. [1] https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance
    .. [2] Chmielowiec, A. Algorithm for error-free determination of the variance of all
           contiguous subsequences and fixed-length contiguous subsequences for a sequence
           of industrial measurement data. Computational Statistics. 2021, 1-28.

    """
    window_size = half_window * 2 + 1
    num_y = data.shape[0]
    squared_diff = np.zeros(num_y)
    mean = data[0]
    # fill the first window
    for i in range(1, window_size):
        val = data[i]
        size_factor = i / (i + 1)
        squared_diff[i] = squared_diff[i - 1] + 2 * size_factor * (val - mean)**2
        mean = mean * size_factor + val / (i + 1)
    # at this point, mean == np.mean(data[:window_size])

    # update squared_diff[half_window] with squared_diff[window_size - 1] / 2; if
    # this isn't done, all values within [half_window:-half_window] in the output are
    # off; no idea why... but it works
    squared_diff[half_window] = squared_diff[window_size - 1] / 2
    for j in range(half_window + 1, num_y - half_window):
        old_val = data[j - half_window - 1]
        new_val = data[j + half_window]
        val_diff = new_val - old_val  # reference divided by window_size here

        new_mean = mean + val_diff / window_size
        squared_diff[j] = squared_diff[j - 1] + val_diff * (old_val + new_val - mean - new_mean)
        mean = new_mean

    # empty the last half-window
    # TODO need to double-check this; not high priority since last half-window
    # is discarded currently
    size = window_size
    for k in range(num_y - half_window + 1, num_y):
        val = data[k]
        size_factor = size / (size - 1)
        squared_diff[k] = squared_diff[k - 1] + 2 * size_factor * (val - mean)**2
        mean = mean * size_factor + val / (size - 1)
        size -= 1

    return np.sqrt(squared_diff / (window_size - ddof))


def std_distribution(data, x_data=None, half_window=None, interp_half_window=5,
                     fill_half_window=3, num_std=1.1, smooth_half_window=None,
                     weights=None, **pad_kwargs):
    """
    Identifies baseline segments by analyzing the rolling standard deviation distribution.

    The rolling standard deviations are split into two distributions, with the smaller
    distribution assigned to noise. Baseline points are then identified as any point
    where the rolling standard deviation is less than a multiple of the median of the
    noise's standard deviation distribution.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    x_data : array-like, shape (N,), optional
        The x-values of the measured data. Default is None, which will create an
        array from -1 to 1 with N points.
    half_window : int, optional
        The half-window to use for the rolling standard deviation calculation. Should
        be approximately equal to the full-width-at-half-maximum of the peaks or features
        in the data. Default is None, which will use half of the value from
        :func:`.optimize_window`, which is not always a good value, but at least scales
        with the number of data points and gives a starting point for tuning the parameter.
    interp_half_window : int, optional
        When interpolating between baseline segments, will use the average of
        ``data[i-interp_half_window:i+interp_half_window+1]``, where `i` is
        the index of the peak start or end, to fit the linear segment. Default is 5.
    fill_half_window : int, optional
        When a point is identified as a peak point, all points +- `fill_half_window`
        are likewise set as peak points. Default is 3.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Higher values
        will assign more points as baseline. Default is 1.1.
    smooth_half_window : int, optional
        The half window to use for smoothing the interpolated baseline with a moving average.
        Default is None, which will use `half_window`. Set to 0 to not smooth the baseline.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from the moving average smoothing.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.

    References
    ----------
    Wang, K.C., et al. Distribution-Based Classification Method for Baseline
    Correction of Metabolomic 1D Proton Nuclear Magnetic Resonance Spectra.
    Analytical Chemistry. 2013, 85, 1231-1239.

    """
    y, x, weight_array, _ = _setup_classification(data, x_data, weights)
    if half_window is None:
        # optimize_window(y) / 2 gives an "okay" estimate that at least scales
        # with data size
        half_window = ceil(optimize_window(y) / 2)
    if smooth_half_window is None:
        smooth_half_window = half_window

    # use dof=1 since sampling a subset of the data; reflect the data since the
    # standard deviation calculation requires noisy data to work
    std = _rolling_std(np.pad(y, half_window, 'reflect'), half_window, 1)[half_window:-half_window]
    median = np.median(std)
    median_2 = np.median(std[std < 2 * median])  # TODO make the 2 an input?
    while median_2 / median < 0.999:  # TODO make the 0.999 an input?
        median = median_2
        median_2 = np.median(std[std < 2 * median])
    noise_std = median_2

    # use ~ to convert from peak==1, baseline==0 to peak==0, baseline==1; if done before,
    # would have to do ~binary_dilation(~mask) or binary_erosion(np.hstack((1, mask, 1))[1:-1]
    mask = np.logical_and(
        ~binary_dilation(std > num_std * noise_std, np.ones(2 * fill_half_window + 1)),
        weight_array
    )

    rough_baseline = _averaged_interp(x, y, mask, interp_half_window)

    baseline = uniform_filter1d(
        pad_edges(rough_baseline, smooth_half_window, **pad_kwargs),
        2 * smooth_half_window + 1
    )[smooth_half_window:y.shape[0] + smooth_half_window]

    return baseline, {'mask': mask}


def fastchrom(data, x_data=None, half_window=None, threshold=None, min_fwhm=None,
              interp_half_window=5, smooth_half_window=None, weights=None,
              max_iter=100, **pad_kwargs):
    """
    Identifies baseline segments by thresholding the rolling standard deviation distribution.

    Baseline points are identified as any point where the rolling standard deviation
    is less than the specified threshold. Peak regions are iteratively interpolated
    until the baseline is below the data.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    x_data : array-like, shape (N,), optional
        The x-values of the measured data. Default is None, which will create an
        array from -1 to 1 with N points.
    half_window : int, optional
        The half-window to use for the rolling standard deviation calculation. Should
        be approximately equal to the full-width-at-half-maximum of the peaks or features
        in the data. Default is None, which will use half of the value from
        :func:`.optimize_window`, which is not always a good value, but at least scales
        with the number of data points and gives a starting point for tuning the parameter.
    threshold : float, optional
        All points in the rolling standard deviation below `threshold` will be considered
        as baseline. Higher values will assign more points as baseline. Default is None,
        which will set the threshold as the 15th percentile of the rolling standard
        deviation.
    min_fwhm : int, optional
        After creating the interpolated baseline, any region where the baseline
        is greater than the data for `min_fwhm` consecutive points will have an additional
        baseline point added and reinterpolated. Should be set to approximately the
        index-based full-width-at-half-maximum of the smallest peak. Default is None,
        which uses 2 * `half_window`.
    interp_half_window : int, optional
        When interpolating between baseline segments, will use the average of
        ``data[i-interp_half_window:i+interp_half_window+1]``, where `i` is
        the index of the peak start or end, to fit the linear segment. Default is 5.
    smooth_half_window : int, optional
        The half window to use for smoothing the interpolated baseline with a moving average.
        Default is None, which will use `half_window`. Set to 0 to not smooth the baseline.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    max_iter : int, optional
        The maximum number of iterations to attempt to fill in regions where the baseline
        is greater than the input data. Default is 100.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from the moving average smoothing.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.

    Notes
    -----
    Only covers the baseline correction from FastChrom, not its peak finding and peak
    grouping capabilities.

    References
    ----------
    Johnsen, L., et al. An automated method for baseline correction, peak finding
    and peak grouping in chromatographic data. Analyst. 2013, 138, 3502-3511.

    """
    y, x, weight_array, _ = _setup_classification(data, x_data, weights)
    if half_window is None:
        # optimize_window(y) / 2 gives an "okay" estimate that at least scales
        # with data size
        half_window = ceil(optimize_window(y) / 2)
    if smooth_half_window is None:
        smooth_half_window = half_window
    if min_fwhm is None:
        min_fwhm = 2 * half_window

    # use dof=1 since sampling a subset of the data; reflect the data since the
    # standard deviation calculation requires noisy data to work
    std = _rolling_std(np.pad(y, half_window, 'reflect'), half_window, 1)[half_window:-half_window]
    if threshold is None:
        # scales fairly well with y and gaurantees baseline segments are created;
        # picked 15% since it seems to work better than 10%
        threshold = np.percentile(std, 15)

    # reference did not mention removing single points, but do so anyway to
    # be more thorough
    mask = _remove_single_points(std < threshold) & weight_array
    rough_baseline = _averaged_interp(x, y, mask, interp_half_window)

    mask_sum = mask.sum()
    # only try to fix peak regions if there actually are peak and baseline regions
    if mask_sum and mask_sum != mask.shape[0]:
        peak_starts, peak_ends = _find_peak_segments(mask)
        for _ in range(max_iter):
            modified_baseline = False
            for start, end in zip(peak_starts, peak_ends):
                baseline_section = rough_baseline[start:end + 1]
                data_section = y[start:end + 1]
                # mask should be baseline_section > data_section, but use the
                # inverse since _find_peak_segments looks for 0s, not 1s
                section_mask = baseline_section < data_section
                seg_starts, seg_ends = _find_peak_segments(section_mask)
                if np.any(seg_ends - seg_starts > min_fwhm):
                    modified_baseline = True
                    # designate lowest point as baseline
                    # TODO should surrounding points also be classified as baseline?
                    mask[np.argmin(data_section - baseline_section) + start] = 1

            if modified_baseline:
                # TODO probably faster to just re-interpolate changed sections
                rough_baseline = _averaged_interp(x, y, mask, interp_half_window)
            else:
                break

    # reference did not discuss smoothing, but include to be consistent with
    # other classification functions
    baseline = uniform_filter1d(
        pad_edges(rough_baseline, smooth_half_window, **pad_kwargs),
        2 * smooth_half_window + 1
    )[smooth_half_window:y.shape[0] + smooth_half_window]

    return baseline, {'mask': mask}


def cwt_br(data, x_data=None, poly_order=5, num_std=1.5, max_scale=50, mask_half_window=2,
           max_iter=50, tol=1e-3, weights=None, **pad_kwargs):
    """
    Continuous wavelet transform baseline recognition (CWT-BR) algorithm.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    x_data : array-like, shape (N,), optional
        The x-values of the measured data. Default is None, which will create an
        array from -1 to 1 with N points.
    poly_order : int, optional
        The polynomial order for fitting the baseline. Default is 5.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Default
        is 1.5.
    max_scale : int, optional
        [description]. Default is 50.
    mask_half_window : int, optional
        [description]. Default is 2.
    max_iter : int, optional
        The maximum number of iterations. Default is 50.
    tol : float, optional
        The exit criteria. Default is 1e-3.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from convolution for the
        continuous wavelet transform.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.
        * 'tol_history': numpy.ndarray
            An array containing the calculated tolerance values for
            each iteration. The length of the array is the number of iterations
            completed. If the last value in the array is greater than the input
            `tol` value, then the function did not converge.
        * 'best_scale' : scalar
            The scale at which the Shannon entropy of the continuous wavelet transform
            of the data is at a minimum.

    Notes
    -----
    Uses the standard deviation for determining outliers during polynomial fitting rather
    than the standard error as used in the reference since the number of standard errors
    to include when thresholding varies with data size while the number of standard
    deviations is independent of data size.

    References
    ----------
    Bertinetto, C., et al. Automatic Baseline Recognition for the Correction of Large
    Sets of Spectra Using Continuous Wavelet Transform and Iterative Fitting. Applied
    Spectroscopy, 2014, 68(2), 155-164.

    """
    y, x, weight_array, original_domain = _setup_classification(data, x_data, weights)
    vander = _get_vander(x, poly_order, None, False)
    # scale y between -1 and 1 so that the residual fit is more numerically stable
    y_domain = np.polynomial.polyutils.getdomain(y)
    y = np.polynomial.polyutils.mapdomain(y, y_domain, np.array([-1., 1.]))

    num_y = y.shape[0]
    shannon_old = -np.inf
    shannon_current = -np.inf
    half_window = max_scale * 2  # is x2 enough padding to prevent edge effects from cwt?
    padded_y = pad_edges(y, half_window, **pad_kwargs)
    # TODO should just allow inputting an array of scales; does not need
    # to be integers since ricker is valid for floats as well

    # set a min scale since there is a bit of noise at low scales
    min_scale = max(2, y.shape[0] // 500)
    for scale in range(min_scale, max_scale + 1):
        wavelet_cwt = cwt(padded_y, ricker, [scale])[0, half_window:-half_window]
        abs_wavelet = np.abs(wavelet_cwt)
        inner = abs_wavelet / abs_wavelet.sum(axis=0)
        # was not stated in the reference to use abs(wavelet) for the Shannon entropy,
        # but otherwise the Shannon entropy vs wavelet scale curve does not look like
        # Figure 2 in the reference; masking out non-positive values also gives an
        # incorrect entropy curve
        shannon_entropy = -np.sum(inner * np.log(inner + _MIN_FLOAT), 0)
        if shannon_current < shannon_old and shannon_entropy > shannon_current:
            break
        shannon_old = shannon_current
        shannon_current = shannon_entropy

    best_scale_ptp_multiple = 8 * (wavelet_cwt.max() - wavelet_cwt.min())
    num_bins = 200
    histogram, bin_edges = np.histogram(wavelet_cwt, num_bins)
    bins = 0.5 * (bin_edges[1:] + bin_edges[:-1])
    fit_params = [histogram.max(), np.log10(0.2 * np.std(wavelet_cwt))]
    # use 10**sigma so that sigma is not actually bounded
    gaussian_fit = lambda x, height, sigma: gaussian(x, height, 0, 10**sigma)
    # TODO should the number of iterations, the height cutoff for the histogram,
    # and the exit tol be parameters? The number of iterations is never greater than
    # 2 or 3, matching the reference. The height is
    for _ in range(10):
        fit_mask = histogram > histogram.max() / 5
        # histogram[~fit_mask] = 0  TODO use this instead? does it help fitting?
        fit_params = curve_fit(
            gaussian_fit, bins[fit_mask], histogram[fit_mask], fit_params,
            check_finite=False,
        )[0]
        sigma_opt = fit_params[1]

        new_num_bins = ceil(best_scale_ptp_multiple / sigma_opt)
        if relative_difference(num_bins, new_num_bins) < 0.05:
            break
        num_bins = new_num_bins
        histogram, bin_edges = np.histogram(wavelet_cwt, num_bins)
        bins = 0.5 * (bin_edges[1:] + bin_edges[:-1])

    gaussian_mask = np.abs(bins) < 3 * sigma_opt
    gaus_area = np.trapz(histogram[gaussian_mask], bins[gaussian_mask])
    num_sigma = 0.6 + 10 * ((np.trapz(histogram, bins) - gaus_area) / gaus_area)

    # pad since erosion considers borders as 0
    # TODO this operation should replace the current _remove_single_points function
    # since it is much more useful and gives significantly better results
    wavelet_mask = binary_erosion(
        np.pad(abs_wavelet < num_sigma * sigma_opt, mask_half_window, 'reflect'),
        np.ones(2 * mask_half_window + 1, bool)
    )[mask_half_window:-mask_half_window] & weight_array

    check_win = np.ones(2 * (num_y // 200) + 1, bool)  # TODO make window size a param
    baseline_old = y
    mask = wavelet_mask.copy()
    tol_history = np.empty(max_iter + 1)
    for i in range(max_iter + 1):
        coef = np.linalg.lstsq(vander[mask], y[mask], None)[0]
        baseline = vander.dot(coef)
        residual = y - baseline
        mask[residual > num_std * np.std(residual)] = False

        # TODO is this necessary? It improves fits where the initial fit didn't
        # include enough points, but ensures that negative peaks are not allowed;
        # maybe make it a param called symmetric, like for mixture_model, and only
        # do if not symmetric; also probably only need to do it the first iteration
        # since after that the masking above will not remove negative residuals
        coef = np.linalg.lstsq(vander[mask], y[mask], None)[0]
        baseline = vander.dot(coef)

        calc_difference = relative_difference(baseline_old, baseline)
        tol_history[i] = calc_difference
        if calc_difference < tol:
            break
        baseline_old = baseline
        added_points = binary_erosion(y < baseline, check_win)
        mask |= added_points

    # TODO should include wavelet_mask in params; maybe called 'initial_mask'?
    params = {
        'mask': mask, 'tol_history': tol_history[:i + 1], 'best_scale': scale
    }

    return baseline, params


def _haar(num_points, scale=2):
    # center at 0 rather than 1/2 to make calculation easier
    x_vals = np.arange(num_points) - (num_points - 1) / 2
    wavelet = np.zeros(num_points)
    # should be [-scale/2, 0) = 1, [0, scale/2) = -1, but that gives bad
    # results for odd scales since it is no longer symmetric; haar isn't meant to be
    # used for odd scales, but also don't want to ruin results; this weighting
    # scheme gives the desired output for even scales and a slightly different,
    # but at least symmetric output for odd scales; TODO could instead average
    # for odd scales... would that be valid? compare to pywavelets
    wavelet[(x_vals > -scale / 2) & (x_vals < 0)] = 1
    wavelet[(x_vals < scale / 2) & (x_vals > 0)] = -1

    # TODO not 100% sure about the 1/sqrt(scale) factor; using that
    # factor seems to closely match the output pywavelets's cwt with their Haar
    # implementation, but not perfectly so need to investigate further; may just
    # be due to different cwt implementations between scipy and pywavelets?
    # pywavelet's Haar implementation may also be defined in frequency space,
    # which could also cause slight deviations from this approach; besides, the
    # pywavelets cwt code had to be modified to even work with Haar, so maybe comparing
    # to their implementation is not the best idea...? Comparing scipy's ricker
    # with pywavelets's ricker shows the two are nearly identical, so should probably
    # include this 1/sqrt scaling
    # NOTE: the 1/sqrt(scale) is a normalization, so could make it a boolean input
    return wavelet / (np.sqrt(scale))


def fabc(data, lam=1e6, scale=None, num_std=3.0, diff_order=2, weights=None, **pad_kwargs):
    """
    Fully automatic baseline correction (fabc).

    Similar to Dietrich's method, except that the derivative is estimated using a
    continuous wavelet transform and the baseline is calculated using Whittaker
    smoothing through the identified baseline points.

    Parameters
    ----------
    data : array-like, shape (N,)
        The y-values of the measured data, with N data points.
    lam : float, optional
        The smoothing parameter. Larger values will create smoother baselines.
        Default is 1e6.
    scale : int, optional
        The scale at which to calculate the continuous wavelet transform. Should be
        approximately equal to the index-based full-width-at-half-maximum of the peaks
        or features in the data. Default is None, which will use half of the value from
        :func:`.optimize_window`, which is not always a good value, but at least scales
        with the number of data points and gives a starting point for tuning the parameter.
    num_std : float, optional
        The number of standard deviations to include when thresholding. Higher values
        will assign more points as baseline. Default is 3.0.
    diff_order : int, optional
        The order of the differential matrix. Must be greater than 0. Default is 2
        (second order differential matrix). Typical values are 2 or 1.
    weights : array-like, shape (N,), optional
        The weighting array, used to override the function's baseline identification
        to designate peak points. Only elements with 0 or False values will have
        an effect; all non-zero values are considered baseline points. If None
        (default), then will be an array with size equal to N and all values set to 1.
    **pad_kwargs
        Additional keyword arguments to pass to :func:`.pad_edges` for padding
        the edges of the data to prevent edge effects from convolution for the
        continuous wavelet transform.

    Returns
    -------
    baseline : numpy.ndarray, shape (N,)
        The calculated baseline.
    params : dict
        A dictionary with the following items:

        * 'mask': numpy.ndarray, shape (N,)
            The boolean array designating baseline points as True and peak points
            as False.

    Notes
    -----
    The classification of baseline points is similar to :func:`dietrich`, except that
    this method approximates the first derivative using a continous wavelet transform
    with the Haar wavelet, which is more robust than the numerical derivative in
    Dietrich's method.

    References
    ----------
    Cobas, J., et al. A new general-purpose fully automatic baseline-correction
    procedure for 1D and 2D NMR data. Journal of Magnetic Resonance, 2006, 183(1),
    145-151.

    """
    y, _, weight_array, _ = _setup_classification(data, None, weights)
    if scale is None:
        # optimize_window(y) / 2 gives an "okay" estimate that at least scales
        # with data size
        scale = ceil(optimize_window(y) / 2)

    half_window = scale * 2  # TODO is 2*scale enough padding to prevent edge effects from cwt?
    wavelet_cwt = cwt(pad_edges(y, half_window, **pad_kwargs), _haar, [scale])
    power = wavelet_cwt[0, half_window:-half_window]**2

    mask = _iter_threshold(power, num_std)
    mask = _remove_single_points(mask) & weight_array

    # TODO should allow a p value so that weights are mask * (1-p) + (~mask) * p
    # similar to mpls and mpspline?
    baseline, weight_array = _whittaker_smooth(y, lam, diff_order, mask.astype(float))

    # TODO should try to make this similar to mpls, where if weights are input, it does
    # nothing else and just calculates the baseline; that way, would be able to use with
    # optimizer functions; however, it would be different than all other classification
    # methods then...
    return baseline, {'mask': mask, 'weights': weight_array}
