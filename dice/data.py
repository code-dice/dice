import inspect
import logging
import os
import random
import re
import types

from .utils import rnd


logger = logging.getLogger(__name__)


class DataError(Exception):
    pass


class CanNotGenerateError(DataError):
    pass


class Data(object):
    mixin = None
    static_list = None
    dynamic_list = None
    regex = None
    bound = None
    min_inc = None
    max_inc = None

    _params = None

    def __new__(cls, *args, **kwargs):
        new_instance = object.__new__(cls, *args, **kwargs)
        if 'generate' not in cls.__dict__:
            new_instance.generate = types.MethodType(Data.generate, new_instance)
        if 'validate' not in cls.__dict__:
            new_instance.validate = types.MethodType(Data.validate, new_instance)
        return new_instance

    @classmethod
    def _frommixin(cls, data_a, data_b, operation):
        new_class = cls()
        new_class.mixin = (data_a, data_b, operation)
        return new_class

    def __sub__(self, other):
        return Data._frommixin(self, other, 'sub')

    def __add__(self, other):
        return Data._frommixin(self, other, 'add')

    def __invert__(self):
        assert len(self.__class__.__bases__) == 1
        parent = self.__class__.__bases__[0]
        return Data._frommixin(parent(), self, 'sub')

    def set_params(self, params):
        self._params = params

    def get_params(self):
        return self._params

    def generate(self):
        MAX_RETRY = 20
        known_attrs = ['static_list', 'dynamic_list', 'regex', 'bound']
        if self.static_list is not None:
            return random.choice(self.static_list)
        elif self.dynamic_list is not None:
            gen_func = getattr(self, 'dynamic_list')
            try:
                return random.choice(gen_func())
            except IndexError:
                raise CanNotGenerateError("No value to generate for '%s'" %
                                          self.__class__.__name__)
        elif self.regex is not None:
            return rnd.regex(self.regex)
        elif self.bound is not None:
            # pylint: disable=W0633
            min_inc, max_inc = self.bound
            res = rnd.int_exp(min_inc=min_inc, max_inc=max_inc, lambd=0.01)
            return str(res)
        elif self.mixin:
            data_a, data_b, operator = self.mixin
            if operator == 'sub':
                res = data_a.generate()
                cnt = 0
                while data_b.validate(res):
                    cnt += 1
                    res = data_a.generate()
                    if cnt > MAX_RETRY:
                        raise CanNotGenerateError(
                            "Retry %s times, abort generation" % MAX_RETRY)
            else:
                raise Exception("Unknown operator '%s'" % operator)
            return res
        else:
            raise Exception("Data type '%s' has not set any attribute in %s" %
                            (self.__class__.__name__, known_attrs))

    def validate(self, obj):
        known_attrs = ['static_list', 'dynamic_list', 'regex', 'bound']
        if self.static_list is not None:
            return obj in self.static_list
        elif self.dynamic_list is not None:
            gen_func = getattr(self, 'dynamic_list')
            return obj in gen_func()
        elif self.regex is not None:
            return re.match(self.regex, obj)
        elif self.bound is not None:
            # pylint: disable=W0633
            min_inc, max_inc = self.bound
            max_in_bound = min_in_bound = True
            try:
                num = int(obj)
            except ValueError:
                return False
            if max_inc is not None:
                max_in_bound = num <= max_inc
            if min_inc is not None:
                min_in_bound = num >= min_inc
            return max_in_bound and min_in_bound
        elif self.mixin:
            data_a, data_b, operator = self.mixin
            if operator == 'sub':
                return data_a.validate(obj) and not data_b.validate(obj)
            else:
                raise Exception("Unknown operator '%s'" % operator)
        else:
            raise Exception("Data type '%s' has not set any attribute in %s" %
                            (self.__class__.__name__, known_attrs))


class String(Data):
    def validate(self, obj):
        return isinstance(obj, types.StringType)

    def generate(self):
        return rnd.text()


class Option(String):
    regex = r'-.*'


class ShortOption(Option):
    regex = r'-[^\-].*'


class LongOption(Option):
    regex = r'--.+'


class Path(String):
    def validate(self, obj):
        return os.path.exists(obj)

    def generate(self):
        return '/tmp'


class ExistPath(Path):
    def validate(self, obj):
        return os.path.exists(obj)

    def generate(self):
        file_name = 'virt-trinity-exist-path'
        path = os.path.join('/tmp', file_name)
        open(path, 'a').close()
        return path


class RegularFile(ExistPath):
    def validate(self, obj):
        return os.path.isfile(obj)

    def generate(self):
        file_name = 'virt-trinity-regular-file'
        path = os.path.join('/tmp', file_name)
        if os.path.exists(path):
            os.remove(path)
        open(path, 'a').close()
        return path


class Integer(String):
    bound = (None, None)


class UnsignedInt(Integer):
    bound = (0, None)


class PositiveInt(Integer):
    bound = (1, None)


class Pair(Data):
    def validate(self, obj):
        if not isinstance(obj, types.TupleType):
            return False
        if len(obj) != 2:
            return False
        return all([isinstance(elem, types.StringType)
                    for elem in obj])

    def generate(self):
        return (rnd.text(), rnd.text())


###################
# HELPER FUNCTIONS:
###################

def get_datas():
    return [cls
            for cls in globals().values()
            if inspect.isclass(cls) and
            issubclass(cls, Data) and
            cls is not Data]
