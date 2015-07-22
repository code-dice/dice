import collections
import curses


class Panel(object):

    def __init__(self, screen, height, width, x=0, y=0):
        self.screen = screen
        self.height = height
        self.width = width
        self.pad = Pad(self.height, self.width)
        self.resize(self.height, self.width)
        self.x, self.y = x, y

    def resize(self, height, width):
        self.height = height
        self.width = width
        self.pad.resize(height, width)


class Catalog(object):
    def __init__(self, name):
        self.name = name
        self.fold = False
        self.active = False
        self.items = []
        self.cur_key = None

    def add_item(self, bundle):
        self.items.append(bundle)


class Pad(object):
    def __init__(self, height, width):
        self.width = width
        self.height = height
        self.pad = curses.newpad(height, width)
        self.cur_y = 1

    def box(self):
        self.pad.box()

    def reset(self):
        self.pad.clear()
        self.cur_y = 1

    def resize(self, height, width):
        self.width = width
        self.height = height
        self.pad.resize(height, width)

    def println(self, text, align='left', style=curses.A_NORMAL):
        if self.cur_y > self.height - 2:
            return

        if len(text) > (self.width - 2):
            text = text[:(self.width - 2)]

        if align == 'left':
            self.pad.addstr(self.cur_y, 1, text.ljust(self.width - 2), style)
        elif align == 'center':
            self.pad.addstr(self.cur_y, 1, text.center(self.width - 2), style)
        self.cur_y += 1

    def refresh(self, pminrow, pmincol, sminrow, smincol, smaxrow, smaxcol):
        self.pad.refresh(pminrow, pmincol, sminrow, smincol, smaxrow, smaxcol)


class TextPanel(Panel):
    def __init__(self, screen, height, width, x=0, y=0):
        super(TextPanel, self).__init__(screen, height, width, x=x, y=y)
        self.content = None
        self.cur_key = (None, None)
        self.select_cb = None

    def clear(self):
        self.content = None

    def set_content(self, bundle):
        self.content = bundle

    def draw(self, active=False):
        self.pad.reset()

        lines = str(self.content).splitlines()
        for line in lines:
            self.pad.println(line, align='left', style=curses.A_NORMAL)

        if active:
            self.pad.box()
        self.pad.refresh(0, 0,
                         self.y, self.x,
                         self.y + self.height, self.x + self.width)

    def on_keypress(self, ch):
        pass


class ListPanel(Panel):
    def __init__(self, screen, height, width, x=0, y=0, format_str=''):
        super(ListPanel, self).__init__(screen, height, width, x=x, y=y)
        self.catalogs = collections.OrderedDict()
        self.cur_key = (None, None)
        self.select_cb = None
        self.format_str = format_str

    def set_select_callback(self, cb):
        self.select_cb = cb

    def clear(self):
        self.catalogs = collections.OrderedDict()

    def format(self, item):
        return self.format_str.format(**item)

    def select(self, cat_key=None, item_key=None):
        self.cur_key = (cat_key, item_key)
        if self.select_cb is not None:
            self.select_cb(cat_key, item_key)

    def get_catalog(self, name):
        if name not in self.catalogs:
            self.catalogs[name] = Catalog(name)
        return self.catalogs[name]

    def add_item(self, bundle, catalog=''):
        cat = self.get_catalog(catalog)
        cat.add_item(bundle)

    def draw(self, active=False):
        # Select one item if available
        cur_cat, cur_item = self.cur_key
        if cur_cat is None or cur_item is None:
            cat_name = None
            item_idx = None
            if self.catalogs:
                cat_name = self.catalogs.keys()[0]
                items = self.catalogs[cat_name].items
                if items:
                    item_idx = 0
            self.select(cat_name, item_idx)

        cur_cat, cur_item = self.cur_key
        if self.catalogs:
            self.pad.reset()
            for cat_name, cat in self.catalogs.items():
                # Draw catalog title bar
                cat_selected = False
                if cat_name == cur_cat:
                    cat_selected = True
                    cat_style = curses.color_pair(1)
                else:
                    cat_style = curses.color_pair(2)

                if cat_name != '':
                    self.pad.println(cat.name.upper(),
                                     align='center', style=cat_style)

                # Draw items
                if not cat.fold:
                    for item_idx, item in enumerate(cat.items):
                        if item_idx == cur_item and cat_selected:
                            item_style = curses.color_pair(3)
                        else:
                            item_style = curses.A_NORMAL
                        self.pad.println(self.format(item), style=item_style)
        if active:
            self.pad.box()
        self.pad.refresh(0, 0,
                         self.y, self.x,
                         self.y + self.height, self.x + self.width)

    def on_keypress(self, ch):
        if ch == ord('j'):
            cat_name, item_idx = self.cur_key

            cats = self.catalogs.keys()

            cat = self.catalogs[cat_name]
            if item_idx < len(cat.items) - 1:
                item_idx += 1
            else:
                cat_idx = list(cats).index(cat_name)
                cat_name = cats[(cat_idx + 1) % len(cats)]
                item_idx = 0
            self.select(cat_name, item_idx)
        elif ch == ord('k'):
            cat_name, item_idx = self.cur_key

            cats = self.catalogs.keys()

            cat = self.catalogs[cat_name]
            if item_idx > 0:
                item_idx -= 1
            else:
                cat_idx = list(cats).index(cat_name)
                cat_name = cats[(cat_idx - 1) % len(cats)]
                item_idx = 0
            self.select(cat_name, item_idx)
