def sum_even(values):
    total = 0
    for value in values:
        if value % 2 == 0:
            total += value
    return total