.PHONY: install run scrape models revenue transit viz clean

install:
	pip install -r requirements.txt --break-system-packages
	playwright install chromium

run:
	python main.py

scrape:
	python main.py --scrape

models:
	python main.py --models

revenue:
	python main.py --revenue

transit:
	python main.py --transit

cannibalization:
	python main.py --cannibalization

viz:
	python main.py --viz-only

clean:
	rm -f data/processed/*.csv data/processed/*.pkl reports/*.png reports/*.log

lint:
	ruff check .

fmt:
	black .

test:
	pytest tests/ -v
