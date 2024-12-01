import pytest
from wvcr.notification_manager import NotificationManager

@pytest.fixture
def notification_manager():
    return NotificationManager()

def test_notification_manager_initialization(notification_manager):
    assert notification_manager is not None

def test_send_notification(notification_manager):
    title = "Test Title"
    text = "Test Message"
    timeout = 5
    
    notification_manager.send_notification(title, text, timeout)
