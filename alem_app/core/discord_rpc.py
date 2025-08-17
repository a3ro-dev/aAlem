
from datetime import datetime

from pypresence import Presence

from alem_app.utils.logging import logger


class DiscordRPCManager:
    def __init__(self, app_config):
        self.enabled = bool(app_config and app_config.get('discord_rpc_enabled', True) and Presence is not None)
        self.rpc = None
        self.started = datetime.now()
        if self.enabled:
            try:
                client_id = app_config.get('discord_client_id')
                self.rpc = Presence(client_id)
                self.rpc.connect()
                logger.info("Discord RPC connected")
                # Immediate initial update so presence (including buttons) shows right away
                try:
                    self.update(state="Idle", details="Alem - Smart Notes")
                except Exception as _e:
                    logger.debug(f"Discord initial update failed: {_e}")
            except Exception as e:
                logger.warning(f"Discord RPC disabled: {e}")
                self.enabled = False

    def update(self, state: str = "Editing notes", details: str = "Alem - Smart Notes"):
        if not self.enabled or self.rpc is None:
            return
        try:
            buttons = app_config.get('discord_buttons', []) if app_config else []
            logger.debug(f"Updating Discord RPC (buttons={buttons})")
            self.rpc.update(
                state=state,
                details=details,
                # Use a default asset key; ensure you upload an asset with this name in your Discord app
                large_image=app_config.get('discord_large_image', 'alem'),
                large_text=app_config.get('discord_large_text', 'Alem'),
                start=int(self.started.timestamp()),
                buttons=buttons if buttons else None,
            )
        except Exception as e:
            logger.debug(f"Discord RPC update failed: {e}")
            # don't disable permanently; transient errors are okay

    def close(self):
        if self.enabled and self.rpc is not None:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
