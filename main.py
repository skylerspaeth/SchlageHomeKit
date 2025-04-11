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

# Max number of seconds to wait for lock to perform an update
lock_timeout = 8

# Percentage at which the battery is considered "low" and HomeKit will be notified
low_battery_percent = 25

# Define global logging style
logging.basicConfig(level=logging.INFO, format="[%(module)s] %(message)s")

# Create a logger specific to this file
logger = logging.getLogger(__name__)

# Set a more conservative logger level for this file to prevent excess noise
logger.setLevel(logging.WARNING)

def main():
    # Create a Schlage object and authenticate with supplied creds
    schlage = Schlage(Auth(os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')))

    class SchlageLock(Accessory):
        """Door lock from user's Schlage account"""

        category = CATEGORY_DOOR_LOCK

        def __init__(self, *args, **kwargs):
            # Used to look up matching lock in API when a HomeKit request comes in
            self.lock_uuid = kwargs['uuid']

            # Args unexpected to HAP-python must be removed before calling super init
            del kwargs['uuid']

            super().__init__(*args, **kwargs)

            # Initialize the lock with its real life state
            lock_state_at_startup = self.get_actual_state()
            self._lock_target_state = lock_state_at_startup
            self._lock_current_state = lock_state_at_startup

            # Create the services to register characteristics onto
            self.lock_service = self.add_preload_service("LockMechanism")
            self.battery_service = self.add_preload_service("BatteryService")

            # Configure how we'll interact with characteristics
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
            self.battery_level = self.battery_service.configure_char(
                "BatteryLevel",
                getter_callback=lambda: get_lock_by_uuid(self.lock_uuid).battery_level
            )
            self.battery_status = self.battery_service.configure_char(
                "StatusLowBattery",
                getter_callback=lambda: 1 if get_lock_by_uuid(self.lock_uuid).battery_level < low_battery_percent else 0
            )

        def add_info_service(self):
            """Callback for when HomeKit requests lock accessory information"""

            serv_info = self.driver.loader.get_service("AccessoryInformation")
            serv_info.configure_char("Name", value=self.display_name)
            serv_info.configure_char("Manufacturer", value="Schlage")
            serv_info.configure_char("Model", value="Wi-Fi Lock")
            serv_info.configure_char("SerialNumber", value=self.lock_uuid)
            self.add_service(serv_info)

        def handle_state_update(self, desired_state):
            """Callback for when HomeKit requests lock state to change"""

            # Ack to prevent timeout
            self._lock_target_state = desired_state
            self.lock_target_state.set_value(self._lock_target_state)

            lock = get_lock_by_uuid(self.lock_uuid)

            if desired_state == 0:
                logger.info(f"Unlocking '{lock.name}'...")
                lock.unlock()
            else:
                logger.info(f"Locking '{lock.name}'...")
                lock.lock()

            # Wait lock_timeout seconds for state to be as desired otherwise assume request won't be processed
            timeout_end_time = time.time() + lock_timeout
            while time.time() < timeout_end_time:
                # I'd like to just call get_actual_state here, but it hangs during un/lock if I do for some reason
                lock = get_lock_by_uuid(self.lock_uuid)
                current_state = 2 if lock.is_jammed else int(lock.is_locked)

                logger.info(f"'{lock.name}' Current state: {current_state}, Target state: {desired_state}")

                if current_state == desired_state:
                    # Update the current state to reflect the change
                    self.lock_current_state.set_value(current_state)
                    logger.info(f"Updated state of '{lock.name}' to {desired_state} successfully.")
                    return

                time.sleep(1) # Re-check state every second

            logger.warning(
                f"WARNING: Waited {lock_timeout} seconds for lock to change state but no change was observed. " +
                "Telling HomeKit to display our desired state anyways or else it will hang..."
            )
            self._lock_current_state = desired_state
            self.lock_current_state.set_value(self._lock_current_state)

        def get_actual_state(self):
            """Callback for when HomeKit queries current, real-life lock state"""

            lock = get_lock_by_uuid(self.lock_uuid)

            # 0: door unlocked (unsecured)
            # 1: door locked   (secured)
            # 2: lock jammed   (bruh)
            state = 2 if lock.is_jammed else int(lock.is_locked)

            logger.info(f"Current state according to Schlage: {state}")
            return state

        def get_battery_level(self):
            """Callback for when HomeKit queries current battery state"""

            return get_lock_by_uuid(self.lock_uuid).battery_level

        def get_battery_status(self):
            """Callback to check battery status (1 = low, 0 = normal)"""

            return 1 if get_lock_by_uuid(self.lock_uuid).battery_level < low_battery_percent else 0

        @Accessory.run_at_interval(5)
        def run(self):
            """Poll physical status on a regular basis"""

            current_state = self.get_actual_state()

            # Avoids making unnecessary calls, but can be removed if causing issues
            if current_state != self._lock_current_state:

                # Update target state despite this being a reaction to physical change
                # because without this, Home app will infinitely show "(un)locking..."
                self._lock_target_state = current_state
                self.lock_target_state.set_value(self._lock_target_state)

                # Alert HomeKit that the state has changed
                self._lock_current_state = current_state
                self.lock_current_state.set_value(self._lock_current_state)


    def get_lock_by_uuid(uuid):
        """Lookup lock by UUID of caller SchlageLock instance"""

        for lock in schlage.locks():
            if lock.device_id == uuid:
                return lock
            else:
                raise ValueError(f"No lock found matching UUID {lock.device_id}, aborting!")

    def get_bridge(driver):
        """Generate a bridge which adds all detected locks"""

        bridge = Bridge(driver, 'Schlage Locks Bridge')

        # Add a SchlageLock to bridge for each lock found in user's Schlage account
        for lock in schlage.locks():
            new_lock = SchlageLock(driver, lock.name, uuid=lock.device_id)
            bridge.add_accessory(new_lock)

        return bridge

    # Setup the accessory on default port
    driver = AccessoryDriver(port=51826)

    # Add the bridge to list of accessories to broadcast
    driver.add_accessory(accessory=get_bridge(driver))

    # Start it!
    driver.start()

if __name__ == '__main__':
    main()
