.PHONY: install validate test demo api lint package

install:
	python -m pip install -e '.[dev]'

validate:
	python scripts/validate.py

test:
	python -m unittest discover -s tests -v

demo:
	python scripts/demo.py

api:
	uvicorn cano_hermes.api.app:app --reload --port 8787

lint:
	ruff check .

package:
	python scripts/package_release.py
