from __future__ import print_function
import argparse
import collections
import io
import json
import logging
import os
# pylint: disable=import-error
import queue
import random
import re
import requests
import sys
import traceback
import threading
import time

from . import provider
from . import window
from .utils import rnd

logger = logging.getLogger('dice')


class TestThread(threading.Thread):
    def __init__(self, exc_queue, app, **kwargs):
        threading.Thread.__init__(self, **kwargs)
        self.exc_queue = exc_queue
        self.app = app

    def run(self):
        try:
            self.app.run_tests()
        # pylint: disable=broad-except
        except Exception:
            self.exc_queue.put(sys.exc_info())


class TestStat(object):

    def __init__(self, key, queue_max=100, method='exact'):
        self.key = key
        self.counter = 0
        self.queue_max = queue_max
        self.method = method
        self.queue = collections.deque([], queue_max)

    def match(self, text):
        if self.method == 'exact':
            return text == self.key
        elif self.method == 'regex':
            return re.match(self.key + '$', text)

    def append(self, result):
        self.counter += 1
        self.queue.append(result)

    def extend(self, stat):
        for result in stat.queue:
            self.append(result)


class DiceApp(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            'providers',
            nargs='?',
            action='store',
            help="list of test providers separated by ','. Default to current "
            "working directory",
            default=os.getcwd(),
        )
        self.parser.add_argument(
            '--server',
            action='store',
            help='server address',
            dest='server',
            default=None,
        )
        self.parser.add_argument(
            '--port',
            action='store',
            help='server port',
            dest='port',
            default='8067',
        )
        self.parser.add_argument(
            '--username',
            action='store',
            help='server authentication user name',
            dest='username',
        )
        self.parser.add_argument(
            '--password',
            action='store',
            help='server authentication password',
            dest='password',
        )
        self.parser.add_argument(
            '--no-ui',
            action='store_false',
            help="don't show terminal interactive user interface.",
            dest='ui',
            default=True,
        )

        self.args, _ = self.parser.parse_known_args()

        self.providers = self._process_providers()

        self.stats = {
            "skip": {},
            "failure": {},
            "success": {},
            "timeout": {},
            "expected_neg": {},
            "unexpected_neg": {},
            "unexpected_pass": {},
        }
        self.QUEUE_MAX = 100
        self.exiting = False
        self.pause = False
        self.setting_watch = False
        self.show_log = False
        self.watching = ''
        self.scroll_x = 0
        self.scroll_y = 0
        self.test_excs = queue.Queue()
        self.test_thread = TestThread(self.test_excs, self)
        self.send_queue = []
        self.last_send_thread = None
        self.last_item = None
        self.cur_counter = 'failure'

        if self.args.ui:
            self.window = window.Window(self)
            self.window.stat_panel.set_select_callback(self._update_items)
            self.window.stat_panel.add_keypress_listener(
                'merge_stat', 'm', self._merge_stat)
            self.window.items_panel.set_select_callback(self._update_content)

        self.stream = io.StringIO()
        self.cur_class = (None, None)
        self.cur_item = (None, None)

    def _update_items(self, cat_name, item_idx):
        self.cur_class = (cat_name, item_idx)

    def _update_content(self, cat_name, item_idx):
        self.cur_item = (cat_name, item_idx)

    def _merge_stat(self, panel):
        self.pause = True
        cat_name, _ = panel.cur_key
        text = self.window.get_input()
        match_keys = []
        for key in self.stats[cat_name]:
            res = re.match(text, key)
            if res is not None:
                match_keys.append(key)

        stat = self.stats[cat_name][text] = TestStat(text, method='regex')

        for key in match_keys:
            stat.extend(self.stats[cat_name][key])
            del self.stats[cat_name][key]

        self.pause = False

    def _stat_result(self, item):
        """
        Categorizes and keep the count of a result of a test item depends on
        the expected failure patterns.
        """
        res = item.res
        fail_patts = item.fail_patts

        key = res.stderr
        catalog = None
        if res:
            if res.exit_status == 'timeout':
                catalog = 'timeout'

            if self.watching and self.watching in res.stderr:
                self.pause = True

            if fail_patts:
                if res.exit_status == 'success':
                    catalog = 'unexpected_pass'
                elif res.exit_status == 'failure':
                    found = False
                    for patt in fail_patts:
                        if re.search(patt, res.stderr):
                            catalog = 'expected_neg'
                            key = patt
                            found = True
                            break
                    if not found:
                        catalog = 'unexpected_neg'
            else:
                if res.exit_status == 'success':
                    catalog = 'success'
                elif res.exit_status == 'failure':
                    catalog = 'failure'
        else:
            catalog = 'skip'

        found = False
        for stat in self.stats[catalog].values():
            if stat.match(key):
                found = True
                key = stat.key
                break

        if not found:
            self.stats[catalog][key] = TestStat(key)

        stat = self.stats[catalog][key]
        stat.append(res)

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

    def send(self, item_queue):
        """
        Serialize a list of test results and send them to remote server.
        """
        content = []
        for item in item_queue:
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
        except requests.ConnectionError as detail:
            logger.debug('Failed to send result to server: %s', detail)

    def run_tests(self):
        """
        Main loop to run tests
        """
        while not self.exiting:
            item = random.choice(self.providers.values()).run_once()
            self.last_item = item

            if self.args.server is not None:
                self.send_queue.append(item)
                if len(self.send_queue) > 200:
                    if self.last_send_thread:
                        self.last_send_thread.join()
                    send_thread = threading.Thread(
                        target=self.send,
                        args=(self.send_queue,)
                    )
                    send_thread.start()
                    self.last_send_thread = send_thread
                    self.send_queue = []

            self._stat_result(item)
            if self.pause:
                while self.pause and not self.exiting:
                    time.sleep(0.5)

    def update_window(self):
        # Set statistics panel content
        panel = self.window.stat_panel
        panel.clear()
        for cat_name in self.stats:
            for key, stat in self.stats[cat_name].items():
                bundle = {'key': key, 'count': stat.counter}
                panel.add_item(bundle, catalog=cat_name)

        # Set items panel content
        panel = self.window.items_panel
        panel.clear()
        cat_name, item_idx = self.cur_class
        if cat_name is not None and item_idx is not None:
            item_name, stat = self.stats[cat_name].items()[item_idx]
            try:
                for item in self.stats[cat_name][item_name].queue:
                    bundle = {'item': item.cmdline}
                    panel.add_item(bundle)
            except RuntimeError:
                pass

        # Set detail panel content
        panel = self.window.detail_panel
        panel.clear()
        cat_name, item_idx = self.cur_class
        if cat_name is not None and item_idx is not None:
            item_name, stat = self.stats[cat_name].items()[item_idx]
            items = self.stats[cat_name][item_name].queue

            item_name, item_idx = self.cur_item
            if item_name is not None and item_idx is not None:
                bundle = items[self.cur_item[1]]
                panel.set_content(bundle)

        self.window.update()

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

        self.last_item = None
        if self.args.ui:
            try:
                self.test_thread.start()
                while True:
                    if self.args.ui:
                        self.update_window()

                    if self.exiting:
                        break

                    if not self.test_thread.isAlive():
                        break
            except KeyboardInterrupt:
                pass
            finally:
                if self.args.ui:
                    self.window.destroy()
                self.exiting = True
                self.test_thread.join()
                try:
                    exc = self.test_excs.get(block=False)
                    for line in traceback.format_exception(*exc):
                        print(line, end='')
                except queue.Empty:
                    pass
        else:
            self.run_tests()
