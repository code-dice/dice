import curses
import time

from . import panel


class Window(object):
    """
    Class for a whole curses window of DICE client.
    """
    def __init__(self, app):
        """
        :param app: The DICE application this window belongs to.
        """
        self.app = app
        self.screen = curses.initscr()

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, 2, 0)
        curses.init_pair(2, -1, 0)
        curses.init_pair(3, -1, 2)

        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.screen.keypad(1)
        self.screen.timeout(100)
        self.screen.refresh()
        self.height, self.width = self.screen.getmaxyx()

        self.stat_panel = panel.ListPanel(
            self.screen,
            self.height, self.width / 6,
            format_str='{count} {key}'
        )

        self.items_panel = panel.ListPanel(
            self.screen,
            self.height, self.width / 2,
            x=self.width / 6, y=0,
            format_str='{item}'
        )

        self.detail_panel = panel.TextPanel(
            self.screen,
            self.height, self.width / 3,
            x=self.width / 3 * 2, y=0,
        )

        self.input_panel = None
        self.input_result = ''

        self.panels = []
        self.panels.append(self.stat_panel)
        self.panels.append(self.items_panel)
        self.panels.append(self.detail_panel)
        self.active_panel = self.stat_panel

    def destroy(self):
        """
        Destroy the curses window.
        """
        curses.nocbreak()
        self.screen.keypad(0)
        curses.curs_set(1)
        curses.echo()
        curses.endwin()

    def draw(self):
        """
        Draw all the panels in the curses window.
        """
        for p in self.panels:
            active = False
            if p is self.active_panel:
                active = True
            p.draw(active=active)

    def _dispatch_events(self):
        """
        Monitor and dispatch events like screen resize, key press
        """
        app = self.app

        # Check key press event and dispatch on_keypress event
        ch = self.screen.getch()

        if self.active_panel.on_keypress(ch):
            return

        if ch == ord('q'):
            app.exiting = True
        elif ch == ord('p'):
            app.pause = not app.pause
        elif ch == ord('w'):
            app.pause = True
            app.setting_watch = True
        elif ch == ord('l'):
            app.show_log = not app.show_log
        elif ch == ord('s'):
            app.last_item.save('saved_item.txt')
        elif ch == ord('\t'):
            cur_idx = self.panels.index(self.active_panel)
            next_idx = (cur_idx + 1) % len(self.panels)
            self.active_panel = self.panels[next_idx]
        elif ch == curses.KEY_UP:
            app.scroll_y -= 1
        elif ch == curses.KEY_DOWN:
            app.scroll_y += 1
        elif ch == curses.KEY_LEFT:
            app.scroll_x -= 1
        elif ch == curses.KEY_RIGHT:
            app.scroll_x += 1

        # Check windows size change and dispatch on_resize event
        height, width = self.screen.getmaxyx()
        if self.height != height or self.width != width:
            for p in self.panels:
                p.resize(height, width / 6)
        self.height, self.width = height, width

    def update(self):
        """
        Get events and update the window.
        """
        self._dispatch_events()
        self.draw()

    def get_input(self):
        """
        Show and focus to an input panel and return the content.

        :return: A string of input content.
        """
        def _write_cb(text):
            # Close input panel
            self.active_panel = old_active_panel
            self.input_panel = None
            del self.panels[-1]
            self.input_result = text

        def _cancel_cb(text):
            # Close input panel
            self.active_panel = old_active_panel
            self.input_panel = None
            del self.panels[-1]

        self.input_result = ''
        self.input_panel = panel.InputPanel(
            self.screen,
            self.height / 2, self.width * 5 / 6,
            _write_cb, _cancel_cb,
            x=self.width / 12, y=self.height / 4
        )
        self.panels.append(self.input_panel)
        old_active_panel = self.active_panel
        self.active_panel = self.input_panel

        while self.input_panel is not None:
            time.sleep(0.5)

        return self.input_result
