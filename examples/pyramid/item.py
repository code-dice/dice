from dice.core import item
from dice import utils


class Item(item.ItemBase):
    def run(self):
        cmdline = './pyramid'
        cmdline += ' %s' % utils.escape(str(self.get('option')))
        self.res = utils.run(cmdline)
