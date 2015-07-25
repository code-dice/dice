from __future__ import print_function
import argparse
import collections
import io
import json
import logging
import os
import queue
import random
import re
import requests
import sys
import traceback
import threading
import time

from collections import Counter

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
        self.queues = {
            "skip": {},
            "failure": {},
            "success": {},
            "timeout": {},
            "expected_neg": {},
            "unexpected_neg": {},
            "unexpected_pass": {},
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
        self.last_item = None
        self.cur_counter = 'failure'

        self.window = window.Window(self)
        self.window.stat_panel.set_select_callback(self._update_items)
        self.window.items_panel.set_select_callback(self._update_content)
        self.stream = io.StringIO()
        self.cur_class = (None, None)
        self.cur_item = (None, None)

    def _update_items(self, cat_name, item_idx):
        self.cur_class = (cat_name, item_idx)

    def _update_content(self, cat_name, item_idx):
        self.cur_item = (cat_name, item_idx)

    def _stat_result(self, item):
        """
        Categorizes and keep the count of a result of a test item depends on
        the expected failure patterns.
        """
        res = item.res
        fail_patts = item.fail_patts

        self.counters['cnt'] += 1
        key = res.stderr
        catalog = None
        if res:
            if res.exit_status == 'timeout':
                catalog = 'timeout'
                self.counters['timeout'] += 1

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
            self.counters['skip'] += 1

        self.counters[catalog] += 1
        self.stats[catalog][key] += 1
        if key not in self.queues[catalog]:
            self.queues[catalog][key] = collections.deque([], self.QUEUE_MAX)
        self.queues[catalog][key].append(res)

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
            self.send_queue.append(item)
            self._stat_result(item)
            if self.pause:
                while self.pause and not self.exiting:
                    time.sleep(0.5)

    def update_window(self):
        # Set statistics panel content
        panel = self.window.stat_panel
        panel.clear()
        for cat_name in self.stats:
            for key, cnt in self.stats[cat_name].most_common(10):
                bundle = {'key': key, 'count': cnt}
                panel.add_item(bundle, catalog=cat_name)

        # Set items panel content
        panel = self.window.items_panel
        panel.clear()
        cat_name, item_idx = self.cur_class
        if cat_name is not None and item_idx is not None:
            item_name, cnt = self.stats[cat_name].most_common(10)[item_idx]
            try:
                for item in self.queues[cat_name][item_name]:
                    bundle = {'item': item.cmdline}
                    panel.add_item(bundle)
            except RuntimeError:
                pass

        # Set detail panel content
        panel = self.window.detail_panel
        panel.clear()
        cat_name, item_idx = self.cur_class
        if cat_name is not None and item_idx is not None:
            item_name, cnt = self.stats[cat_name].most_common(10)[item_idx]
            items = self.queues[cat_name][item_name]

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
        last_thread = None

        self.last_item = None
        self.test_thread.start()

        try:
            while True:
                self.update_window()

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

                if not self.test_thread.isAlive():
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.exiting = True
            self.window.destroy()
            self.test_thread.join()
            try:
                exc = self.test_excs.get(block=False)
                for line in traceback.format_exception(*exc):
                    print(line, end='')
            except queue.Empty:
                pass
