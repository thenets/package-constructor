venv:
	python3 -m venv venv
	venv/bin/pip install -U pip
	venv/bin/pip install -r requirements-dev.txt

.PHONY: clean
clean:
	rm -rf venv/

.PHONY: fmt
fmt: venv
	./venv/bin/isort ./src/
	./venv/bin/black -q ./src/
	./venv/bin/ruff --fix ./src/

.PHONY: lint
lint: venv
	@./venv/bin/ruff check ./src/

.PHONY: test
test:
	@echo "You can pass custom args: make test ARGS='-k test_something'"
	@echo
	./venv/bin/pytest -c ./pyproject.toml $(ARGS)

.PHONY: update-freeze
update-freeze: clean venv
	./venv/bin/pip freeze > requirements-freeze.txt
	make _audit --no-print-directory
	make clean venv --no-print-directory

_audit:
	./venv/bin/pip install -U pip-audit
	./venv/bin/pip-audit -r requirements-freeze.txt
