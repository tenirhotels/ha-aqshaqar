"""Config flow for AQSHAQAR."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN, NAME, VERSION


class AqshaqarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the AQSHAQAR config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Install AQSHAQAR without additional user credentials."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title=f"{NAME} — Shymbulak",
                data={"version": VERSION},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
