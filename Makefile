PYTHON := /Users/theoauyeung/miniforge3/bin/python3.12
RSCRIPT := $(shell which Rscript)

.PHONY: install ingest features test clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

ingest:
	$(PYTHON) scripts/ingest.py

features:
	$(PYTHON) scripts/build_features.py

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/ff.duckdb
