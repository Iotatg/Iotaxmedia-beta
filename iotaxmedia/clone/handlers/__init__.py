# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone-side handler registration."""


CLONE_HANDLER_GROUP = 100

START_OVERRIDE_GROUP = -1


def register_clone_handlers(app, token: str, owner_id: int) -> None:
    from iotaxmedia.clone.handlers import customization, start_override

    customization.register(app, token, owner_id)
    start_override.register(app, token)
