==================
Writing DICE Tests
==================

Anatomy of a DICE Project
=========================

The file structure of a basic DICE project likes::

    project_root
    |-- constraints
    |   `-- pyramid.yaml
    |-- item.py
    `-- utils

- An ``item.py`` is a python script defines how a single test item is run and pass
  the result to DICE for analysis.

- The ``constraints`` directory contains one or more YAML_ files defines the
  expected results for different conditions.

- The optional ``utils`` directory contains python helper modules to assist
  specific tests.


Writing Test Runner
===================

``item.py`` contains a class ``Item`` inherits from ``dice.item`` class from DICE`s
core API:

.. literalinclude:: ../../examples/pyramid/item.py


Writing Constraint
==================

An example constraint YAML_ file likes:

.. literalinclude:: ../../examples/pyramid/die/pyramid.yaml
    :language: yaml

Every constraint YAML_ file contains a list of constraint objects. For each
constraint, there is some predefined properties.

- ``name`` is the identifier of a specific constraint. It is recommended in
  CamelCase style to be differentiated from other variables.
- ``target`` is where this constraint is applied to for the test item.
- ``tree`` is a python style code snippet shows the expected result for a given
  conditions.

.. _YAML: http://yaml.org/spec/1.2/spec.html
