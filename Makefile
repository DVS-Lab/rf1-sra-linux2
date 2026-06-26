PYTHON ?= python3
PYTHONPYCACHEPREFIX ?= /private/tmp/rf1-sra-linux2-pycache

.PHONY: test

test:
	bash code/check_shell_syntax.sh
	PYTHONPYCACHEPREFIX=$(PYTHONPYCACHEPREFIX) $(PYTHON) -m compileall code tests
	$(PYTHON) -m pytest -q -p no:cacheprovider
	$(PYTHON) code/validate_repo.py
