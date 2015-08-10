Getting Started
===============

Installing DICE
---------------

DICE is currently in experimental stage and not ready for release yet. So
easy-install or pip way of installation is not available now. The only way to install DICE is from the source code.

Install from Git Source
^^^^^^^^^^^^^^^^^^^^^^^

To install DICE from git repository, clone the source code to local first::

    git clone https://github.com/Hao-Liu/dice
    cd dice

Then install dependencies from pip::

    sudo pip install -r requirements.txt

Install DICE::

    sudo python setup.py install


Using DICE
----------

Example Project
^^^^^^^^^^^^^^^

Build the example binary from source::

    cd examples/pyramid
    gcc pyramid.c -o pyramid

Run DICE on the example project::

    dice --providers .

Create a new Project
^^^^^^^^^^^^^^^^^^^^

TBD

