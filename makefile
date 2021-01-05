#
# HAL
# continuous integration (ci) pipeline
#

PY:=python
PIP:=$(PY) -m pip
BLACK_FMT:=$(PY) -m black

.DEFAULT: run
.PHONY: deps format run

run: deps
	$(PY) HAL.py

deps:
	$(PIP) install -r requirements.txt

lint: deps
	$(BLACK_FMT) --check .
	
format: deps
	$(BLACK_FMT) .
