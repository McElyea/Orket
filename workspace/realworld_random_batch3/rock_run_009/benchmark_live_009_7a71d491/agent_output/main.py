def sum_even(values):
    even_sum = 0
    for value in values:
        if value % 2 == 0:
            even_sum += value
    return even_sum