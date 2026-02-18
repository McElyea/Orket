def group_anagrams(values):
    from collections import defaultdict
    anagram_dict = defaultdict(list)
    for word in values:
        sorted_word = ''.join(sorted(word))
        anagram_dict[sorted_word].append(word)
    return [sorted(group) for group in anagram_dict.values()]