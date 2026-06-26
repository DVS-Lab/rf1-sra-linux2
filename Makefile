PYTHON ?= python3
PYTHONPYCACHEPREFIX ?= /private/tmp/rf1-sra-linux2-pycache

.PHONY: test

test:
	bash scripts/check_shell_syntax.sh
	PYTHONPYCACHEPREFIX=$(PYTHONPYCACHEPREFIX) $(PYTHON) -m compileall code tests scripts
	$(PYTHON) -m pytest -q -p no:cacheprovider
	$(PYTHON) scripts/validate_repo.py
