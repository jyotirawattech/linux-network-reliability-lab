.PHONY: test coverage experiment compare-policies compare-delivery verify

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

coverage:
	PYTHONPATH=src python3 scripts/run_coverage.py

experiment:
	PYTHONPATH=src python3 scripts/run_experiment.py

compare-policies:
	PYTHONPATH=src python3 scripts/compare_policies.py

compare-delivery:
	@PYTHONPATH=src python3 -m reliability_lab.delivery_experiment

verify: test coverage experiment compare-policies compare-delivery
