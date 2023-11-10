venv:
	python3 -m venv venv
	venv/bin/pip install -U pip poetry
	export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
		&& venv/bin/poetry install --no-root --with dev --with test
	venv/bin/poetry show --tree

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
## Run tests
test:
	@echo "You can pass custom args: make test ARGS='-k test_something'"
	@echo
	./venv/bin/pytest -c ./pyproject.toml $(ARGS)

.PHONY: test-dev
## Run tests without restarting or stopping the Cachito server
test-dev:
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
