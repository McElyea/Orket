def second_largest(values):
    unique_values = list(set(values))
    unique_values.sort()
    return unique_values[-2]