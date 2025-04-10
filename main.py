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

        # Used to look up matching lock in API when a HomeKit request comes in
        self.lock_uuid = uuid

        lock_state_at_startup = 1
        self._lock_target_state = lock_state_at_startup
        self._lock_current_state = lock_state_at_startup

        # Lock mechanism
        self.lock_service = self.add_preload_service("LockMechanism")

        self.lock_current_state = self.lock_service.configure_char(
            "LockCurrentState",
            getter_callback=self.get_actual_state,
            value=0
        )

        self.lock_target_state = self.lock_service.configure_char(
            "LockTargetState",
            getter_callback=lambda: self._lock_target_state,
            setter_callback=self.handle_state_update,
            value=0
        )


    def handle_state_update(self, desired_state):
        """Callback for when HomeKit requests lock state to change"""

        # Ack to prevent timeout
        self.lock_target_state.set_value(desired_state)

        lock = get_lock_by_uuid(self.lock_uuid)

        if desired_state == 0:
            print("Unlocking the door...")
            lock.unlock()
        else:
            print("Locking the door...")
            lock.lock()

        # Wait lock_timeout seconds for state to be as desired otherwise assume request won't be processed
        timeout_end_time = time.time() + lock_timeout
        while time.time() < timeout_end_time:
            time.sleep(2) # Re-check state every 2 seconds

            lock = get_lock_by_uuid(self.lock_uuid)
            state = 1 if lock.is_locked else 0

            print(f"Current lock state: {state}, Target state: {desired_state}")

            if state == desired_state:
                # Update the current state to reflect the change
                self.lock_current_state.set_value(state)
                print("Updated the state successfully.")
                return

        print(f"WARNING: Waited {lock_timeout} seconds for lock to change state but no change was observed. Skipping request...")
        self.lock_current_state.set_value(desired_state)

    def get_actual_state(self):
        """Callback for when HomeKit queries current, real-life lock state"""

        return 1 if get_lock_by_uuid(self.lock_uuid).is_locked else 0


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
