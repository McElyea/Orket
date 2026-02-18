def max_in_list(values):
    max_value = values[0]
    for value in values:
        if value > max_value:
            max_value = value
    return max_value