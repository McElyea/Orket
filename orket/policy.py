import json
import os
from orket.filesystem import FilesystemPolicy


def load_policy():
    # Load spaces
    with open("permissions.json", "r", encoding="utf-8") as f:
        spaces = json.load(f)

    # Load policy rules
    with open("policy.json", "r", encoding="utf-8") as f:
        policy = json.load(f)

    return FilesystemPolicy(spaces, policy)
