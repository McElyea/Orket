def max_in_list(values):
    current_max = values[0]
    for value in values:
        if value > current_max:
            current_max = value
    return current_max