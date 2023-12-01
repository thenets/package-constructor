include ./dev-tools/common.mk

# =============
# Utils
# =============
venv:
	python3 -m venv venv
	venv/bin/pip install -U pip poetry
# - Install main packages
	export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
		&& venv/bin/poetry install
# - Install all dev packages
	export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
		&& venv/bin/poetry install --no-root \
			--with dev \
			--with test \
			--with audit
	venv/bin/poetry show --tree

.PHONY: clean
clean:
	rm -rf venv/
	rm -f requirements-freeze.txt
	find . -name 'cache' -type d -exec podman unshare chown -R 0:0 {} + || true
	find . -name 'cache' -type d -exec rm -rf {} + || true
	find . -name '__pycache__' -type d -exec rm -rf {} + || true

.PHONY: fmt
## Run code formatters and linters
fmt: venv
	./venv/bin/isort ./src/ --skip-glob '*/cache/*'
	./venv/bin/black -q ./src/ --force-exclude 'cache/'
	./venv/bin/ruff --fix ./src/ --exclude '*/cache/*'

.PHONY: lint
lint: venv
	@./venv/bin/ruff check ./src/
	@./venv/bin/bandit \
		-r ./src/ \
		--severity high

.PHONY: pre-commit
pre-commit: fmt lint

.PHONY: security-check
security-check: update-freeze
	./venv/bin/pip-audit -r requirements-freeze.txt

# =============
# Tests
# =============
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

# =============
# Dependencies
# =============
.PHONY: update-freeze
update-freeze: clean venv
# - Freeze only the virtualenv dependencies
	./venv/bin/poetry export --without-hashes --format=requirements.txt > requirements-freeze.txt

.PHONY: poetry-update
poetry-update:
	@set -x \
	&& export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring \
	&& venv/bin/poetry lock \
	&& venv/bin/poetry update \
	&& venv/bin/poetry show --tree
