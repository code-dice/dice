class Tree(object):
    pass


class ItemBase(object):
    def __init__(self):
        self.res = ''
        self.tree = Tree
        self.fail_patts = set()

    def constrain(self, constraints):
        for cstr in constraints:
            cstr.apply(self)

    def run(self):
        pass

    def set(self, target, value):
        setattr(self, target, value)

    def get(self, target):
        return getattr(self, target)

    def serialize(self):
        return ''
