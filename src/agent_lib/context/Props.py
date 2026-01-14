from __future__ import annotations
from typing import TYPE_CHECKING, dataclass_transform

from dataclasses import dataclass

if TYPE_CHECKING:
    from agent_lib.context.CtxComponent import Children


@dataclass_transform(frozen_default=True, kw_only_default=True)
def propsclass[T](cls: type[T]):
    return dataclass(frozen=True, kw_only=True)(cls)


@propsclass
class Props:
    """This is the base class for props. Other props child inherit from this. It can also be used directly to construct props that only have children with no other arguments."""

    children: Children = None


@propsclass
class JustChildren(Props):
    """This is a used for lexically typing props that have only the children argument. No other classes should inherit from this class."""


@propsclass
class NoProps(Props):
    """Convinence class for empty props."""

    children: None = None
