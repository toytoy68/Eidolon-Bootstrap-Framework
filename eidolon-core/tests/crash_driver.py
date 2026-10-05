import os
import sys

from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


def main():
    directory, identity, boundary = sys.argv[1:]

    def crash(kind):
        if kind == boundary:
            os._exit(77)

    Runtime(Store(directory), checkpoint=crash).run(identity)


if __name__ == "__main__":
    main()
