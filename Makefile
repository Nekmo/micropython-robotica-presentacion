# Minimal makefile for Sphinx documentation

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build
SASSC         ?= sassc

.PHONY: help Makefile css revealjs serve upload model check-demos

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

css:
	$(SASSC) _static/theme.scss _static/theme.css

revealjs: css
	@$(SPHINXBUILD) -b revealjs "$(SOURCEDIR)" "$(BUILDDIR)/revealjs" $(SPHINXOPTS) $(O)

# Web Serial and the camera need a secure context: serve over localhost
serve: revealjs
	python3 -m http.server -d "$(BUILDDIR)/revealjs" 8000

# Upload the Stack-chan firmware port (robot/) to the robot over USB;
# robot/main.py starts the full firmware on boot
MPYTOOL ?= mpytool
upload:
	$(MPYTOOL) mkdir libs || true
	$(MPYTOOL) cp -r robot/libs/stackchan :libs/
	$(MPYTOOL) mkdir res || true
	$(MPYTOOL) mkdir res/stackchan || true
	$(MPYTOOL) cp robot/res/stackchan/*.png :res/stackchan/
	$(MPYTOOL) cp robot/main.py :main.py

# Export the Blender model to glTF for the 3D slides
BLENDER ?= blender
model:
	$(BLENDER) --background --python models/export_stackchan.py -- models/stackchan.blend _static/models/stackchan.glb

check-demos:
	python3 -m py_compile demos/*/*.py robot/main.py
	@echo OK

%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
