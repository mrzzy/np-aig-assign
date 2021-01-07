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
	$(PY) HAL.py

lint: deps
	$(BLACK_FMT) --check .
	
format: deps
	$(BLACK_FMT) .

# dependency targets
deps: dep-pip dep-ffmpeg
	
dep-pip: 
	$(PIP) install -r requirements.txt

dep-ffmpeg:
	sudo apt-get update
	sudo apt-get install -y ffmpeg
