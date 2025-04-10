# Python built-ins
import json, logging, signal, sys, os

# HAP-python
from pyhap.accessory_driver import AccessoryDriver
from accessory import Lock
from service import Service

# Pyschlage
from pyschlage import Auth, Schlage

# Verify Schlage creds env vars are present
if None in [os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')]:
    raise ValueError("Missing env var SCHLAGE_USER or SCHLAGE_PASS.")

# Create a Schlage object and authenticate with supplied creds
schlage = Schlage(Auth(os.environ.get('SCHLAGE_USER'), os.environ.get('SCHLAGE_PASS')))

def configure_logging():
    log = logging.getLogger()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)8s] %(module)-18s %(message)s")
    hdlr = logging.StreamHandler(sys.stdout)
    log.setLevel(20)
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    return log

def configure_hap_accessory():
    driver = AccessoryDriver(port=51926, persist_file="hap.state")
    accessory = Lock(
        driver,
        "Lock", # used as display_name
        service=Service,
        schlage_auth=schlage,
        lock_state_at_startup=int(schlage.locks()[0].is_locked)
    )
    driver.add_accessory(accessory=accessory)
    return driver, accessory

def main():
    log = configure_logging()

    hap_driver, _ = configure_hap_accessory()
    hap_driver.start()

if __name__ == "__main__":
    main()
