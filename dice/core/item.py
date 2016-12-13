class ItemError(Exception):
    """
    Class for Item specific exceptions.
    """
    pass


class ItemBase(object):
    """
    Base class for an item. This should be overridden in the providers item.py.
    """
    def __init__(self, provider):
        self.provider = provider
        self.res = ''
        self.fail_patts = set()

    def run(self):
        """
        Run the item. Must be overridden in the providers.
        """
        raise NotImplementedError("run() not implemented for class '%s'" %
                                  self.__class__.__name__)

    def set(self, path, value):
        """
        Set value for specific item option.

        :param path: An XPath-like string for the setting target.
        :param value: Option value to be set.
        """
        setattr(self, path, value)

    def get(self, path):
        """
        Get value for specific item option.

        :param path: An XPath-like string for the getting target.
        :return: Option value got.
        """
        return getattr(self, path, None)
