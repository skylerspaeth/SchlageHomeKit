# Builtins
import logging, os

# HAP-python
from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_DOOR_LOCK

# Pyschlage
from pyschlage import Auth, Schlage

# Read Schlage creds from environment variables
if None in [os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')]:
    raise ValueError("Missing env var SCHLAGE_USER or SCHLAGE_PASS.")

# Create a Schlage object and authenticate with your credentials.
schlage = Schlage(Auth(os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')))

# Define logging style
logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")

class SchlageLock(Accessory):
    """Door lock from user's Schlage account"""

    category = CATEGORY_DOOR_LOCK

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lock_mechanism = self.add_preload_service("LockMechanism")
        self.lock_target_state = self.lock_mechanism.get_characteristic("LockTargetState")
        self.lock_current_state = self.lock_mechanism.get_characteristic("LockCurrentState")

        self.lock_target_state.setter_callback = self.lock_changed

    def lock_changed(self, value):
        """Callback for when HomeKit requests lock state to change"""

        if value == 0:
            print("Unlocking the door...")
        else:
            print("Locking the door...")

        # Update the current state to reflect the change
        self.lock_current_state.set_value(value)

def get_bridge(driver):
    """Generate a bridge which adds all detected locks"""

    bridge = Bridge(driver, 'Schlage Locks Bridge')

    # Add a lock to bridge for each one found in user's Schlage account
    for lock in schlage.locks():
        new_lock = SchlageLock(driver, lock.name)
        bridge.add_accessory(new_lock)

    return bridge

# Setup the accessory on port 51826
driver = AccessoryDriver(port=51826)

# Add the bridge to list of accessories to broadcast
driver.add_accessory(accessory=get_bridge(driver))

# Start it!
driver.start()
