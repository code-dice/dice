import ast
import copy
import os
import random
import yaml

from . import trace


class ConstraintError(Exception):
    """
    Constraint module specified exception.
    """
    pass


class ConstraintManager(object):
    """
    Manager class contains and manipulates all constraints.
    """
    def __init__(self, provider):
        """
        :param path: Directory to load constraint YAML file from.
        """
        self.provider = provider
        path = os.path.join(provider.path, 'oracles')
        self.constraints = self._load_constraints(path)
        self.item = None
        self.status = {}

    def _load_constraints(self, path):
        """
        Load constraints from a directory containing YAML files.

        :param path: Directory to load constraint YAML file from.
        """
        cstrs = []
        for root, _, files in os.walk(path):
            for fname in files:
                fpath = os.path.join(root, fname)
                with open(fpath) as fp:
                    cstrs.extend(yaml.load(fp))

        cstrs = [Constraint.from_dict(self.provider, c) for c in cstrs]
        return cstrs

    def _assumption_valid(self, constraint):
        """
        Check whether the assumption of a constraint is valid.

        :param constraint: The constraint whose assumption to be checked.
        """
        if constraint.require is None:
            return True

        module = ast.parse(constraint.require)
        assert len(module.body) == 1
        expr = module.body[0]
        assert isinstance(expr, ast.Expr)

        compare = expr.value
        assert isinstance(compare, ast.Compare)

        assert len(compare.ops) == 1
        left = compare.left
        if isinstance(left, ast.Name):
            left = left.id
        op = compare.ops[0].__class__.__name__
        right = compare.comparators[0]

        if isinstance(right, ast.Name):
            right = right.id

        if left in self.status:
            left = self.status[left]

        if op == 'Is':
            return left.lower() == right.lower()
        else:
            raise ConstraintError('Operator %s is not handled' % op)

    def constrain(self, item):
        """
        Apply constraints to an item.

        :param item: Item for constraints to apply on.
        """
        self.item = item
        self.status = {c.name: 'untouched'
                       for c in self.constraints}
        while any(s == 'untouched' for s in self.status.values()):
            for constraint in self.constraints:
                if self._assumption_valid(constraint):
                    result = constraint.apply(item)
                else:
                    result = 'skipped'

                self.status[constraint.name] = result


class Constraint(object):
    """
    Class for a constraint on specific option of test item.
    """

    def __init__(self, name, provider,
                 depends_on=None, require=None, path=None, oracle=None):
        """
        :param name: Unique string name of the constraint.
        :param depends_on: A logical expression shows prerequisite to apply
                           this constraint.
        :param require: Logical expression shows the limit of this constraint.
        :param oracle: A block of code shows the details of this constraint.
        """
        self.name = name
        self.provider = provider
        self.depends_on = depends_on
        self.require = require
        self.path = path
        self.oracle = oracle
        self.fail_ratio = 0.1
        self.traces = self._oracle2traces(oracle)

    @classmethod
    def from_dict(cls, provider, data):
        """
        Generate a constraint instance from a dictionary
        """
        name = data['name']
        del data['name']
        return cls(name, provider, **data)

    def _oracle2traces(self, oracle):
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
                    traces.append(trace.Trace(self.provider, cur_trace))
                    cur_trace.pop()
                else:
                    raise ConstraintError('Unknown node: %s' % node)

        def _parse_module(node):
            # Accept a single expression to define the only valid condition
            if isinstance(node.body[0], ast.Expr):
                assert len(node.body) == 1
                cur_trace.append(node.body[0].value)
                ret = ast.parse('return success()').body[0]
                cur_trace.append(ret)
                traces.append(trace.Trace(self.provider, cur_trace))
                cur_trace.pop()
                cur_trace.pop()
            else:
                _parse_block(v.body)

        root = ast.parse(oracle)
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
                    _parse_module(v)
                else:
                    raise ConstraintError('Unknown node: %s' % v)
        return traces

    def _choose(self, fail_ratio=None):
        fails = []
        passes = []

        for t in self.traces:
            if t.result == 'success':
                passes.append(t)
            elif t.result == 'fail':
                fails.append(t)

        if fail_ratio is None:
            fail_ratio = self.fail_ratio
        if random.random() < fail_ratio:
            return random.choice(fails)
        else:
            return random.choice(passes)

    def apply(self, item):
        """
        Apply this constraint to an item.

        :param item: The item to be applied on.
        :return: Expected result of constraint item.
        """
        t = self._choose()
        sol = t.solve(item)
        patts = t.result_patts
        if patts is not None:
            if isinstance(patts, list):
                item.fail_patts |= patts
            else:
                item.fail_patts.add(patts)
        item.set(self.path, sol)
        return t.result

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)
