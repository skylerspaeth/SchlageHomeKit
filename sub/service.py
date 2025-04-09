import logging, time, os

log = logging.getLogger()

class Service:
    def __init__(self) -> None:
        pass

    def start(self):
        self._runner = create_runner(
            name="homekey",
            target=self.run,
            flag=attrgetter("_run_flag"),
            delay=0,
            exception_delay=5,
            start=True,
        )

    def stop(self):
        pass

    def run(self):
        pass

    def get_configuration_state(self):
        log.info("get_configuration_state")
        return 0
