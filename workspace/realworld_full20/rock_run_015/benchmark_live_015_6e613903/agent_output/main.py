def are_anagrams(a, b):
    a = a.replace(' ', '').lower()
    b = b.replace(' ', '').lower()
    return sorted(a) == sorted(b)