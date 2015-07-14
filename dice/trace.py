import ast

from dice import symbol


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

        if left not in symbols:
            if comparator == 'Integer':
                if op != 'IsNot':
                    symbols[left] = symbol.Integer()
                else:
                    symbols[left] = symbol.Bytes(exc_types=['Integer'])
            elif isinstance(comparator, int):
                symbols[left] = symbol.Integer()
            else:
                raise Exception('Unexpected comparator %s' % comparator)
        sleft = symbols[left]
        sleft_type = sleft.__class__.__name__

        if op == 'Is':
            if sleft_type != comparator:
                raise Exception('Unmatched type %s. Should be %s' % (comparator, sleft_type))
        elif op == 'IsNot':
            if sleft_type == comparator:
                raise Exception('Unmatched type. Should not be %s' % sleft_type)
        elif op == 'Eq':
            sleft.value = comparator
        elif op == 'NotEq':
            sleft.exc.append(comparator)
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
                print 'Unknown node type:', node
