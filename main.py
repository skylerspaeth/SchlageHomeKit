# Builtins
import logging, os

# HAP-python
from pyhap.accessory import Accessory, Bridge
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_DOOR_LOCK

# Pyschlage
from pyschlage import Auth, Schlage

# Verify Schlage creds env vars are present
if None in [os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')]:
    raise ValueError("Missing env var SCHLAGE_USER or SCHLAGE_PASS.")

# Create a Schlage object and authenticate with supplied creds
schlage = Schlage(Auth(os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')))

# Define logging style
logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")

class SchlageLock(Accessory):
    """Door lock from user's Schlage account"""

    category = CATEGORY_DOOR_LOCK

    def __init__(self, *args, **kwargs):
        # Args unexpected to HAP-python must be removed before calling super init
        uuid = kwargs['uuid']
        del kwargs['uuid']

        super().__init__(*args, **kwargs)

        self.lock_uuid = uuid

        self.lock_mechanism = self.add_preload_service("LockMechanism")
        self.lock_target_state = self.lock_mechanism.get_characteristic("LockTargetState")
        self.lock_current_state = self.lock_mechanism.get_characteristic("LockCurrentState")

        self.lock_target_state.setter_callback = self.lock_changed

    def lock_changed(self, value):
        """Callback for when HomeKit requests lock state to change"""

        # Lookup lock by caller's UUID
        for lock in schlage.locks():
            if lock.device_id == self.lock_uuid:
                if value == 0:
                    print("Unlocking the door...")
                    lock.unlock()
                else:
                    print("Locking the door...")
                    lock.lock()

                # Update the current state to reflect the change
                self.lock_current_state.set_value(1 if lock.is_locked else 0)

                break

            else:
                print(f"ERROR: No lock found matching UUID {lock.device_id}, skipping request...")

def get_bridge(driver):
    """Generate a bridge which adds all detected locks"""

    bridge = Bridge(driver, 'Schlage Locks Bridge')

    # Add a lock to bridge for each one found in user's Schlage account
    for lock in schlage.locks():
        new_lock = SchlageLock(driver, lock.name, uuid=lock.device_id)
        bridge.add_accessory(new_lock)

    return bridge

# Setup the accessory on port 51826
driver = AccessoryDriver(port=51826)

# Add the bridge to list of accessories to broadcast
driver.add_accessory(accessory=get_bridge(driver))

# Start it!
driver.start()
