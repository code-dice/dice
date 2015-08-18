import collections
import curses
import threading


class _Catalog(object):
    def __init__(self, name):
        self.name = name
        self.fold = False
        self.active = False
        self.items = []
        self.cur_key = None

    def add_item(self, bundle):
        self.items.append(bundle)


class _Pad(object):
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


class _PanelBase(object):

    def __init__(self, screen, height, width, x=0, y=0):
        self.screen = screen
        self.height = height
        self.width = width
        self.pad = _Pad(self.height, self.width)
        self.resize(self.height, self.width)
        self.x, self.y = x, y
        self.keypress_listeners = {}

    def resize(self, height, width):
        self.height = height
        self.width = width
        self.pad.resize(height, width)

    def add_keypress_listener(self, name, key, callback):
        if name not in self.keypress_listeners:
            self.keypress_listeners[name] = {'key': key, 'callback': callback}


class TextPanel(_PanelBase):
    """
    Curses panel contains only block of text.
    """
    def __init__(self, screen, height, width, x=0, y=0):
        """
        :param screen: Curses screen to draw this panel on.
        :param height: Height of the panel.
        :param width: Width of the panel.
        :param x: X position of the panel.
        :param y: Y position of the panel.
        """
        super(TextPanel, self).__init__(screen, height, width, x=x, y=y)
        self.content = None
        self.cur_key = (None, None)
        self.select_cb = None

    def clear(self):
        """
        Clear panel content.
        """
        self.content = None

    def set_content(self, bundle):
        """
        Set panel content.

        :param bundle: Content to be set.
        """
        self.content = bundle

    def draw(self, active=False):
        """
        Draw the text panel.

        :param active: If set to true, draw the panel with surrounding box.
        """
        self.pad.reset()

        lines = str(self.content).splitlines()
        for line in lines:
            self.pad.println(line, align='left', style=curses.A_NORMAL)

        if active:
            self.pad.box()
        self.pad.refresh(0, 0,
                         self.y, self.x,
                         self.y + self.height, self.x + self.width)

    def on_keypress(self, key):
        """
        Event handler when keypress event received by the panel.

        :param key: Key being pressed.
        """
        pass


class ListPanel(_PanelBase):
    """
    Curses panel contains list of entries.
    """
    def __init__(self, screen, height, width, x=0, y=0, format_str=''):
        """
        :param screen: Curses screen to draw this panel on.
        :param height: Height of the panel.
        :param width: Width of the panel.
        :param x: X position of the panel.
        :param y: Y position of the panel.
        :param format_str: The template to format a list entry.
        """
        super(ListPanel, self).__init__(screen, height, width, x=x, y=y)
        self.catalogs = collections.OrderedDict()
        self.cur_key = (None, None)
        self.select_cb = None
        self.format_str = format_str

    def set_select_callback(self, callback):
        """
        Set callback function triggered when an list item is selected.

        :param callback: Select callback function.
        """
        self.select_cb = callback

    def clear(self):
        """
        Clear panel content.
        """
        self.catalogs = collections.OrderedDict()

    def select(self, cat_key=None, item_key=None):
        """
        Select specified item.

        :param cat_key: Catalog name of the item for selection.
        :param item_key: Item name of the item for selection.
        """
        self.cur_key = (cat_key, item_key)
        if self.select_cb is not None:
            self.select_cb(cat_key, item_key)

    def add_item(self, bundle, catalog=''):
        """
        Add an item the list panel.

        :param bundle: Content of added item.
        :param catalog: Catalog of added item.
        """
        if catalog not in self.catalogs:
            self.catalogs[catalog] = _Catalog(catalog)
        cat = self.catalogs[catalog]
        cat.add_item(bundle)

    def draw(self, active=False):
        """
        Draw the list panel.

        :param active: If set to true, draw the panel with surrounding box.
        """
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
                        self.pad.println(self.format_str.format(**item),
                                         style=item_style)
        if active:
            self.pad.box()
        self.pad.refresh(0, 0,
                         self.y, self.x,
                         self.y + self.height, self.x + self.width)

    def on_keypress(self, key):
        """
        Event handler when keypress event received by the panel.

        :param key: Key being pressed.
        """
        if key == ord('j'):
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
        elif key == ord('k'):
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

        for listener in self.keypress_listeners.values():
            if key == ord(listener['key']):
                callback_thread = threading.Thread(
                    target=listener['callback'],
                    args=(self,)
                )
                callback_thread.start()


class InputPanel(_PanelBase):
    """
    Curses panel allows get input from keyboard.
    """
    def __init__(self, screen, height, width, write_callback, cancel_callback,
                 x=0, y=0):
        """
        :param screen: Curses screen to draw this panel on.
        :param height: Height of the panel.
        :param width: Width of the panel.
        :param write_callback: Callback function triggered when user writes.
        :param cancel_callback: Callback function triggered when user cancels.
        :param x: X position of the panel.
        :param y: Y position of the panel.
        """
        super(InputPanel, self).__init__(screen, height, width, x=x, y=y)
        self.content = ''
        self.cur_key = (None, None)
        self.write_cb = write_callback
        self.cancel_cb = cancel_callback

    def draw(self, active=False):
        """
        Draw the list panel.

        :param active: If set to true, draw the panel with surrounding box.
        """
        self.pad.reset()

        lines = str(self.content).splitlines()
        for line in lines:
            self.pad.println(line, align='left', style=curses.A_NORMAL)

        if active:
            self.pad.box()
        self.pad.refresh(0, 0,
                         self.y, self.x,
                         self.y + self.height, self.x + self.width)

    def on_keypress(self, key):
        """
        Event handler when keypress event received by the panel.

        :param key: Key being pressed.
        """
        if key < 0:
            return False

        # Press Ctrl-W to trigger write event
        if key == 23:
            if self.write_cb:
                self.write_cb(self.content)
        # Press Ctrl-D to trigger cancel event
        elif key == 4:
            if self.cancel_cb:
                self.cancel_cb(self.content)
        elif key == curses.KEY_BACKSPACE:
            self.content = self.content[:-1]
        else:
            self.content += chr(key)
        return True
