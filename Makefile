.PHONY: test coverage experiment verify

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

coverage:
	PYTHONPATH=src python3 scripts/run_coverage.py

experiment:
	PYTHONPATH=src python3 scripts/run_experiment.py

verify: test coverage experiment
