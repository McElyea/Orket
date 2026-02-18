def group_anagrams(values):
    anagram_dict = {}
    for word in values:
        sorted_word = ''.join(sorted(word))
        if sorted_word not in anagram_dict:
            anagram_dict[sorted_word] = []
        anagram_dict[sorted_word].append(word)
    return [sorted(group) for group in anagram_dict.values()]