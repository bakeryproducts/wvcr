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
    
    # This will send a real notification
    notification_manager.send_notification(title, text, timeout)
    
    # Since we're testing real notifications, we can only verify
    # that the call doesn't raise any exceptions
    # The actual notification will be visible on the system
