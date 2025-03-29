import logging, os

from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_DOOR_LOCK

logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")

lock_name = os.environ.get('SCHLAGE_HOMEKIT_LOCK_NAME', 'My Lock')

class SchlageLock(Accessory):
    """Wrapper for dknowles2's pyschlage library"""

    category = CATEGORY_DOOR_LOCK

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock_mechanism = self.add_preload_service("LockMechanism")
        self.lock_target_state = self.lock_mechanism.get_characteristic("LockTargetState")
        self.lock_current_state = self.lock_mechanism.get_characteristic("LockCurrentState")

        self.lock_target_state.setter_callback = self.lock_changed

    """Callback for when HomeKit requests lock state to change"""
    def lock_changed(self, value):
        if value == 1:
            print("Locking the door...")
        else:
            print("Unlocking the door...")

        # Update the current state to reflect the change
        self.lock_current_state.set_value(value)

# Setup the accessory on port 51826
driver = AccessoryDriver(port=51826)

lock = SchlageLock(driver, "MyTempLock")

driver.add_accessory(accessory=lock)

# Start it!
driver.start()
