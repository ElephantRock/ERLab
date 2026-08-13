#!/usr/bin/env python3
"""Test fixture: exits 0 but writes no metrics.json."""
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
sys.exit(0)
