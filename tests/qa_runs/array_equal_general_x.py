def can_make_equal(arr, x):
    # Empty or single element: trivially already "all equal".
    if len(arr) <= 1:
        return True

    # x = 0: the operation (±0) changes nothing, so the array
    # can only be all-equal if it ALREADY is.
    if x == 0:
        return all(a == arr[0] for a in arr)

    # x and -x define the same remainder lanes; normalize.
    x = abs(x)

    # Invariant: ±x never changes (value mod x).
    # All elements can meet iff they share one remainder lane.
    ref = arr[0] % x            # Python % normalizes negatives into [0, x)
    for a in arr[1:]:
        if a % x != ref:
            return False        # different lane -> impossible
    return True
