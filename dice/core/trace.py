import ast
import builtins
import inspect
import logging
import sys

from . import symbol


logger = logging.getLogger(__name__)


class TraceError(Exception):
    """
    Class for trace specific exceptions.
    """
    pass


class Trace(object):
    """
    Class represent a condition trace in constraint oracle code. It contains a
    list of commands, including comparisons, operations and ends with a return
    command.
    """
    def __init__(self, provider, trace_list):
        """
        :param trace_list: A list contains code of the trace.
        """
        self.item = None
        self.provider = provider
        self.symbols = {}
        self.trace = trace_list[:]
        ret = trace_list[-1]
        assert isinstance(ret, ast.Return)
        self.result = ret.value.func.id.lower()
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
        mod_name = '.'.join([self.provider.name, 'utils', pkg_name])
        mod = sys.modules[mod_name]
        func = getattr(mod, func_name)
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                name = arg.id
                args.append(self.item.get(name))
            else:
                raise TraceError('Unknown argument type: %s' % arg)
        return func(*args)

    def _proc_compare(self, node):
        assert len(node.ops) == 1
        assert len(node.comparators) == 1
        assert isinstance(node.left, ast.Name)

        left = node.left.id
        op = node.ops[0].__class__.__name__
        comparator = node.comparators[0]

        known_symbols = []
        for name in dir(symbol):
            obj = getattr(symbol, name)
            if inspect.isclass(obj) and issubclass(obj, symbol.SymbolBase):
                known_symbols.append(name)

        exc_types = []
        right_value = None
        if isinstance(comparator, ast.Name):
            if comparator.id not in known_symbols:
                raise TraceError("Unknown symbol '%s'" % comparator.id)
            if op == 'IsNot':
                sym_type = 'Bytes'
                exc_types.append(comparator.id)
            else:
                sym_type = comparator.id
        elif isinstance(comparator, ast.Num):
            sym_type = 'Integer'
            right_value = comparator.n
        elif isinstance(comparator, ast.Str):
            sym_type = 'Bytes'
            right_value = comparator.s

        if isinstance(comparator, ast.Call):
            call_ret = self._exec_call(comparator)

            test_val = call_ret
            if isinstance(call_ret, (list, tuple)):
                test_val = call_ret[0]

            if isinstance(test_val, builtins.str):
                sym_type = 'Bytes'
            elif isinstance(test_val, int):
                sym_type = 'Integer'

        if left not in self.symbols:
            self.symbols[left] = getattr(
                symbol, sym_type)(exc_types=[exc_types])

        sleft = self.symbols[left]
        sleft_type = sleft.__class__.__name__

        if op != 'IsNot':
            if not issubclass(sleft.__class__, getattr(symbol, sym_type)):
                raise TraceError(
                    'Unmatched type %s(operator: %s). Should be %s' %
                    (sym_type, op, sleft_type))

        if op == 'Is':
            pass
        elif op == 'IsNot':
            pass
        elif op == 'Eq':
            if sleft.scope and right_value not in sleft.scope:
                raise Exception(
                    'Unsatisfiable condition. Need equal to "%s", '
                    'but scope is %s' % (right_value, sleft.scope)
                )
            sleft.scope = [right_value]
        elif op == 'NotEq':
            if sleft.excs is None:
                sleft.excs = []
            sleft.excs.append(right_value)
        elif op == 'Lt':
            if sleft_type == 'Integer':
                sleft.maximum = right_value - 1
        elif op == 'LtE':
            if sleft_type == 'Integer':
                sleft.maximum = right_value
        elif op == 'Gt':
            if sleft_type == 'Integer':
                sleft.minimum = right_value + 1
        elif op == 'GtE':
            if sleft_type == 'Integer':
                sleft.minimum = right_value
        elif op == 'In':
            sleft.scope = call_ret
        elif op == 'NotIn':
            sleft.excs = call_ret
        else:
            raise TraceError('Unknown operator: %s' % op)

    def _proc_call(self, node):
        func_name = node.func.id
        assert func_name in ['any', 'all']
        assert isinstance(node.args[0], ast.Compare)
        comp = node.args[0]
        op = comp.ops[0].__class__.__name__
        left = comp.left
        right = comp.comparators[0]
        if isinstance(left, ast.Name):
            sym_left = self.symbols[left.id]
            assert isinstance(right, ast.Call)
            right = self._exec_call(right)
            assert isinstance(right, (list, tuple))
            assert op in ['In', 'NotIn']
            if func_name == 'all':
                if op == 'In':
                    sym_left.scopes.append((right, True, 0))
                elif op == 'NotIn':
                    sym_left.scopes.append((right, False, 1))
            elif func_name == 'any':
                if op == 'In':
                    sym_left.scopes.append((right, True, 1))
                    sym_left.scopes.append((right, False, 0))
                elif op == 'NotIn':
                    sym_left.scopes.append((right, True, 0))
                    sym_left.scopes.append((right, False, 1))
        elif isinstance(left, ast.Call):
            sym_right = self.symbols[right.id]
            left = self._exec_call(left)
            if func_name == 'all':
                if op == 'In':
                    raise Exception('TODO')
                elif op == 'NotIn':
                    sym_right.excludes = left
            elif func_name == 'any':
                if op == 'In':
                    pass  # TODO
        else:
            raise TraceError('Unknown left type %s' % left)

    def solve(self, item):
        """
        Generate a satisfiable random option according to this trace.
        :param item: Item to which generated option applies.
        :return: Generated random option.
        """
        self.item = item
        self.symbols = {}

        for node in self.trace:
            if isinstance(node, ast.Compare):
                self._proc_compare(node)
            elif isinstance(node, ast.Call):
                self._proc_call(node)
            elif isinstance(node, ast.Return):
                res_self = self.symbols['self'].model()
                return res_self
            else:
                raise TraceError('Unknown node type: %s' % type(node))
