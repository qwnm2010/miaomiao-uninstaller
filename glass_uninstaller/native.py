"""ctypes bridge to the optional C filesystem accelerator."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Iterable

_INVALID = 0xFFFFFFFFFFFFFFFF


class NativeCore:
    def __init__(self) -> None:
        self.lib = None
        self.path = Path(__file__).resolve().parent.parent / "libmiaomiao.so"
        try:
            lib = ctypes.CDLL(str(self.path))
            lib.mm_dir_size.argtypes = [ctypes.c_char_p, ctypes.c_int]
            lib.mm_dir_size.restype = ctypes.c_uint64
            lib.mm_paths_size.argtypes = [
                ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_int
            ]
            lib.mm_paths_size.restype = ctypes.c_uint64
            lib.mm_cancel.argtypes = []
            lib.mm_cancel.restype = None
            lib.mm_clear_cancel.argtypes = []
            lib.mm_clear_cancel.restype = None
            self.lib = lib
        except (OSError, AttributeError):
            self.lib = None

    @property
    def available(self) -> bool:
        return self.lib is not None

    def dir_size(self, path: str | Path, budget_ms: int = 2000) -> int | None:
        if self.lib is None:
            return None
        result = int(self.lib.mm_dir_size(os.fsencode(str(path)),
                                          max(1, int(budget_ms))))
        return None if result == _INVALID else result

    def cancel(self) -> None:
        if self.lib is not None:
            self.lib.mm_cancel()

    def clear_cancel(self) -> None:
        if self.lib is not None:
            self.lib.mm_clear_cancel()

    def paths_size(self, paths: Iterable[str | Path], budget_ms: int = 2000) -> int | None:
        if self.lib is None:
            return None
        encoded = [os.fsencode(str(p)) for p in paths]
        if not encoded:
            return 0
        array = (ctypes.c_char_p * len(encoded))(*encoded)
        result = int(self.lib.mm_paths_size(array, len(encoded),
                                            max(1, int(budget_ms))))
        return result


native = NativeCore()
