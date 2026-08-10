"""Importing this package registers every adapter with base._REGISTRY."""

import importlib
import pkgutil

from awesome_log_data.base import DatasetAdapter, DatasetId

_REGISTRY: dict[DatasetId, type[DatasetAdapter]] = {}


def register[A: type[DatasetAdapter]](adapter: A) -> A:
    "Class decorator: registers adapter under adapter.dataset_id."
    if adapter.dataset_id in _REGISTRY:
        raise ValueError(f"dataset_id {adapter.dataset_id!r} is already registered")
    _REGISTRY[adapter.dataset_id] = adapter
    return adapter


def adapter_exists(dataset_id: DatasetId) -> bool:
    return dataset_id in _REGISTRY


def get_adapter(dataset_id: DatasetId) -> type[DatasetAdapter]:
    try:
        return _REGISTRY[dataset_id]
    except KeyError:
        raise LookupError(f"no adapter registered for dataset_id {dataset_id!r}") from None


# Each submodule calls register() (defined above) as a class decorator at
# import time. Importing a package's __init__.py does not, by itself, import
# its submodules — so without this, nothing would ever trigger that
# decorator and _REGISTRY would stay empty for real callers like cli.py,
# which only imports this package, never the submodules directly. Auto-
# discovering and importing every submodule here means a new adapters/<x>.py
# file registers itself without this file needing to be touched. Must run
# after register()/_REGISTRY/get_adapter are defined above: each submodule
# does `from awesome_log_data.adapters import register`, which would hit a
# partially-initialized module if this ran first.
for _module_info in pkgutil.iter_modules(__path__, prefix=f"{__name__}."):
    importlib.import_module(_module_info.name)
