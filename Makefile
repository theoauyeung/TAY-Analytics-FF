PYTHON := /Users/theoauyeung/miniforge3/bin/python3.12
RSCRIPT := $(shell which Rscript)

.PHONY: install ingest test clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

ingest:
	$(PYTHON) scripts/ingest.py

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/ff.duckdb
