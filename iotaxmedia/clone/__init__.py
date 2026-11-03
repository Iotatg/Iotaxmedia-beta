# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone subsystem for iotaxmedia-beta.

In-process clone bots: each clone boots in its own namespace with its own
config/client tree; clones without their own session strings borrow the main
bot's assistants and playback state (see borrow.py).
"""

from iotaxmedia.clone.runtime import CloneManager, get_clone_manager

__all__ = ["CloneManager", "get_clone_manager"]
