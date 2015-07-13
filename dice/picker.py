import inspect
import logging
import random
import sys
import types as mod_types

from . import data


logger = logging.getLogger(__name__)


class PickerError(Exception):
    pass


class PickImpossibleError(PickerError):
    pass


class PickSkippedError(PickerError):
    pass


class PickerBase(object):
    types = {}
    data_type = None

    def __init__(self, test):
        self.test = test
        for tp in self.types.values():
            params = {'test': self.test}
            try:
                tp['data_type'].set_params(params)
            except (KeyError, AttributeError):
                pass

    def prerequisite(self):
        cls_name = self.__class__.__name__
        name = inspect.stack()[0][3]
        raise NotImplementedError(
            "Method '%s' should be implemented for class '%s'" %
            (name, cls_name))

    def apply(self, _):
        cls_name = self.__class__.__name__
        name = inspect.stack()[0][3]
        raise NotImplementedError(
            "Method '%s' should be implemented for class '%s'" %
            (name, cls_name))

    def apply_many(self, _):
        cls_name = self.__class__.__name__
        name = inspect.stack()[0][3]
        raise NotImplementedError(
            "Method '%s' should be implemented for class '%s'" %
            (name, cls_name))

    def predict(self):
        cls_name = self.__class__.__name__
        name = inspect.stack()[0][3]
        raise NotImplementedError(
            "Method '%s' should be implemented for class '%s'" %
            (name, cls_name))


class Picker(PickerBase):
    def pick(self, positive_weight=0.9):
        types = self.types.keys()
        if not types:
            raise ValueError("Property 'types' is not set for %s" %
                             self.__class__.__name__)

        # Weighted pick to favor positive result
        if 'positive' in types and random.random() < positive_weight:
            chosen_type = 'positive'
        else:
            chosen_type = random.choice(types)

        logger.debug('Chosen type is %s in %s', chosen_type, types)

        # Get chosen data type instance and failure patterns.
        if chosen_type == 'other':
            data_type = self.data_type
            for type_name, tp in self.types.items():
                if type_name != 'other':
                    data_type -= tp['data_type']
        else:
            try:
                data_type = self.types[chosen_type]['data_type']
            except KeyError:
                raise KeyError(
                    "Type '%s' don't have 'data_type' in class '%s'" %
                    (chosen_type, self.__class__.__name__))
        fail_patts = self.types[chosen_type]['patterns']
        logger.debug('Fail patterns are %s', fail_patts)

        try:
            if data_type:
                res = data_type.generate()
            else:
                res = None
        except (ValueError, data.CanNotGenerateError), detail:
            raise PickImpossibleError(
                "Can't generate data. Picking is impossible: %s" %
                detail)
        try:
            self.apply(res)
        except NotImplementedError:
            pass
        try:
            self.apply_many(data_type)
        except NotImplementedError:
            pass

        return fail_patts


class Checker(PickerBase):
    def pick(self, positive_weight=0.9):
        types = self.types.keys()
        if not types:
            raise ValueError("Property 'types' is not set for %s" %
                             self.__class__.__name__)

        predicted_type = self.predict()
        if 'positive' in types and predicted_type != 'positive':
            if random.random() < positive_weight:
                raise PickSkippedError("Pick skipped")
        fail_patts = self.types[predicted_type]['patterns']
        return fail_patts


class Setter(PickerBase):
    def pick(self, positive_weight=0.9):
        types = {
            'true&set': None,
            'true&unset': None,
            'false&set': None,
            'false&unset': None,
        }
        pos_types = []
        neg_types = []
        pred_func = getattr(self, 'predicate')
        patterns = getattr(self, 'patterns')

        pred = 'true' if pred_func() else 'false'
        for tp in types:
            if tp in patterns and patterns[tp] is not None:
                types[tp] = patterns[tp]
                if tp.startswith(pred):
                    neg_types.append(tp)
            else:
                if tp.startswith(pred):
                    pos_types.append(tp)

        if pos_types:
            if neg_types:
                if random.random() < positive_weight:
                    chosen_type = random.choice(pos_types)
                else:
                    chosen_type = random.choice(neg_types)
            else:
                chosen_type = random.choice(pos_types)
        else:
            if neg_types:
                chosen_type = random.choice(neg_types)
            else:
                raise PickImpossibleError("No valid choice")

        should_set = chosen_type.split('&')[1] == 'set'
        self.apply(should_set)
        return types[chosen_type]


def pick(item, root=None):
    picker_classes = {root.__name__: root}
    logger.debug('Start picking')
    while True:
        logger.debug('Current %s pickers: %s', len(picker_classes), picker_classes)
        picked_count = 0
        for name, picker_class in picker_classes.items():
            picker = picker_class(item)
            match = picker.prerequisite()
            if match:
                picked_count += 1
                fail_patt = picker.pick()
                if fail_patt:
                    if isinstance(fail_patt, mod_types.StringType):
                        item.fail_patts.add(fail_patt)
                    elif isinstance(fail_patt, mod_types.ListType):
                        item.fail_patts |= set(fail_patt)
                else:
                    if hasattr(picker_class, 'children'):
                        for c_name, c_picker in picker_class.children.items():
                            picker_classes[c_name] = c_picker
                del picker_classes[name]
        logger.debug('Picked %d from %d', picked_count, len(picker_classes))
        if picked_count == 0:
            break


def setup_picker_tree(module):
    def _picker_predicate(member):
        return inspect.isclass(member) and issubclass(member, PickerBase)

    pickers = dict(
        inspect.getmembers(sys.modules[module.__name__],
                           predicate=_picker_predicate))

    logger.debug('Found %s pickers: %s', len(pickers), pickers)

    root = pickers[module.root_picker]

    for name, picker in pickers.items():
        parent = picker.depends_on
        if parent is None:
            if name != root.__name__:
                raise ValueError('Non-root picker %s has no parent' % name)
        else:
            if hasattr(parent, 'children'):
                parent.children[name] = picker
            else:
                setattr(parent, 'children', {name: picker})
    return root
