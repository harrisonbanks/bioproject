"""Entry point: python -m biointel <command> [args]."""
import sys

from biointel.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
