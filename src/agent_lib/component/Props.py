from __future__ import annotations
from typing import TypedDict, TYPE_CHECKING

from dataclasses import dataclass

if TYPE_CHECKING:
    from agent_lib.component.ContextComponent import Children


@dataclass(frozen=True)
class Props:
    """This is the base class for props. Other props child inherit from this. It can also be used directly to construct props that only have children with no other arguments."""

    children: Children


@dataclass(frozen=True)
class JustChildren(Props):
    """This is a used for lexically typing props that have only the children argument. No other classes should inherit from this class."""


@dataclass(frozen=True)
class NoProps(Props):
    """Convinence class for empty props."""

    children: Children = None
