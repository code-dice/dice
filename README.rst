====
DICE
====

.. image:: https://travis-ci.org/Hao-Liu/dice.svg?branch=master
    :target: https://travis-ci.org/Hao-Liu/dice
.. image:: https://coveralls.io/repos/Hao-Liu/dice/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/Hao-Liu/dice?branch=master
.. image:: https://readthedocs.org/projects/dice/badge/?version=latest
    :target: https://readthedocs.org/projects/dice/?badge=latest
    :alt: Documentation Status

DICE is a black-box random testing framework.

Goals and Objectives
====================

- Provides professional random testing.
- Apply to your project with minimal effort.
- Human friendly configuration process.

Getting Started
======================

DICE is currently in experimental stage and not ready for release yet. So
easy-install or pip way of installation is not available now. The only way to install DICE is from the source code.

Install from Git Source
-----------------------

To install DICE from git repository, clone the source code to local first::

    git clone https://github.com/Hao-Liu/dice
    cd dice

Then install dependencies from pip::

    sudo pip install -r requirements.txt

Install DICE::

    sudo python setup.py install


Run the Example Project
-----------------------

Build the example binary from source::

    cd examples/pyramid
    gcc pyramid.c -o pyramid

Run DICE on the example project::

    dice

This will open a ncurses TUI shows the statistics of results by generating the
option randomly.

.. image:: dice-screenshot.png

The left panel is a **stat panel** shows the stat of error message patterns
categorized by the exit status and whether error message matches expectation
defined in the constraint file.

The central panel is a **list panel** lists recent called command lines matches
the error message pattern selecting in the **stat panel**.

The right panel is a **detail panel** show the detailed information of the
selected command in **list panel** includes command line, standard output and
standard error.

The follow key press allowing navigation through the panels.

+-----+------------------------------+
| Key | Function                     |
+=====+==============================+
| TAB | Toggle current working panel |
+-----+------------------------------+
| Q   | Exit DICE                    |
+-----+------------------------------+
| P   | Pause/Resume execution       |
+-----+------------------------------+
| J   | Select next item             |
+-----+------------------------------+
| K   | Select previous item         |
+-----+------------------------------+
| M   | Merge stat by regex pattern  |
+-----+------------------------------+
| ^W  | Save current input           |
+-----+------------------------------+
| ^D  | Cancel current input         |
+-----+------------------------------+

Documentation
=============

All documentation is online at https://dice.readthedocs.org/en/latest/.

Contribute
==========

Bug reporting, issues and patches to both code and documentation are welcome on
Github_.

`Contribution Guideline`: http://dice.readthedocs.org/en/latest/contribute.html

Reference
=========

.. _Github: https://github.com/Hao-Liu/dice
.. _`Getting Started`: http://dice.readthedocs.org/en/latest/get_start.html
.. _Documentation: https://dice.readthedocs.org/en/latest/
