PYTHON := /Users/theoauyeung/miniforge3/bin/python3.12
RSCRIPT := $(shell which Rscript)

.PHONY: install ingest features train valuations simulate draft test clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

ingest:
	$(PYTHON) scripts/ingest.py

features:
	$(PYTHON) scripts/build_features.py

train:
	$(PYTHON) scripts/train_models.py

valuations:
	$(PYTHON) scripts/compute_valuations.py

simulate:
	$(PYTHON) scripts/run_simulation.py

draft:
	$(PYTHON) scripts/run_draft.py

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/ff.duckdb
