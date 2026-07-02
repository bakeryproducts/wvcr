import subprocess
from typing import Protocol

from loguru import logger
from plyer import notification


class NotificationBackend(Protocol):
    @staticmethod
    def send_notification(
        title: str,
        text: str,
        timeout: int = 3,
        color: str = "#2ecc71",
        font_size: str = "32px",
        cutoff: int | None = None,
    ) -> None: ...


class HyprlandNotificationManager:
    @staticmethod
    def send_notification(
        title: str,
        text: str,
        timeout: int = 3,
        color: str = "#2ecc71",
        font_size: str = "32px",
        cutoff: int | None = None,
    ):
        if cutoff and len(text) > cutoff:
            text = text[:cutoff] + "..."

        color_hex = color.lstrip("#")
        timeout_ms = timeout * 1000
        message = f"fontsize:{font_size.rstrip('px')} {title}: {text}"

        try:
            subprocess.run(
                [
                    "hyprctl",
                    "notify",
                    "-1",
                    str(timeout_ms),
                    f"rgb({color_hex})",
                    message,
                ],
                check=True,
                capture_output=True,
            )
        except Exception as e:
            logger.exception(e)
            logger.error(f"Failed to send Hyprland notification: {e}")


class SystemNotificationManager:
    @staticmethod
    def send_notification(
        title: str,
        text: str,
        timeout: int = 3,
        color: str = "#2ecc71",
        font_size: str = "32px",
        cutoff: int | None = None,
    ):
        if cutoff and len(text) > cutoff:
            text = text[:cutoff] + "..."

        message = (
            f"<span color='{color}' font='{font_size}'><i><b>{text}</b></i></span>"
        )

        try:
            notification.notify(
                title=title,
                message=message,
                app_name="WVCR",
                app_icon=None,
                timeout=timeout,
                ticker="WVCR Notification",
            )
        except Exception as e:
            logger.exception(e)
            logger.error(f"Failed to send system notification: {e}")


class LayerShellNotificationManager:
    @staticmethod
    def send_notification(
        title: str,
        text: str,
        timeout: int = 3,
        color: str = "#2ecc71",
        font_size: str = "32px",
        cutoff: int | None = None,
    ):
        if cutoff and len(text) > cutoff:
            text = text[:cutoff] + "..."

        from wvcr.hint.popup import show_popup

        try:
            show_popup(title=title, text=text, timeout=timeout, color=color)
        except Exception as e:
            logger.exception(e)
            logger.error(f"Failed to show layer-shell popup: {e}")


# Legacy alias
NotificationManager = SystemNotificationManager
