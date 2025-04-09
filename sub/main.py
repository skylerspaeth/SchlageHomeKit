import json
import logging
import signal
import sys

from pyhap.accessory_driver import AccessoryDriver

from accessory import Lock
from service import Service

def configure_logging():
    log = logging.getLogger()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)8s] %(module)-18s:%(lineno)-4d %(message)s")
    hdlr = logging.StreamHandler(sys.stdout)
    log.setLevel(20)
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    return log

def configure_hap_accessory():
    driver = AccessoryDriver(port=51926, persist_file="hap.state")
    accessory = Lock(
        driver,
        "Lock",
        service=Service,
        lock_state_at_startup=int(True)
    )
    driver.add_accessory(accessory=accessory)
    return driver, accessory

def main():
    log = configure_logging()

    hap_driver, _ = configure_hap_accessory()
    hap_driver.start()

if __name__ == "__main__":
    main()
