import os

USER_BASE_DIR = os.path.expanduser('~/.virt-trinity')

if not os.path.isdir(USER_BASE_DIR):
    os.mkdir(USER_BASE_DIR)
