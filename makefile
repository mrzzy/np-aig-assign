#
# HAL
# continuous integration (ci) pipeline
#

PY:=python
PIP:=$(PY) -m pip
BLACK_FMT:=$(PY) -m black

.DEFAULT: run
.PHONY: deps format run run-trials

run: dep-pip
	$(PY) HAL.py
	
run-trials: dep-pip
	$(PY) HAL_Trials.py

lint: dep-pip
	$(BLACK_FMT) --check .

format: dep-pip
	$(BLACK_FMT) .

# dependency targets
deps: dep-pip

dep-pip:
	$(PIP) install -r requirements.txt
