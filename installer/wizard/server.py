"""Flask-based localhost wizard server for the QuickStockBot installer."""

from __future__ import annotations

import uuid as _uuid_mod
from typing import Any

from flask import Flask, Response, jsonify, make_response, request

from wizard import config_writer, reachability, validator
from wizard.html_wizard import WIZARD_HTML


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> Response:
        return Response(WIZARD_HTML, mimetype="text/html")

    @app.get("/api/status")
    def api_status() -> Response:
        return jsonify({"ok": True, "version": "1.0.0"})

    @app.post("/api/validate/alpaca")
    def api_validate_alpaca() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        paper = bool(data.get("paper", True))
        ok, msg = validator.validate_alpaca_keys(
            api_key=str(data.get("api_key", "")),
            api_secret=str(data.get("api_secret", "")),
            paper=paper,
        )
        return jsonify({"success": ok, "message": msg})

    @app.post("/api/validate/inputs")
    def api_validate_inputs() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        step = data.get("step")
        errors: dict[str, str] = {}

        if step == "credentials":
            err = validator.validate_relay_url(str(data.get("relay_url", "")))
            if err:
                errors["relay_url"] = err
            err = validator.validate_license_key(str(data.get("license_key", "")))
            if err:
                errors["license_key"] = err
            err = validator.validate_connection_password(
                str(data.get("connection_password", "")),
                str(data.get("connection_password_confirm", "")),
            )
            if err:
                errors["connection_password"] = err

        elif step == "scanner":
            errors.update(validator.validate_scanner_settings(data))

        elif step == "risk":
            errors.update(validator.validate_risk_settings(data))

        return jsonify({"valid": not errors, "errors": errors})

    @app.post("/api/check-relay")
    def api_check_relay() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        bot_id = str(data.get("bot_id") or _uuid_mod.uuid4())
        result = reachability.check_relay(
            relay_url=str(data.get("relay_url", "")),
            bot_id=bot_id,
            license_key=str(data.get("license_key", "")),
            connection_password=str(data.get("connection_password", "")),
            timeout=15.0,
        )
        return jsonify(
            {
                "success": result.success,
                "bot_url": result.bot_url,
                "message": result.message,
                "bot_id": bot_id,
            }
        )

    @app.post("/api/install")
    def api_install() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        try:
            config_dir, bot_id = config_writer.write_config(data)

            # Extract the bundled bot exe to a permanent location.
            bot_exe_path = config_writer.extract_bot_exe(config_dir)

            # Register the BOT exe (not the installer) for autostart on login.
            try:
                config_writer.setup_autostart(str(bot_exe_path), config_dir)
                autostart_ok = True
                autostart_msg = "Autostart configured."
            except Exception as exc:
                autostart_ok = False
                autostart_msg = f"Autostart setup failed (manual setup required): {exc}"

            # Create a desktop shortcut so the user can restart the bot manually.
            try:
                config_writer.create_desktop_shortcut(bot_exe_path)
                shortcut_ok = True
                shortcut_msg = "Desktop shortcut created."
            except Exception as exc:
                shortcut_ok = False
                shortcut_msg = f"Desktop shortcut could not be created: {exc}"

            # Launch the bot immediately — no need to wait for a reboot.
            try:
                config_writer.launch_bot(bot_exe_path)
                launched = True
                launch_msg = "Bot started."
            except Exception as exc:
                launched = False
                launch_msg = f"Could not start bot automatically: {exc}"

            return jsonify(
                {
                    "success": True,
                    "bot_id": bot_id,
                    "config_dir": str(config_dir),
                    "autostart_ok": autostart_ok,
                    "autostart_message": autostart_msg,
                    "shortcut_ok": shortcut_ok,
                    "shortcut_message": shortcut_msg,
                    "bot_launched": launched,
                    "launch_message": launch_msg,
                }
            )
        except Exception as exc:
            resp = make_response(jsonify({"success": False, "message": str(exc)}), 500)
            return resp

    @app.post("/api/uninstall")
    def api_uninstall() -> Response:
        try:
            config_writer.uninstall()
            return jsonify({"success": True})
        except Exception as exc:
            resp = make_response(jsonify({"success": False, "message": str(exc)}), 500)
            return resp

    return app
