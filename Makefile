PYTHON := /Users/theoauyeung/miniforge3/bin/python3.12
RSCRIPT := $(shell which Rscript)

.PHONY: install ingest features train valuations test clean

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

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/ff.duckdb
