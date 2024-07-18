from __future__ import annotations

import importlib
import types
from types import TracebackType
from typing import Any
from typing import Optional
from typing import Tuple
from typing import Type


_INTEGRATION_IMPORT_ERROR_TEMPLATE = (
    "\nCould not find `optuna-integration` for `{0}`.\n"
    "Please run `pip install optuna-integration[{0}]`."
)


class _DeferredImportExceptionContextManager:
    """Context manager to defer exceptions from imports.

    Catches :exc:`ImportError` and :exc:`SyntaxError`.
    If any exception is caught, this class raises an :exc:`ImportError` when being checked.

    Args:
        module_to_package_name:
            A custom package name used when the module import fails.
            This argument should be used when the module name and the package name registered in
            PyPI are different. For example, ``google.cloud.storage`` is registered as
            ``google-cloud-storage`` in PyPI, but the module name is ``google``. We can notify
            the true package name to users by using this argument.
    """

    def __init__(self, module_to_package_name: dict[str, str]) -> None:
        self._deferred: Optional[Tuple[Exception, str]] = None
        self._module_to_package_name = module_to_package_name

    def __enter__(self) -> "_DeferredImportExceptionContextManager":
        """Enter the context manager.

        Returns:
            Itself.

        """
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_value: Optional[Exception],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        """Exit the context manager.

        Args:
            exc_type:
                Raised exception type. :obj:`None` if nothing is raised.
            exc_value:
                Raised exception object. :obj:`None` if nothing is raised.
            traceback:
                Associated traceback. :obj:`None` if nothing is raised.

        Returns:
            :obj:`None` if nothing is deferred, otherwise :obj:`True`.
            :obj:`True` will suppress any exceptions avoiding them from propagating.

        """
        if isinstance(exc_value, (ImportError, SyntaxError)):
            if isinstance(exc_value, ImportError):
                print(exc_value.name)
                package_name = self._module_to_package_name.get(str(exc_value.name))
                package_info = (
                    f"'{exc_value.name}'"
                    if package_name is None
                    else f"'{exc_value.name}' (Package Name: {package_name})"
                )
                message = (
                    "Tried to import {} but failed. Please make sure that the package is "
                    "installed correctly to use this feature. Actual error: {}."
                ).format(package_info, exc_value)
            elif isinstance(exc_value, SyntaxError):
                message = (
                    "Tried to import a package but failed due to a syntax error in {}. Please "
                    "make sure that the Python version is correct to use this feature. Actual "
                    "error: {}."
                ).format(exc_value.filename, exc_value)
            else:
                assert False

            self._deferred = (exc_value, message)
            return True
        return None

    def is_successful(self) -> bool:
        """Return whether the context manager has caught any exceptions.

        Returns:
            :obj:`True` if no exceptions are caught, :obj:`False` otherwise.

        """
        return self._deferred is None

    def check(self) -> None:
        """Check whether the context manager has caught any exceptions.

        Raises:
            :exc:`ImportError`:
                If any exception was caught from the caught exception.

        """
        if self._deferred is not None:
            exc_value, message = self._deferred
            raise ImportError(message) from exc_value


def try_import(
    module_to_package_name: dict[str, str] | None = None
) -> _DeferredImportExceptionContextManager:
    """Create a context manager that can wrap imports of optional packages to defer exceptions.

    Args:
        module_to_package_name:
            A custom package name used when the module import fails.
            This argument should be used when the module name and the package name registered in
            PyPI are different. For example, ``google.cloud.storage`` is registered as
            ``google-cloud-storage`` in PyPI, but the module name is ``google``. We can notify
            the true package name to users by using this argument.

    Returns:
        Deferred import context manager.

    """
    return _DeferredImportExceptionContextManager(module_to_package_name or {})


class _LazyImport(types.ModuleType):
    """Module wrapper for lazy import.

    This class wraps the specified modules and lazily imports them only when accessed.
    Otherwise, `import optuna` is slowed down by importing all submodules and
    dependencies even if not required.
    Within this project's usage, importlib override this module's attribute on the first
    access and the imported submodule is directly accessed from the second access.

    Args:
        name: Name of module to apply lazy import.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._name = name

    def _load(self) -> types.ModuleType:
        module = importlib.import_module(self._name)
        self.__dict__.update(module.__dict__)
        return module

    def __getattr__(self, item: str) -> Any:
        return getattr(self._load(), item)
