import sys

from delivery.cli import _main

if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
