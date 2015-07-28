import ast
import inspect
import logging
import sys

from dice import symbol


logger = logging.getLogger(__name__)


class TraceError(Exception):
    pass


class TraceSolveError(TraceError):
    pass


class Trace(object):
    def __init__(self, trace):
        self.trace = trace[:]
        ret = trace[-1]
        assert isinstance(ret, ast.Return)
        self.result = ret.value.func.id
        args = ret.value.args

        self.result_patts = None
        if args:
            self.result_patts = args[0].s

    def __repr__(self):
        lines = []
        for line in self.trace:
            if isinstance(line, ast.Compare):
                s = str(line.ops[0].__class__.__name__)
            else:
                s = line.value.func.id
            lines.append(s)
        return repr(lines)

    def _exec_call(self, node):
        func_name = node.func.attr
        pkg_name = node.func.value.id
        mod_name = '.'.join(['virsh', 'utils', pkg_name])
        mod = sys.modules[mod_name]
        func = getattr(mod, func_name)
        return func()

    def _proc_compare(self, node, symbols):
        assert len(node.ops) == 1
        assert len(node.comparators) == 1
        assert isinstance(node.left, ast.Name)

        left = node.left.id
        op = node.ops[0].__class__.__name__
        comparator = node.comparators[0]

        if isinstance(comparator, ast.Name):
            comparator = comparator.id
        elif isinstance(comparator, ast.Num):
            comparator = comparator.n
        elif isinstance(comparator, ast.Str):
            comparator = comparator.s

        call_result = None
        if isinstance(comparator, ast.Call):
            call_result = self._exec_call(comparator)

        if left not in symbols:
            # Objective for testing left symbol type
            test_obj = comparator
            if call_result is not None:
                test_obj = call_result

            if op in ['In', 'NotIn']:
                assert isinstance(test_obj, list)
                test_obj = call_result[0]

            known_symbols = []
            for name in dir(symbol):
                obj = getattr(symbol, name)
                if inspect.isclass(obj) and issubclass(obj, symbol.Symbol):
                    known_symbols.append(name)

            if isinstance(test_obj, int):
                symbols[left] = symbol.Integer()
            elif isinstance(test_obj, str):
                if test_obj in known_symbols:
                    if op != 'IsNot':
                        symbols[left] = getattr(symbol, test_obj)()
                    else:
                        symbols[left] = symbol.Bytes(exc_types=[test_obj])
                else:
                    symbols[left] = symbol.Bytes()
            else:
                raise Exception('Unexpected comparator type %s' %
                                type(test_obj))
        sleft = symbols[left]
        sleft_type = sleft.__class__.__name__

        if op == 'Is':
            if sleft_type != comparator:
                raise Exception(
                    'Unmatched type %s. Should be %s' %
                    (comparator, sleft_type))
        elif op == 'IsNot':
            if sleft_type == comparator:
                raise Exception(
                    'Unmatched type. Should not be %s' % sleft_type)
        elif op == 'Eq':
            if sleft.scope and comparator not in sleft.scope:
                raise Exception(
                    'Unsatisfiable condition. Need equal to "%s", '
                    'but scope is %s' % (comparator, sleft.scope)
                )
            sleft.scope = [comparator]
        elif op == 'NotEq':
            if sleft.excs is None:
                sleft.excs = []
            sleft.excs.append(comparator)
        elif op == 'Lt':
            if sleft_type == 'Integer':
                sleft.maximum = comparator - 1
        elif op == 'LtE':
            if sleft_type == 'Integer':
                sleft.maximum = comparator
        elif op == 'Gt':
            if sleft_type == 'Integer':
                sleft.minimum = comparator + 1
        elif op == 'GtE':
            if sleft_type == 'Integer':
                sleft.minimum = comparator
        elif op == 'In':
            sleft.scope = call_result
        elif op == 'NotIn':
            sleft.excs = call_result
        else:
            raise TraceSolveError('Unknown operator: %s' % op)

    def solve(self):
        symbols = {}

        for node in self.trace:
            if isinstance(node, ast.Compare):
                self._proc_compare(node, symbols)
            elif isinstance(node, ast.Return):
                res_self = symbols['self'].model()
                return res_self
            else:
                logger.error('Unknown node type: %s', type(node))
