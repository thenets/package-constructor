venv:
	python3 -m venv venv
	venv/bin/pip install -U pip
	venv/bin/pip install -r requirements.txt

clean:
	rm -rf venv/

fmt: venv
	./venv/bin/black -q ./src/
	./venv/bin/ruff --fix ./src/

lint: venv
	@./venv/bin/ruff check ./src/
