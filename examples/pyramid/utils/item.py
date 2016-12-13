import os

from dice.core import item
from dice import utils


class Item(item.ItemBase):
    def run(self):
        cmdline = os.path.join(self.provider.path, 'pyramid')
        cmdline += ' %s' % utils.escape(str(self.get('option')))
        self.res = utils.run(cmdline)
