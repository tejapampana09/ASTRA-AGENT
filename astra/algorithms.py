"""
Algorithms and utility functions.
"""

from typing import List, Tuple

def max_subarray_sum(nums: List[int]) -> int:
    """
    Finds the maximum sum of a contiguous subarray within a one-dimensional array of numbers
    using Kadane's algorithm.

    Args:
        nums: A list of integers (can be positive, negative, or zero).

    Returns:
        The maximum sum of a contiguous subarray. If the list is empty, raises ValueError.
    """
    if not nums:
        raise ValueError("Array must not be empty")

    max_current = max_global = nums[0]

    for num in nums[1:]:
        max_current = max(num, max_current + num)
        if max_current > max_global:
            max_global = max_current

    return max_global


def max_subarray_sum_with_indices(nums: List[int]) -> Tuple[int, int, int]:
    """
    Finds the maximum sum of a contiguous subarray and returns both the sum and the 
    start/end indices (inclusive) of the subarray.

    Args:
        nums: A list of integers.

    Returns:
        A tuple of (max_sum, start_index, end_index).
    """
    if not nums:
        raise ValueError("Array must not be empty")

    max_current = max_global = nums[0]
    start = end = temp_start = 0

    for i in range(1, len(nums)):
        num = nums[i]
        if num > max_current + num:
            max_current = num
            temp_start = i
        else:
            max_current = max_current + num

        if max_current > max_global:
            max_global = max_current
            start = temp_start
            end = i

    return max_global, start, end
