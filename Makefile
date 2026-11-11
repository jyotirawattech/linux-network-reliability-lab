.PHONY: test coverage experiment compare-policies verify

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

coverage:
	PYTHONPATH=src python3 scripts/run_coverage.py

experiment:
	PYTHONPATH=src python3 scripts/run_experiment.py

compare-policies:
	PYTHONPATH=src python3 scripts/compare_policies.py

verify: test coverage experiment compare-policies
