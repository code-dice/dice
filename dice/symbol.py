import os
import random
import string


class Symbol(object):
    pass


class Bytes(Symbol):
    def __init__(self, exc_types=None):
        pass

    def model(self):
        cnt = int(random.expovariate(0.1))
        return ''.join(bt for bt in os.urandom(cnt) if bt != b'\x00')


class String(Symbol):
    def __init__(self, exc_types=None):
        pass

    def model(self):
        cnt = int(random.expovariate(0.1))
        return ''.join(random.choice(string.printable) for _ in xrange(cnt))


class Integer(Symbol):
    def __init__(self, exc_types=None):
        self.value = None
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

    def model(self):
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
