#!/usr/bin/env python3
"""Print the offline detection-policy experiment; no files or sockets are opened."""

import json

from reliability_lab.policy_experiment import run_policy_comparison


if __name__ == "__main__":
    print(json.dumps(run_policy_comparison(), indent=2, sort_keys=True))
