def rotate_right(values, k):
    n = len(values)
    if n == 0:
        return values
    k = k % n
    return values[-k:] + values[:-k]