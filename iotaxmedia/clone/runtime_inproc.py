# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""In-process clone runtime: namespace swap + task-scoped import hook.

A clone boots by evicting ``config`` and ``iotaxmedia.*`` from sys.modules,
swapping env to the clone's identity, and re-importing the world fresh. A
global import hook then routes scoped imports by asyncio task context:

- clone runtime tasks  -> their own captured module tree,
- boot section         -> falls through (fresh execution, ctx is raised),
- everyone else during -> the saved PARENT modules, so main-bot coroutines
  an open window          never re-execute the package into a rogue copy.
"""

import asyncio
import builtins
import contextvars
import logging
import os
import sys
import time
import traceback

logger = logging.getLogger("iotaxmedia.clone")
import types
from typing import Any, Dict, Optional

_PKG_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
_ROOT = os.path.dirname(_PKG_DIR)


def _is_scoped(name: str) -> bool:
    return name == "config" or name == "iotaxmedia" or name.startswith("iotaxmedia.")


_CLONE_CTX: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "iotax_clone_token", default=None
)
_CLONE_TREES: Dict[str, Dict[str, types.ModuleType]] = {}
_WINDOW_SAVED: Optional[Dict[str, types.ModuleType]] = None









_TRUE_IMPORT = getattr(builtins, "_IOTAX_TRUE_IMPORT", None)
if _TRUE_IMPORT is None:
    _TRUE_IMPORT = builtins.__import__
    builtins._IOTAX_TRUE_IMPORT = _TRUE_IMPORT  # type: ignore[attr-defined]

_SHARED_CTX = getattr(builtins, "_IOTAX_CLONE_CTX", None)
if _SHARED_CTX is None:
    _SHARED_CTX = contextvars.ContextVar("iotax_clone_token", default=None)
    builtins._IOTAX_CLONE_CTX = _SHARED_CTX  # type: ignore[attr-defined]
_CLONE_CTX = _SHARED_CTX  # type: ignore[assignment]

_SHARED_TREES = getattr(builtins, "_IOTAX_CLONE_TREES", None)
if _SHARED_TREES is None:
    _SHARED_TREES = {}
    builtins._IOTAX_CLONE_TREES = _SHARED_TREES  # type: ignore[attr-defined]
_CLONE_TREES = _SHARED_TREES  # type: ignore[assignment]


def _set_window(tree: Optional[Dict[str, types.ModuleType]]) -> None:
    global _WINDOW_SAVED
    _WINDOW_SAVED = tree
    builtins._IOTAX_WINDOW_SAVED = tree  # type: ignore[attr-defined]


def _get_window() -> Optional[Dict[str, types.ModuleType]]:
    return getattr(builtins, "_IOTAX_WINDOW_SAVED", None)


_ORIG_IMPORT = _TRUE_IMPORT


def _clone_import(
    name: str,
    globals=None,
    locals=None,
    fromlist=(),
    level: int = 0,
) -> Any:
    if level == 0 and _is_scoped(name):
        window = _get_window()
        token = _CLONE_CTX.get()





        if token is not None and window is None:
            tree = _CLONE_TREES.get(token)
            if tree is not None:
                if fromlist:
                    mod = tree.get(name)
                    if mod is not None:
                        return mod
                else:
                    top = name.split(".", 1)[0]
                    mod = tree.get(top)
                    if mod is not None:
                        return mod

        elif token is None and window is not None:


            if fromlist:
                mod = window.get(name)
                if mod is not None:
                    return mod
            else:
                top = name.split(".", 1)[0]
                mod = window.get(top)
                if mod is not None:
                    return mod
    return _ORIG_IMPORT(name, globals, locals, fromlist, level)


def install_hook() -> None:
    global _ORIG_IMPORT


    _ORIG_IMPORT = _TRUE_IMPORT
    if builtins.__import__ is not _clone_import:
        builtins.__import__ = _clone_import


def _snapshot_current_tree() -> Dict[str, types.ModuleType]:
    """Snapshot every scoped module currently loaded (used mid-boot)."""
    return {n: sys.modules[n] for n in list(sys.modules) if _is_scoped(n)}


def parent_module(name: str) -> Optional[types.ModuleType]:
    """Fetch a MAIN-bot module explicitly from the saved window snapshot.

    Clone-context code must use this to reach PARENT-side singletons (e.g.
    the real CloneManager): a plain import inside a clone task resolves to
    the clone's own tree copy, whose module globals are separate.
    """
    mod = _get_window().get(name) if _get_window() is not None else None
    if mod is not None:
        return mod
    return sys.modules.get(name)


class CloneNamespace:
    """Builds a fresh ``config`` + ``iotaxmedia`` tree for one clone."""

    def __init__(self, token: str):
        self.token = token.strip()
        self._saved: Dict[str, Optional[types.ModuleType]] = {}
        self._env: Dict[str, Optional[str]] = {}
        self.active = False

    def begin(self) -> None:
        install_hook()
        for name in list(sys.modules):
            if _is_scoped(name):
                self._saved[name] = sys.modules.pop(name)
        self._env = {
            k: os.environ.get(k)
            for k in ("CLONE_MODE", "CLONE_TOKEN", "BOT_TOKEN")
        }
        os.environ["CLONE_MODE"] = "1"
        os.environ["CLONE_TOKEN"] = self.token
        os.environ["BOT_TOKEN"] = self.token
        _set_window({n: m for n, m in self._saved.items() if m is not None})
        self.active = True

    def end(self) -> None:
        for name in list(sys.modules):
            if _is_scoped(name):
                sys.modules.pop(name, None)
        for name, mod in self._saved.items():
            if mod is not None:
                sys.modules[name] = mod
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _set_window(None)
        self.active = False

    def import_fresh(self, name: str) -> types.ModuleType:
        if not self.active:
            raise RuntimeError("CloneNamespace not active")
        return __import__(name, globals(), locals(), [], 0)


class InProcessClone:
    """One clone bot running as an asyncio task inside the main process."""

    def __init__(self, token: str):
        self.token = token.strip()
        self.ns = CloneNamespace(self.token)
        self.task: Optional[asyncio.Task] = None  # noqa: F821 (set in start)
        self.shutdown_event = None
        self.plugins_ready = None
        self.app: Any = None
        self.config_mod: Any = None
        self.borrowing = False

    async def start(self) -> bool:
        if self.task is not None and not self.task.done():
            return True
        install_hook()



        ctx_token = _CLONE_CTX.set(self.token)
        self.ns.begin()



        window = _get_window()
        main_pkg = (window or {}).get("iotaxmedia")
        bridged = False
        if main_pkg is not None:
            builtins._BETA_MAIN_PKG = main_pkg  # type: ignore[attr-defined]
            bridged = True
        boot_ok = False
        try:
            self.shutdown_event = asyncio.Event()
            self.plugins_ready = asyncio.Event()


            from iotaxmedia.clone import boot as boot_mod

            self.task = asyncio.create_task(
                boot_mod.run(self),
                name=f"clone_{self.token.split(':')[0]}",
            )
            if not await self._wait_ready(timeout=120):
                await self.stop()
                logger.error(
                    f"Clone {self.token[:12]}… failed to become ready"
                )
                return False
            logger.info(f"[BETA_CLONE] {self.token[:12]}… online")
            boot_ok = True
        except Exception as exc:
            logger.error(
                f"Clone {self.token[:12]}… namespace boot failed: {exc}\n"
                + traceback.format_exc()
            )
            try:
                await self.stop()
            except Exception:
                pass
            return False
        finally:


            if boot_ok:
                self._capture_tree()
            else:
                _CLONE_TREES.pop(self.token, None)
            self.ns.end()
            if bridged:
                try:
                    del builtins._BETA_MAIN_PKG  # type: ignore[attr-defined]
                except AttributeError:
                    pass
            _CLONE_CTX.reset(ctx_token)
        return True

    def _capture_tree(self) -> None:
        tree: Dict[str, types.ModuleType] = {}
        for name in list(sys.modules):
            if _is_scoped(name):
                tree[name] = sys.modules[name]
        if tree:
            _CLONE_TREES[self.token] = tree

    async def _wait_ready(self, timeout: float) -> bool:
        deadline = time.time() + timeout
        while not self.plugins_ready.is_set():
            if self.task is not None and self.task.done():
                return False
            if time.time() > deadline:
                return False
            await asyncio.sleep(0.25)
        return True

    async def stop(self) -> None:
        if self.shutdown_event is not None:
            self.shutdown_event.set()
        if self.task is None or self.task.done():
            _CLONE_TREES.pop(self.token, None)
            return
        app = self.app
        if app is not None:
            try:
                await asyncio.wait_for(app.exit(), timeout=15)
            except Exception:
                pass
        if not self.task.done():
            self.task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self.task), timeout=15)
        except Exception:
            pass


        _CLONE_TREES.pop(self.token, None)

    def is_running(self) -> bool:
        return bool(self.task is not None and not self.task.done())






try:
    if (
        getattr(builtins, "_IOTAX_PARENT_PKG", None) is None
        and _CLONE_CTX.get() is None
        and _get_window() is None
        and not os.environ.get("CLONE_MODE")
    ):
        import iotaxmedia as _parent_pkg

        builtins._IOTAX_PARENT_PKG = _parent_pkg  # type: ignore[attr-defined]
except Exception:
    pass


install_hook()
