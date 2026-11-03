"""Frozen standalone entry; contains no GUI runtime from the application."""
from companion.update_helper import main

if __name__ == "__main__":
    raise SystemExit(main())
