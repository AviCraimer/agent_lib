# -*- coding: utf-8 -*-
import inspect
from typing import Any, Callable, Generic, Self, TYPE_CHECKING, override

# Define the type of function we wrap (classmethod or staticmethod)
type DescriptorFunc = classmethod[Any, Any, Any] | staticmethod[Any, Any]


class ClassProperty[T]:
    """
    A descriptor that mimics @property but works on the class level.
    """

    fget: DescriptorFunc
    fset: DescriptorFunc | None

    def __init__(
        self,
        fget: DescriptorFunc | Callable[..., T],
        fset: DescriptorFunc | Callable[..., Any] | None = None,
    ) -> None:
        self.fget = self._ensure_descriptor(fget)
        self.fset = self._ensure_descriptor(fset) if fset is not None else None

    @staticmethod
    def _ensure_descriptor(func: DescriptorFunc | Callable[..., Any]) -> DescriptorFunc:
        if isinstance(func, (classmethod, staticmethod)):
            return func
        return classmethod(func)  # type: ignore

    def __get__(self, obj: Any, owner: type | None = None) -> T:
        if owner is None and obj is not None:
            owner = type(obj)
        return self.fget.__get__(obj, owner)()  # type: ignore

    # --- THE TRICK IS HERE ---
    # We define __set__ and setter ONLY at runtime.
    # Inside TYPE_CHECKING, these do not exist.
    # This forces Pylance to treat this as a Read-Only attribute on the instance.
    if not TYPE_CHECKING:

        def __set__(self, obj: Any, value: Any) -> None:
            if not self.fset:
                raise AttributeError("Cannot set read-only class property")

            if inspect.isclass(obj):
                func = self.fset.__get__(None, obj)
            else:
                func = self.fset.__get__(obj, type(obj))
            return func(value)

        def setter(self, func: Callable[[Any, Any], None]) -> Self:
            self.fset = self._ensure_descriptor(func)
            return self


def class_property[T](
    func: Callable[[Any], T] | DescriptorFunc,
) -> ClassProperty[T]:
    return ClassProperty(func)


class ClassPropertyMetaClass(type(Generic)):  # type: ignore
    @override
    def __setattr__(cls, key: str, value: Any) -> None:
        if key in cls.__dict__:
            obj = cls.__dict__.get(key)
            # Check for the descriptor at runtime
            if isinstance(obj, ClassProperty):
                # We call the hidden __set__ method manually
                return obj.__set__(cls, value)  # type: ignore

        return super().__setattr__(key, value)
