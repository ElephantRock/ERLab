#!/usr/bin/env python3
"""Test fixture: exits 0 but writes malformed metrics.json."""
import argparse
import json
import os
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

os.makedirs(args.output, exist_ok=True)
with open(os.path.join(args.output, "metrics.json"), "w") as f:
    json.dump({"metrics": {"accuracy": "not_a_number"}}, f)
sys.exit(0)
