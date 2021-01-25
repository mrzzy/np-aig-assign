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
	env DIFFICULTY=hard DEBUG=True REAL_TIME=False RANDOM_SEED=7479057933734829 $(PY) HAL.py
	
run-trials: dep-pip
	$(PY) HALTrials.py

lint: dep-pip
	$(BLACK_FMT) --check .

format: dep-pip
	$(BLACK_FMT) .

# dependency targets
deps: dep-pip

dep-pip:
	$(PIP) install -r requirements.txt
