class Tree(object):
    pass


class ItemBase(object):
    def __init__(self):
        self.res = ''
        self.tree = Tree
        self.fail_patts = set()

    def run(self):
        pass

    def set(self, target, value):
        setattr(self, target, value)

    def get(self, target):
        return getattr(self, target, None)

    def serialize(self):
        return ''
