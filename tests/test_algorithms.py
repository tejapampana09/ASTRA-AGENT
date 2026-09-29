import pytest
from astra.algorithms import max_subarray_sum, max_subarray_sum_with_indices

def test_max_subarray_sum_basic():
    # Standard example with positive and negative numbers
    assert max_subarray_sum([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6  # [4, -1, 2, 1]

def test_max_subarray_sum_all_positive():
    assert max_subarray_sum([1, 2, 3, 4, 5]) == 15

def test_max_subarray_sum_all_negative():
    # Kadane's algorithm handling all negative numbers (returns max single element)
    assert max_subarray_sum([-5, -1, -3, -4]) == -1

def test_max_subarray_sum_single_element():
    assert max_subarray_sum([42]) == 42

def test_max_subarray_sum_empty():
    with pytest.raises(ValueError):
        max_subarray_sum([])

def test_max_subarray_sum_with_indices():
    nums = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
    max_sum, start, end = max_subarray_sum_with_indices(nums)
    assert max_sum == 6
    assert nums[start:end+1] == [4, -1, 2, 1]
