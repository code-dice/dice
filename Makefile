PYTHON ?= python

all:
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install

clean:
	$(PYTHON) setup.py clean

check: all
	$(PYTHON) setup.py test

rpm:
	$(PYTHON) setup.py bdist_rpm \
	  --requires PyYAML,python-requests,python-tox,python-future
