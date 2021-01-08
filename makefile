#
# HAL
# continuous integration (ci) pipeline
#

PY:=python
PIP:=$(PY) -m pip
BLACK_FMT:=$(PY) -m black

.DEFAULT: run
.PHONY: deps format run

run: dep-pip
	env DIFFICULTY=hard CAMERA=OpenCVCamera HEADLESS=True $(PY) HAL.py

lint: dep-pip
	$(BLACK_FMT) --check .

format: dep-pip
	$(BLACK_FMT) .

# dependency targets
deps: dep-pip

dep-pip:
	$(PIP) install -r requirements.txt
