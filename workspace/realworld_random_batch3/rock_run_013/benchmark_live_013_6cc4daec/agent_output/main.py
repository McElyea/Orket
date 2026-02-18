def rotate_right(values, k):
    n = len(values)
    k = k % n
    return values[-k:] + values[:-k]