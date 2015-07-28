import ast
import copy
import os
import random
import yaml

from . import trace


class ConstraintError(Exception):
    pass


class Constraint(object):

    def __init__(self, name,
                 depends_on=None, assume=None, target=None, tree=None):
        self.name = name
        self.depends_on = depends_on
        self.assume = assume
        self.target = target
        self.tree = tree
        self.fail_ratio = 0.1
        self.traces = self._tree2traces(tree)

    def _tree2traces(self, tree):
        def _revert_compare(node):
            """
            Helper function to revert a compare node to its negation.
            """
            rev_node = copy.deepcopy(node)
            op = rev_node.ops[0]

            if isinstance(op, ast.Is):
                rev_node.ops = [ast.IsNot()]
            elif isinstance(op, ast.Gt):
                rev_node.ops = [ast.LtE()]
            elif isinstance(op, ast.Lt):
                rev_node.ops = [ast.GtE()]
            elif isinstance(op, ast.Eq):
                rev_node.ops = [ast.NotEq()]
            elif isinstance(op, ast.In):
                rev_node.ops = [ast.NotIn()]
            else:
                raise ConstraintError('Unknown operator: %s' % op)
            return rev_node

        def _revert_test(node):
            """
            Helper function to revert a test node to its negation.
            """
            rev_node = copy.deepcopy(node)
            # Allow syntax like 'any(a is b)' or 'all(c in d)'
            if isinstance(rev_node, ast.Call):
                func_name = rev_node.func.id
                assert len(rev_node.args) == 1
                assert isinstance(rev_node.args[0], ast.Compare)

                rev_node.args[0] = _revert_compare(rev_node.args[0])
                if func_name == 'any':
                    rev_node.func.id = 'all'
                elif func_name == 'all':
                    rev_node.func.id = 'any'
            elif isinstance(rev_node, ast.Compare):
                rev_node = _revert_compare(node)
            else:
                raise ConstraintError('Unknown test node: %s' % node)
            return rev_node

        def _parse_if(node):
            cur_trace.append(node.test)
            _parse_block(node.body)
            cur_trace.pop()

            rev_node = _revert_test(node.test)

            cur_trace.append(rev_node)
            _parse_block(node.orelse)
            cur_trace.pop()

        def _parse_block(nodes):
            for node in nodes:
                if isinstance(node, ast.If):
                    _parse_if(node)
                elif isinstance(node, ast.Return):
                    cur_trace.append(node)
                    traces.append(trace.Trace(cur_trace))
                    cur_trace.pop()
                else:
                    raise ConstraintError('Unknown node: %s' % v)

        root = ast.parse(tree)
        stack = []
        stack.append((root))
        observed = []
        traces = []
        cur_trace = []
        while stack:
            v = stack.pop()
            if v not in observed:
                if isinstance(v, ast.If):
                    _parse_if(v)
                elif isinstance(v, ast.Module):
                    _parse_block(v.body)
                else:
                    raise ConstraintError('Unknown node: %s' % v)
        return traces

    def _choose(self, fail_ratio=None):
        fails = []
        passes = []

        for t in self.traces:
            if t.result == 'PASS':
                passes.append(t)
            elif t.result == 'FAIL':
                fails.append(t)

        if fail_ratio is None:
            fail_ratio = self.fail_ratio
        if random.random() < fail_ratio:
            return random.choice(fails)
        else:
            return random.choice(passes)

    def apply(self, item):
        t = self._choose()
        sol = t.solve()
        patts = t.result_patts
        if patts is not None:
            if isinstance(patts, list):
                item.fail_patts |= patts
            else:
                item.fail_patts.add(patts)
        item.set(self.target, sol)

    @classmethod
    def from_dict(cls, data):
        name = data['name']
        del data['name']
        return cls(name, **data)

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)


def load(path):
    cstrs = []
    for root, _, files in os.walk(path):
        for fname in files:
            fpath = os.path.join(root, fname)
            with open(fpath) as fp:
                cstrs.extend(yaml.load(fp))

    cstrs = [Constraint.from_dict(c) for c in cstrs]
    return cstrs
