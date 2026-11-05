"""utility module shim (UIFlow helper used by generated main.py files)."""

import sys

from stackchan_sim import compat


def print_error_msg(e):
    compat.print_exception(e)
    try:
        sys.stderr.flush()
    except AttributeError:
        pass
