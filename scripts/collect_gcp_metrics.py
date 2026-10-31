import sys
from benchmark.cli import main

if __name__ == "__main__":
    main(["collect", *sys.argv[1:]])
