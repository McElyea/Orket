def group_anagrams(values):
    from collections import defaultdict
    anagrams = defaultdict(list)
    for word in values:
        sorted_word = ''.join(sorted(word))
        anagrams[sorted_word].append(word)
    return sorted([sorted(group) for group in anagrams.values()])