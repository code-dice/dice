from dice import item
from dice.utils import base

class Item(item.ItemBase):
    def run(self):
        cmdline = 'examples/pyramid/pyramid'
        cmdline += ' %s' % self.get('option')
        self.res = base.run(cmdline)
