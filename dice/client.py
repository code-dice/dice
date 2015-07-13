import re
import os
import sys
import time
import json
import curses
import random
import logging
import StringIO
import requests
import argparse
import threading

from collections import Counter

from . import provider
from .utils import rnd

logger = logging.getLogger('dice')


class DiceApp(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            '--server',
            action='store',
            help='Server address',
            dest='server',
            default='127.0.0.1',
        )
        self.parser.add_argument(
            '--port',
            action='store',
            help='Server port',
            dest='port',
            default='8067',
        )
        self.parser.add_argument(
            '--username',
            action='store',
            help='Server authentication user name',
            dest='username',
        )
        self.parser.add_argument(
            '--password',
            action='store',
            help='Server authentication password',
            dest='password',
        )
        self.parser.add_argument(
            '--providers',
            action='store',
            help="List of test providers separated by ','",
            dest='providers',
            default='',
        )

        self.args, _ = self.parser.parse_known_args()

        self.providers = self._process_providers()

        self.stats = {
            "skip": Counter(),
            "failure": Counter(),
            "success": Counter(),
            "timeout": Counter(),
            "expected_neg": Counter(),
            "unexpected_neg": Counter(),
            "unexpected_pass": Counter(),
        }
        self.counters = {
            "cnt": 0,
            "skip": 0,
            "failure": 0,
            "success": 0,
            "timeout": 0,
            "expected_neg": 0,
            "unexpected_neg": 0,
            "unexpected_pass": 0,
        }
        self.exiting = False
        self.pause = False
        self.setting_watch = False
        self.show_log = False
        self.watching = ''
        self.scroll_x = 0
        self.scroll_y = 0
        self.test_thread = threading.Thread(
            target=self.run_tests,
        )
        self.send_queue = []
        self.last_item = None
        self.cur_counter = 'failure'
        self.screen = curses.initscr()
        self.stream = StringIO.StringIO()

    def _stat_result(self, item):
        """
        Categorizes and keep the count of a result of a test item depends on
        the expected failure patterns.
        """
        res = item.res
        fail_patts = item.fail_patts

        self.counters['cnt'] += 1
        if res:
            if res.exit_status == 'timeout':
                self.counters['timeout'] += 1

            if self.watching and self.watching in res.stderr:
                self.pause = True

            if fail_patts:
                if res.exit_status == 'success':
                    self.counters['unexpected_pass'] += 1
                    self.stats['unexpected_pass'][res.stderr] += 1
                elif res.exit_status == 'failure':
                    found = False
                    for patt in fail_patts:
                        if re.search(patt, res.stderr):
                            self.counters['expected_neg'] += 1
                            self.stats['expected_neg'][patt] += 1
                            found = True
                            break
                    if not found:
                        self.counters['unexpected_neg'] += 1
                        self.stats['unexpected_neg'][res.stderr] += 1
            else:
                if res.exit_status == 'success':
                    self.counters['success'] += 1
                    self.stats['success'][res.stderr] += 1
                elif res.exit_status == 'failure':
                    self.stats['failure'][res.stderr] += 1
                    self.counters['failure'] += 1
        else:
            self.counters['skip'] += 1

    def _show_report(self):
        """
        Show the most frequent pattern of a specified result type depends on
        the expected failure patterns.
        """
        maxy, maxx = self.screen.getmaxyx()
        width, height = maxx / 2, maxy

        cnt = self.counters["cnt"]

        cur_y = 1
        item_id = 0
        pad = curses.newpad(height, width)
        stat_cnt = self.counters[self.cur_counter]
        for err, c in self.stats[self.cur_counter].most_common(30):
            pad.addstr(cur_y, 1, str(c))
            pad.addstr(cur_y, 6, "%6.2f" % (float(c) * 100 / stat_cnt))

            style = curses.A_BOLD if bool(item_id % 2) else curses.A_DIM
            for line in err.splitlines():
                if len(line) > (width - 17):
                    line = line[:(width - 17)]
                pad.addstr(cur_y, 15, line, style)
                cur_y += 1
                if cur_y == height:
                    break
            if cur_y == height:
                break
            item_id += 1
        pad.box()
        title = self.cur_counter.replace('_', ' ').upper()
        pad.addstr(0, 10, ' MOST FREQUENT %s ' % title)
        if cnt:
            pad.addstr(0, 2, '%.2f%%' % (float(stat_cnt) / cnt * 100))
        pad.refresh(0, 0, 0, 0, height, width)

    def _show_log(self):
        maxy, maxx = self.screen.getmaxyx()
        width, height = maxx / 2, maxy

        cur_y = 1
        pad = curses.newpad(height, width)
        lines = self.stream.getvalue().splitlines()
        for line in lines[-(height - 2):]:
            if len(line) > (width - 2):
                line = line[:(width - 2)]
            pad.addstr(cur_y, 1, line)
            cur_y += 1
        pad.box()
        pad.refresh(0, 0, 0, 0, height, width)

    def _show_last_result(self):
        """
        Show last result of tested items
        """
        maxy, maxx = self.screen.getmaxyx()
        width, height = maxx / 2, maxy

        pad = curses.newpad(height, width)
        item = self.last_item
        if item:
            lines = ''
            lines = str(item.res)
            if item.fail_patts:
                lines += 'fail patterns:\n'
                for patt in item.fail_patts:
                    lines += '  %s\n' % patt

            if self.scroll_y < 0:
                self.scroll_y = 0
            if self.scroll_x < 0:
                self.scroll_x = 0
            lines = lines.splitlines()[self.scroll_y:]
            cur_y = 1
            for line in lines:
                line = line.replace('\t', '  ')
                if len(line) > width - 2 + self.scroll_x:
                    line = line[self.scroll_x:(width - 2 + self.scroll_x)]
                else:
                    line = line[self.scroll_x:]
                pad.addstr(cur_y, 1, line)
                cur_y += 1
                if cur_y == height:
                    break
        pad.box()
        pad.addstr(0, 10, ' LAST RESULT ')
        pad.refresh(0, 0, 0, maxx / 2, maxy, maxx)

    def _monitor_key(self):
        """
        Monitor key press
        """
        ch = self.screen.getch()
        if ch == ord('q'):
            self.exiting = True
        elif ch == ord('p'):
            self.pause = not self.pause
        elif ch == ord('n'):
            idx = self.stats.keys().index(self.cur_counter)
            new_idx = (idx + 1) % len(self.stats)
            self.cur_counter = self.stats.keys()[new_idx]
        elif ch == ord('N'):
            idx = self.stats.keys().index(self.cur_counter)
            new_idx = (idx - 1) % len(self.stats)
            self.cur_counter = self.stats.keys()[new_idx]
        elif ch == ord('w'):
            self.pause = True
            self.setting_watch = True
        elif ch == ord('l'):
            self.show_log = not self.show_log
        elif ch == ord('s'):
            self.last_item.save('saved_item.txt')
        elif ch == curses.KEY_UP:
            self.scroll_y -= 1
        elif ch == curses.KEY_DOWN:
            self.scroll_y += 1
        elif ch == curses.KEY_LEFT:
            self.scroll_x -= 1
        elif ch == curses.KEY_RIGHT:
            self.scroll_x += 1

    def _show_watch_setting(self):
        """
        Show watch setup window
        """
        maxy, maxx = self.screen.getmaxyx()
        width, height = max(len(self.watching) + 10, 20), 3

        pad = curses.newpad(height, width)
        pad.box()
        pad.addstr(0, 10, ' WATCH ')
        pad.addstr(1, 5, self.watching)
        pad.refresh(0, 0, (maxy - height) / 2, (maxx - width) / 2,
                    (maxy + height) / 2, (maxx + width) / 2)

    def _monitor_watch_input(self):
        ch = self.screen.getch()
        if ch != -1:
            if ch == ord('\n'):
                self.setting_watch = False
                self.pause = False
            elif ch == curses.KEY_BACKSPACE:
                if self.watching:
                    self.watching = self.watching[:-1]
            else:
                self.watching += chr(ch)

    def _show_exit(self):
        """
        Show existing pad in the center of screen
        """
        maxy, maxx = self.screen.getmaxyx()
        width, height = 20, 3

        pad = curses.newpad(height, width)
        pad.box()
        pad.addstr(1, 5, 'EXISTING...')
        pad.refresh(0, 0, (maxy - height) / 2, (maxx - width) / 2,
                    (maxy + height) / 2, (maxx + width) / 2)

    def _process_providers(self):
        """
        Print a list of available providers if --list-providers is set
        or return a dict of specified providers.
        """
        providers = {}
        if self.args.providers:
            for path in self.args.providers.split(','):
                prvdr = provider.Provider(path)
                providers[prvdr.name] = prvdr
        else:
            sys.exit('Error: --providers option not specified')
        return providers

    def send(self, queue):
        """
        Serialize a list of test results and send them to remote server.
        """
        content = []
        for item in queue:
            content.append(item.serialize())
        data = json.dumps(content)
        headers = {}
        headers['content-type'] = 'application/json'
        url = 'http://%s:%s/api/tests/' % (self.args.server, self.args.port)
        try:
            response = requests.post(
                url,
                data=data,
                headers=headers,
                auth=(self.args.username, self.args.password),
            )
            if response.status_code != 201:
                logger.debug('Failed to send result (HTTP%s):',
                             response.status_code)
                if 'DOCTYPE' in response.text:
                    html_path = 'debug_%s.html' % rnd.regex('[a-z]{4}')
                    with open(html_path, 'w') as fp:
                        fp.write(response.text)
                    logger.debug('Html response saved to %s',
                                 os.path.abspath(html_path))
                else:
                    logger.debug(response.text)
        except requests.ConnectionError, detail:
            logger.debug('Failed to send result to server: %s', detail)

    def run_tests(self):
        """
        Main loop to run tests
        """
        while not self.exiting:
            item = random.choice(self.providers.values()).run_once()
            self.last_item = item
            self.send_queue.append(item)
            self._stat_result(item)
            if self.pause:
                while self.pause and not self.exiting:
                    time.sleep(0.5)

    def run(self):
        """
        Main loop to update screen and send tests results.
        """
        shandler = logging.StreamHandler(self.stream)
        logger.setLevel(logging.WARNING)

        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.addHandler(shandler)

        os.environ["EDITOR"] = "echo"
        last_thread = None
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.screen.keypad(1)
        self.screen.timeout(100)
        self.screen.refresh()

        self.last_item = None
        self.test_thread.start()

        try:
            while True:
                if self.setting_watch:
                    self._show_watch_setting()
                    self._monitor_watch_input()
                else:
                    if self.show_log:
                        self._show_log()
                    else:
                        self._show_report()
                    self._show_last_result()
                    self._monitor_key()

                if len(self.send_queue) > 200:
                    if last_thread:
                        last_thread.join()
#                    send_thread = threading.Thread(
#                        target=self.send,
#                        args=(self.send_queue,)
#                    )
#                    send_thread.start()
#                    last_thread = send_thread
                    self.send_queue = []

                if self.exiting:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.exiting = True
            self._show_exit()
            self.test_thread.join()
            curses.nocbreak()
            self.screen.keypad(0)
            curses.curs_set(1)
            curses.echo()
            curses.endwin()
