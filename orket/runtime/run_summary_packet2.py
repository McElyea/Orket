from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_module = _import_module("orket.runtime.summary.run_summary_packet2")
_sys.modules[__name__] = _module
_parent = _sys.modules[__name__.rsplit(".", 1)[0]]
setattr(_parent, __name__.rsplit(".", 1)[1], _module)
