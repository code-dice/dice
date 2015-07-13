import types
import random
import string
import logging

from . import base


def cpuset(min_inc=0, max_inc=100, max_len=1000, used_vcpu=None):
    cnt = int_exp(1, max_len)

    cpus = []
    cpusets = set()
    for _ in xrange(cnt):
        choice = random.randint(0, 2)
        if choice == 0:
            # Number
            num = int_exp(min_inc, max_inc)
            cpusets.add(num)
            cpus.append(str(num))
        elif choice == 1:
            # Range
            upper = int_exp(min_inc, max_inc - 1)
            lower = int_exp(min_inc, upper)
            cpusets.update(set(xrange(lower, upper + 1)))
            cpus.append('-'.join((str(lower), str(upper))))
        elif choice == 2:
            # Negation
            num = int_exp(min_inc, max_inc)
            cpusets.discard(num)
            cpus.append('^' + str(num))

    if used_vcpu is not None:
        for cpu in (used_vcpu & cpusets):
            cpusets.discard(cpu)
            cpus.append('^' + str(cpu))

        if not cpusets:
            cpusets.update(set(xrange(min_inc, max_inc + 1)))
            cpus.append('-'.join((str(min_inc), str(max_inc))))
            for cpu in (used_vcpu & cpusets):
                cpusets.discard(cpu)
                cpus.append('^' + str(cpu))

        used_vcpu.update(cpusets)

    cpu_str = ','.join(cpus)
    return cpu_str


def count(min_inc=0, max_inc=None, lambd=0.1):
    return int_exp(min_inc=min_inc, max_inc=max_inc, lambd=lambd)


def int_exp(min_inc=0, max_inc=None, lambd=0.01):
    """
    A non accurate exponentially distributed integer generator.
    """
    shift = int(random.expovariate(lambd))
    if max_inc is not None:
        if max_inc - min_inc == 0:
            shift = 0
        else:
            shift %= max_inc - min_inc
    if min_inc is not None and min_inc >= 0:
        return min_inc + shift
    else:
        minus = random.random() > 0.5
        if min_inc is not None and minus and shift > - min_inc:
            shift %= - min_inc
        return - shift if minus else shift


def integer(min_inc=0, max_inc=10):
    return random.randint(min_inc, max_inc)


def text(escape=False, min_len=5, max_len=10, charset=None, excludes=None):
    """
    Generate a randomized string.
    """

    if not excludes:
        excludes = "\n\t\r\x0b\x0c"

    if charset:
        chars = list(charset)
    else:
        chars = []
        for char in string.printable:
            if char not in excludes:
                chars.append(char)

    length = random.randint(min_len, max_len)

    result_str = ''.join(random.choice(chars) for _ in xrange(length))

    if escape:
        return base.escape(result_str)
    else:
        return result_str

ALL_CHARS = set(string.letters) - set('&\'"<>')
# ALL_CHARS = set(string.printable)


def regex(re_str):
    """
    Generate a random string matches given regular expression.
    """
    def _end_chose(chosen, cmin, cmax):
        current_group = result_stack[-1]
        current_group.append((chosen, cmin, cmax, neg_chose))

    def _start_group():
        current_group = [[]]
        result_stack.append(current_group[0])
        result_stack[-2].append(current_group)

    def _end_sub_group():
        current_sub_group = []
        result_stack[-2][-1].append(current_sub_group)
        result_stack.pop()
        result_stack.append(current_sub_group)

    def _end_group(cmin, cmax):
        parent_group = result_stack[-2]
        result_stack.pop()
        parent_group.append((tuple(parent_group.pop()), cmin, cmax))

    def _randomize(stack):
        if len(stack) == 3:
            sub_stacks, cmin, cmax = stack
            assert isinstance(sub_stacks, types.TupleType)
            sub_stacks = random.choice(sub_stacks)
            assert isinstance(sub_stacks, types.ListType)
        elif len(stack) == 4:
            chose_str, cmin, cmax, neg = stack
            sub_stacks = None
            assert isinstance(chose_str, types.StringType)
            if neg:
                chose_str = ''.join(ALL_CHARS - set(chose_str))

        if cmax is None:
            cnt = int(random.expovariate(0.1)) + cmin
        else:
            cnt = random.randint(cmin, cmax)

        rnd_str = ""
        if sub_stacks is not None:
            for _ in xrange(cnt):
                for sub_stack in sub_stacks:
                    rnd_str += _randomize(sub_stack)
        else:
            for _ in xrange(cnt):
                rnd_str += random.choice(chose_str)
        return rnd_str

    spanning = False
    escaping = False

    chosen = []
    choosing = False
    neg_chose = False

    counting = None
    count_min = 0
    count_max = None

    root_result = []
    result_stack = [[root_result], root_result]

    _start_group()
    char_list = list(re_str)
    while char_list:
        c = char_list.pop(0)
        if choosing:
            if spanning:
                span_from = chosen[-1]
                span_to = c
                cur = ord(span_from)
                while cur < ord(span_to):
                    cur += 1
                    chosen += chr(cur)
                spanning = False
                continue

            if escaping:
                if c == 'n':
                    chosen += '\n'
                elif c == 't':
                    chosen += '\t'
                elif c == 'r':
                    chosen += '\r'
                else:
                    chosen += c
                escaping = False
                continue

            if c == ']':
                choosing = False
                if char_list and char_list[0] in '{?+*':
                    counting = 'chose'
                else:
                    _end_chose(chosen, 1, 1)
                continue

            if c == '-':
                spanning = True
                continue

            if c == '\\':
                escaping = True
                continue

            else:
                chosen += c
                continue

        if counting:
            if c == ',':
                count_max = 0
                continue

            if c == '}':
                if count_max is None:
                    count_max = count_min
                if counting == 'chose':
                    _end_chose(chosen, count_min, count_max)
                elif counting == 'group':
                    _end_group(count_min, count_max)
                else:
                    logging.error("Unknown counting type %s", counting)
                counting = None
                continue
            if c in string.digits:
                if count_max is None:
                    count_min = 10 * count_min + int(c)
                else:
                    count_max = 10 * count_max + int(c)
                continue
            if c == '{':
                count_min = 0
                count_max = None
                continue
            if c in '?+*':
                count_min = 0
                count_max = None
                if c == '+':
                    count_min = 1
                if c == '?':
                    count_max = 1
                if counting == 'chose':
                    _end_chose(chosen, count_min, count_max)
                elif counting == 'group':
                    _end_group(count_min, count_max)
                else:
                    logging.error("Unknown counting type %s", counting)
                counting = None
                continue
            logging.error("Not handled counting character: %s", c)

        if escaping:
            _end_chose(c, 1, 1)
            escaping = False
            continue

        if c == '(':
            _start_group()
            continue

        if c == ')':
            if char_list and char_list[0] in '{?+*':
                counting = 'group'
            else:
                _end_group(1, 1)
            continue

        if c == '[':
            choosing = True
            if char_list[0] == '^':
                char_list.pop(0)
                neg_chose = True
            chosen = ''
            continue

        if c == '\\':
            escaping = True
            continue

        if c == '|':
            _end_sub_group()
            continue

        chosen = c
        if char_list and char_list[0] in '{?+*':
            counting = 'chose'
        else:
            _end_chose(chosen, 1, 1)
        continue
    _end_group(1, 1)
    return _randomize(result_stack[0][0][0])
