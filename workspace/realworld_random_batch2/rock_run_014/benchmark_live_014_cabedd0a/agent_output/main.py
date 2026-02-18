def second_largest(values):
    unique_values = list(set(values))
    if len(unique_values) < 2:
        return None
    unique_values.sort(reverse=True)
    return unique_values[1]