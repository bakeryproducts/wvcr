from loguru import logger
from plyer import notification


class NotificationManager:
    @staticmethod
    def send_notification(title: str, text: str, timeout: int = 10, color: str = '#2ecc71', font_size: str = '32px'):
        """
        Send a system notification with styled text.
        
        Args:
            title: Notification title
            text: Message text
            timeout: Notification display duration in seconds
            color: HTML color code for the text
            font_size: Font size with units (e.g. '32px', '12pt')
        """
        notification_text = text[:100] + ('...' if len(text) > 100 else '')
        message = f"<span color='{color}' font='{font_size}'><i><b>{notification_text}</b></i></span>"
        
        try:
            notification.notify(
                title=title,
                message=message,
                app_name='WVCR',
                app_icon=None,
                timeout=timeout,
                ticker='WVCR Notification',
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def test_notification(self):
        """Test the notification system with a sample message."""
        test_message = "This is a test notification message. If you see this, notifications are working correctly!"
        self.send_notification("Test Notification", test_message, font_size='24px')
        logger.info("Notification test completed")