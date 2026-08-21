PYTHON ?= python3

.PHONY: test demo proofs batch verify clean install

install:
	pip install -e .

test:
	$(PYTHON) -m unittest discover -s tests -t tests -v

demo:
	PYTHONPATH=src $(PYTHON) -m teacheraids.cli letter-tile --charset A-F --theme animal --out out
	PYTHONPATH=src $(PYTHON) -m teacheraids.cli clock-face --out out
	PYTHONPATH=src $(PYTHON) -m teacheraids.cli pattern-blocks --out out

proofs:
	$(PYTHON) tools/font_sheet.py --out proofs
	$(PYTHON) tools/pattern_sheet.py --out proofs

batch:
	PYTHONPATH=src $(PYTHON) -m teacheraids.cli batch --out out --keep-going

verify:
	PYTHONPATH=src $(PYTHON) -m teacheraids.cli verify out

clean:
	rm -rf out proofs
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
