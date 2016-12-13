import fnmatch
import imp
import importlib
import inspect
import logging
import os

from . import constraint

logger = logging.getLogger('dice')


class ProviderError(Exception):
    """
    Class for provider specific exceptions.
    """
    pass


class Provider(object):
    """
    Class for a dice test provider.
    """
    def __init__(self, path):
        """
        :param path: Path of the directory this provider locates.
        """
        if not os.path.isdir(path):
            raise ProviderError("%s is not a directory." % path)

        self.name = os.path.basename(os.path.abspath(os.path.normpath(path)))
        self.path = path

        self.modules = {}

        root = os.path.join(path, 'utils')
        files = [f for f in os.listdir(root)
                 if os.path.isfile(os.path.join(root, f))]

        relative_path = os.path.relpath(root, path)
        folders = os.path.split(relative_path)
        root_ns = self.name + '_' + '.'.join(
            [folder for folder in folders if folder not in ['', '.']])

        if '__init__.py' in files:
            files.remove('__init__.py')

        init_path = os.path.join(root, '__init__.py')
        open(init_path, 'a').close()
        files.insert(0, '__init__.py')

        for file_name in fnmatch.filter(files, '*.py'):
            mod_name, _ = os.path.splitext(file_name)
            if mod_name == '__init__':
                mod_name = ''
            ns_list = [ns for ns in [root_ns, mod_name] if ns]
            mod_ns = '.'.join(ns_list)
            imp.load_source(mod_ns, os.path.join(root, file_name))
            self.modules[mod_ns] = importlib.import_module(mod_ns)

        try:
            os.remove(init_path)
        except IOError:
            logger.warning('Failed to remove %s', init_path)

        mod_cls_map = {}

        for mod_name, cls_name in mod_cls_map.items():
            if mod_name not in self.modules:
                raise ProviderError("Module %s doesn't exists in %s" %
                                    (mod_name, path))

            mod = self.modules[mod_name]

            if (not hasattr(mod, cls_name) or
                    not inspect.isclass(getattr(mod, cls_name))):
                raise ProviderError("Module %s doesn't has class %s" %
                                    (mod_name, cls_name))

        self.Item = self.modules['%s.item' % root_ns].Item
        self.constraint_manager = constraint.ConstraintManager(self)

    def generate(self):
        """
        Generate a new constrained test item.

        :return: Constrained item.
        """
        item = self.Item(provider=self)
        self.constraint_manager.constrain(item)
        return item
