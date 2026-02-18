def longest_common_prefix(values):
    if not values:
        return ''
    prefix = values[0]
    for value in values[1:]:
        while not value.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ''
    return prefix