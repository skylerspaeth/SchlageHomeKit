# Python built-ins
import functools, logging, time
log = logging.getLogger()

# HAP-python
from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_DOOR_LOCK
from service import Service

# Max number of seconds after requesting change to allow for bolt to finish rotating
lock_timeout = 10

class Lock(Accessory):
    category = CATEGORY_DOOR_LOCK

    def __init__(self, *args, service: Service, schlage_auth, lock_state_at_startup, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_client_public_keys = None

        self._lock_target_state = lock_state_at_startup
        self._lock_current_state = lock_state_at_startup

        self.schlage_auth = schlage_auth
        self.service = service
        self.add_lock_service()
        self.add_unpair_hook()

        self.lock_target_state.set_value(lock_state_at_startup)

    def add_unpair_hook(self):
        unpair = self.driver.unpair

        @functools.wraps(unpair)
        def patched_unpair(client_uuid):
            unpair(client_uuid)
            self.on_unpair(client_uuid)

        self.driver.unpair = patched_unpair

    def add_preload_service(self, service, chars=None, unique_id=None):
        """Create a service with the given name and add it to this acc."""
        if isinstance(service, str):
            service = self.driver.loader.get_service(service)
        if unique_id is not None:
            service.unique_id = unique_id
        if chars:
            chars = chars if isinstance(chars, list) else [chars]
            for char_name in chars:
                if isinstance(char_name, str):
                    char = self.driver.loader.get_char(char_name)
                    service.add_characteristic(char)
                else:
                    service.add_characteristic(char_name)
        self.add_service(service)
        return service

    def add_info_service(self):
        serv_info = self.driver.loader.get_service("AccessoryInformation")
        serv_info.configure_char("Name", value=self.display_name)
        serv_info.configure_char("Manufacturer", value="Schlage")
        serv_info.configure_char("Model", value="Wi-Fi Lock")
        serv_info.configure_char("SerialNumber", value="1234")
        self.add_service(serv_info)

    def add_lock_service(self):
        self.service_lock_mechanism = self.add_preload_service("LockMechanism")

        self.lock_current_state = self.service_lock_mechanism.configure_char(
            "LockCurrentState", getter_callback=self.get_lock_current_state, value=0
        )

        self.lock_target_state = self.service_lock_mechanism.configure_char(
            "LockTargetState",
            getter_callback=self.get_lock_target_state,
            setter_callback=self.set_lock_target_state,
            value=0,
        )

    def _update_hap_pairings(self):
        client_public_keys = set(self.clients.values())
        if self._last_client_public_keys == client_public_keys:
            return
        self._last_client_public_keys = client_public_keys
        self.service.update_hap_pairings(client_public_keys)

    def get_realtime_state_from_schlage(self):
        lock = self.schlage_auth.locks()[0]

        # 0: door unlocked (unsecured)
        # 1: door locked   (secured)
        # 2: lock jammed   (bruh)
        state = 2 if lock.is_jammed else int(lock.is_locked)
        print(f"current state according to schlage: {state}")

        return state

    def get_lock_current_state(self):
        log.info("get_lock_current_state")

        return self.get_realtime_state_from_schlage()

    def get_lock_target_state(self):
        log.info("get_lock_target_state")
        return self._lock_target_state

    def set_lock_target_state(self, value):
        log.info(f"set_lock_target_state {value}")

        # What our desired state is
        self._lock_target_state = value
        self.lock_target_state.set_value(value)

        # Try setting the physical lock
        lock = self.schlage_auth.locks()[0]
        lock.lock() if bool(value) else lock.unlock()

        # Wait lock_timeout seconds for state to be as desired otherwise assume request won't be processed
        timeout_end_time = time.time() + lock_timeout
        while time.time() < timeout_end_time:
            self._lock_current_state = self.get_realtime_state_from_schlage()
            
            # If a jam is detected
            if self._lock_current_state == 2:
                return self._lock_current_state

            # If the locks current state reflects desired
            if self._lock_current_state == value:
                # Update the HomeKit state to reflect the change
                print("Action completed, updating HomeKit value...")
                self.lock_current_state.set_value(self._lock_current_state, should_notify=True)

                print("Updated the state successfully.")
                return self._lock_current_state

            time.sleep(2) # Re-check state every 2 seconds

        # If timeout is reached and lock still doesn't reflect desired state, set to whatever the current state is
        print(f"WARNING: Waited {lock_timeout} seconds for lock to change state but no change was observed. Skipping request...")
        self.lock_current_state.set_value(self._lock_current_state, should_notify=True)

        return self._lock_target_state

    # All methods below are forwarded to Service because they aren't specific to this accessory
    def get_configuration_state(self):
        self._update_hap_pairings()
        log.info("get_configuration_state")
        return self.service.get_configuration_state()

    @property
    def clients(self):
        return self.driver.state.paired_clients

    def on_unpair(self, client_id):
        log.info(f"on_unpair {client_id}")
        self._update_hap_pairings()
