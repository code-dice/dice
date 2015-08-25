==================
Writing DICE Tests
==================

Anatomy of a DICE Project
=========================

The file structure of a basic DICE project likes::

    project_root
    |-- oracles
    |   `-- pyramid.yaml
    |-- item.py
    `-- utils

- An ``item.py`` is a python script defines how a single test item is run and pass
  the result to DICE for analysis.

- The ``oracles`` directory contains one or more YAML_ files defines the
  expected results for different conditions.

- The optional ``utils`` directory contains python helper modules to assist
  specific tests.


Writing Test Runner
===================

``item.py`` contains a class ``Item`` inherits from ``dice.item`` class from DICE`s
core API:

.. literalinclude:: ../../examples/pyramid/item.py


Writing Oracle
==============

An example oracle YAML_ file likes:

.. literalinclude:: ../../examples/pyramid/oracles/pyramid.yaml
    :language: yaml

Every oracle YAML_ file contains a list of oracle objects. For each
oracle, there is some predefined properties.

- ``name`` is the identifier of a specific oracle. It is recommended in
  CamelCase style to be differentiated from other variables.
- ``target`` is where this oracle is applied to for the test item.
- ``tree`` is a python style code snippet shows the expected result for a given
  conditions.

.. _YAML: http://yaml.org/spec/1.2/spec.html
