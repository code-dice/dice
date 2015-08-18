import fnmatch
import imp
import importlib
import inspect
import logging
import os

from . import constraint

logger = logging.getLogger('dice')


class ProviderError(Exception):
    pass


class Provider(object):
    def __init__(self, path):
        if not os.path.isdir(path):
            raise ProviderError("%s is not a directory." % path)

        if 'item.py' not in os.listdir(path):
            raise ProviderError("'item.py' not found in '%s'. You should "
                                "specify a valid provider path." % path)

        self.name = os.path.basename(os.path.normpath(path))
        self.path = path

        self.modules = {}

        mod_dirs = ['']
        if os.path.isdir(os.path.join(path, 'utils')):
            mod_dirs.append('utils')

        for subdir in mod_dirs:
            root = os.path.join(path, subdir)
            files = [f for f in os.listdir(root)
                     if os.path.isfile(os.path.join(root, f))]

            relative_path = os.path.relpath(root, path)
            folders = os.path.split(relative_path)
            root_ns = '.'.join(
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
                ns_list = [ns for ns in [self.name, root_ns, mod_name] if ns]
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

        self.Item = self.modules['%s.item' % self.name].Item
        self.constraint_manager = constraint.ConstraintManager(
            os.path.join(path, 'die'))

    def run_once(self):
        item = self.Item()
        self.constraint_manager.constrain(item)
        item.run()
        return item
