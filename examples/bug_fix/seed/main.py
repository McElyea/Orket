"""Small label-normalization CLI with a deliberately seeded whitespace bug."""
import json
import sys


def normalize_label(value: str) -> str:
    return value.replace(" ", "-").lower()


if __name__ == "__main__":
    print(json.dumps(normalize_label(json.loads(sys.argv[1])), ensure_ascii=True))
