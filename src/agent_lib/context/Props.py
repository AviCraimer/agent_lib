from __future__ import annotations
from typing import TYPE_CHECKING, Any, dataclass_transform

from dataclasses import dataclass

if TYPE_CHECKING:
    from agent_lib.context.CtxComponent import Children


@dataclass_transform(frozen_default=True, kw_only_default=True)
@dataclass(frozen=True, kw_only=True)
class Props:
    """This is the base class for props. Other props child inherit from this. It can also be used directly to construct props that only have children with no other arguments."""

    children: Children = None

    # 2. We tell Python Runtime: "When a child inherits this, make it a dataclass"
    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        # Apply the dataclass logic to the child class
        dataclass(frozen=True, kw_only=True)(cls)


class JustChildren(Props):
    """This is a used for lexically typing props that have only the children argument. No other classes should inherit from this class."""


class NoProps(Props):
    """Convinence class for empty props."""

    children: None = None
