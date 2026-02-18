def second_largest(values):
    unique_values = list(set(values))
    unique_values.sort(reverse=True)
    return unique_values[1]