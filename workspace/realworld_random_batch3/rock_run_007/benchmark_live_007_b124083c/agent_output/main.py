def is_palindrome(s):
    cleaned_s = s.lower()
    return cleaned_s == cleaned_s[::-1]