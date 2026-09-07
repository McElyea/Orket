import sys

from orket.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["runtime", *sys.argv[1:]]))
