"""Module entry: python -m backend.app.data_generator [--mode full] [--seed 20261022]"""
import sys

from backend.app.data_generator.generate import main

if __name__ == "__main__":
    sys.exit(main())

