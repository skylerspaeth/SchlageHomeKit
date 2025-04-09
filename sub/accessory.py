import functools
import logging
import time

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_DOOR_LOCK

from service import Service

log = logging.getLogger()

class Lock(Accessory):
    category = CATEGORY_DOOR_LOCK

    def __init__(self, *args, service: Service, schlage_lock, lock_state_at_startup=1, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_client_public_keys = None

        self._lock_target_state = lock_state_at_startup
        self._lock_current_state = lock_state_at_startup

        self.schlage_lock = schlage_lock
        self.service = service
        self.service.on_endpoint_authenticated = self.on_endpoint_authenticated
        self.add_lock_service()
        self.add_unpair_hook()

    def on_endpoint_authenticated(self, endpoint):
        self._lock_target_state = 0 if self._lock_current_state else 1
        log.info(
            f"Toggling lock state due to endpoint authentication event {self._lock_target_state} -> {self._lock_current_state} {endpoint}"
        )
        self.lock_target_state.set_value(self._lock_target_state, should_notify=True)
        self._lock_current_state = self._lock_target_state
        self.lock_current_state.set_value(self._lock_current_state, should_notify=True)

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
        serv_info.configure_char("SerialNumber", value="default")
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

    def get_lock_current_state(self):
        log.info("get_lock_current_state")
        return self.schlage_lock.is_locked
        # return self._lock_current_state

    def get_lock_target_state(self):
        log.info("get_lock_target_state")
        return self._lock_target_state

    def set_lock_target_state(self, value):
        log.info(f"set_lock_target_state {value}")

        self._lock_target_state = value

        # Try setting the physical lock
        self.schlage_lock.lock() if bool(value) else self.schlage_lock.unlock()

        # Wait lock_timeout seconds for state to be as desired otherwise assume request won't be processed
        timeout_end_time = time.time() + 10
        while time.time() < timeout_end_time:
            time.sleep(2) # Re-check state every 2 seconds

            current_state = int(self.schlage_lock.is_locked)

            if current_state == value:
                # Update the current state to reflect the change
                self._lock_current_state = int(self.schlage_lock.is_locked)
                self.lock_current_state.set_value(self._lock_current_state, should_notify=True)
                print(self.schlage_lock.lock_state_metadata)
                print("Updated the state successfully.")
                return self._lock_current_state

        print(f"WARNING: Waited {lock_timeout} seconds for lock to change state but no change was observed. Skipping request...")
        self._lock_current_state = int(self.schlage_lock.is_locked)
        self.lock_current_state.set_value(self._lock_current_state, should_notify=True)

        return self._lock_target_state

    # All methods down here are forwarded to Service
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
