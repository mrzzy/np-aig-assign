#
# HAL
# continuous integration (ci) pipeline
#

PY:=python
PIP:=$(PY) -m pip
BLACK_FMT:=$(PY) -m black

.PHONY: deps format run

deps:
	$(PIP) install -r requirements.txt

lint: deps
	$(BLACK_FMT) --check .
	
format: deps
	$(BLACK_FMT) .

run: deps
	$(PY) HAL.py
