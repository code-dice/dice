import os
import random
import string


class SymbolBase(object):
    """
    Base class for a symbol object represent a catalog of data to be
    randomized.
    """

    def __init__(self, scope=None, excs=None, exc_types=None):
        """
        :param scope: A list limits the scope of generated results.
        :param excs: A list won't exist in generated results.
        :param exc_types: A list of types won't exist in generated results.
        """
        self.scope = scope
        self.excs = excs
        self.exc_types = exc_types

    def generate(self):
        """
        Generate a random instance of this symbol without considering scope,
        excs or exc_types. Must be overridden.
        """
        raise NotImplementedError("Method 'generate' not implemented for %s" %
                                  self.__class__.__name__)

    def model(self):
        """
        Generate a random instance of this symbol.
        """
        if self.scope is None:
            res = self.generate()
            if self.excs is not None:
                while res in self.excs:
                    res = self.generate()
            return res
        else:
            res = random.choice(self.scope)
            if self.excs is not None:
                while res in self.excs:
                    res = random.choice(self.scope)
            return res


class Bytes(SymbolBase):
    """
    Symbol class for a string contains random bytes (1~255).
    """
    def generate(self):
        """
        Generate a random bytes string.
        """
        cnt = int(random.expovariate(0.1))
        return ''.join(bt for bt in os.urandom(cnt) if bt != b'\x00')


class NonEmptyBytes(Bytes):
    """
    Symbol class for a random byte(1-255) string except empty string.
    """
    def generate(self):
        """
        Generate a random non-empty bytes string.
        """
        cnt = int(random.expovariate(0.1)) + 1
        return ''.join(bt for bt in os.urandom(cnt) if bt != b'\x00')


class String(Bytes):
    """
    Symbol class for a random printable string.
    """
    def generate(self):
        """
        Generate a random printable string.
        """
        cnt = int(random.expovariate(0.1))
        return ''.join(random.choice(string.printable) for _ in range(cnt))


class StringList(SymbolBase):
    """
    Symbol class for a list of random printable strings.
    """
    def __init__(self, scope=None, excs=None, exc_types=None):
        """
        :param scope: A list limits the scope of generated results.
        :param excs: A list won't exist in generated results.
        :param exc_types: A list of types won't exist in generated results.
        """
        super(StringList, self).__init__()
        self.scopes = []

    def generate(self):
        """
        Generate a random printable strings.
        """
        cnt = int(random.expovariate(0.1))
        return ''.join(random.choice(string.printable) for _ in range(cnt))

    def model(self):
        """
        Generate a random-numbered list contains random printable strings.
        """
        cnt = int(random.expovariate(0.1))
        res = set()
        for _ in range(cnt):
            entry = None
            if self.scopes:
                for scope, _, _ in self.scopes:
                    if scope:
                        entry = random.choice(scope)
            else:
                entry = self.generate()
            if entry:
                res.add(entry)
        return list(res)


class Integer(SymbolBase):
    """
    Symbol class for a random integer.
    """
    def __init__(self, scope=None, excs=None, exc_types=None):
        """
        :param scope: A list limits the scope of generated results.
        :param excs: A list won't exist in generated results.
        :param exc_types: A list of types won't exist in generated results.
        """
        super(Integer, self).__init__(scope)
        self.maximum = None
        self.minimum = None

        self.exc_types = []
        if exc_types is not None:
            self.exc_types = exc_types

    def __repr__(self):
        maximum, minimum = self.maximum, self.minimum
        if self.maximum is None:
            maximum = 'Inf'
        if self.minimum is None:
            minimum = '-Inf'
        return '<%s %s~%s>' % (self.__class__.__name__, minimum, maximum)

    def generate(self):
        """
        Generate a random integer.
        """
        scale = 50.0
        maximum = self.maximum
        minimum = self.minimum
        while True:
            sign = 1.0 if random.random() > 0.5 else -1.0
            res = sign * (2.0 ** (random.expovariate(1.0 / scale)) - 1.0)
            if maximum is not None:
                if maximum >= 0 and res > maximum + 1:
                    continue
                if maximum < 0 and res > maximum:
                    continue
            if minimum is not None:
                if minimum >= 0 and res < minimum:
                    continue
                if minimum < 0 and res < minimum - 1:
                    continue
            return int(res)
