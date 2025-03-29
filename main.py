# Builtins
import logging, os, time

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

# Max number of seconds to wait for lock to perform an update
lock_timeout = 20

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

        # Lock mechanism
        self.lock_service = self.add_preload_service("LockMechanism")

        self.lock_target_state = self.lock_service.get_characteristic("LockTargetState")
        self.lock_current_state = self.lock_service.get_characteristic("LockCurrentState")

        self.lock_target_state.setter_callback = self.handle_state_update
        self.lock_current_state.getter_callback = self.get_actual_state

        # Battery
        self.battery_service = self.add_preload_service("BatteryService")

        self.battery_level = self.battery_service.get_characteristic("BatteryLevel")
        self.battery_status = self.battery_service.get_characteristic("StatusLowBattery")

        self.battery_level.getter_callback = self.get_battery_level
        self.battery_status.getter_callback = self.get_battery_status

    def handle_state_update(self, value):
        """Callback for when HomeKit requests lock state to change"""

        lock = get_lock_by_uuid(self.lock_uuid)

        if value == 0:
            print("Unlocking the door...")
            lock.unlock()
            print("Request finished, re-quering state")
        else:
            print("Locking the door...")
            lock.lock()
            print("Request finished, re-quering state")

        # Wait lock_timeout seconds for state to be as desired otherwise assume request won't be processed
        timeout_end_time = time.time() + lock_timeout
        while True:
            time.sleep(2) # Re-check state every 2 seconds

            lock = get_lock_by_uuid(self.lock_uuid)
            state = 1 if lock.is_locked else 0

            if state == value:
                # Update the current state to reflect the change
                self.lock_current_state.set_value(state)
                print("Updated the state successfully.")
                break
            if time.time() > timeout_end_time:
                print(f"WARNING: Waited {lock_timeout} seconds for lock to change state but no change was observed. Skipping request...")
                break
            print("Trying again...")

    def get_actual_state(self):
        """Callback for when HomeKit queries current, real-life lock state"""

        print("HomeKit queried us for state...")
        return 1 if get_lock_by_uuid(self.lock_uuid).is_locked else 0

    def get_battery_level(self):
        """Callback for when HomeKit queries current battery state"""

        return get_lock_by_uuid(self.lock_uuid).battery_level

    def get_battery_status(self):
        """Callback to check battery status (1 = low, 0 = normal)"""
        return get_lock_by_uuid(self.lock_uuid).battery_level
        return 1 if get_lock_by_uuid(self.lock_uuid).battery_level < 25 else 0


def get_lock_by_uuid(uuid):
    # Lookup lock by caller's UUID
    for lock in schlage.locks():
        if lock.device_id == uuid:
            return lock
        else:
            raise ValueError(f"No lock found matching UUID {lock.device_id}, aborting!")

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
