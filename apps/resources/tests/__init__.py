"""Monkeypatches for test environment compatibility.

Python 3.14 / Django 5.1 compatibility patches.
"""

from django.template.context import BaseContext


def _patched_base_context_copy(self):
    """Avoid super().__copy__() which breaks on Python 3.14.

    ``super().__copy__()`` resolves to ``MutableMapping.__copy__()``
    which does ``return self.__class__(self)``.  We inline that call
    to bypass the broken ``super()`` resolution on Python 3.14.
    """
    duplicate = self.__class__(self)  # Same as MutableMapping.__copy__
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _patched_base_context_copy
