import logging
import time
from datetime import datetime, timedelta

from app import main as app_main
from app.settings import config

log = logging.getLogger("recurrent")


def wait_until_next_run():
    now = datetime.now()
    future = datetime(now.year, now.month, now.day, config.schedule.hour or 0, config.schedule.minute)
    while now.timestamp() >= future.timestamp():
        if config.schedule.hour is None:
            future += timedelta(hours=1)
        else:
            future += timedelta(days=1)
    while now < future:
        to_sleep = (future - now).total_seconds()
        log.info(f"sleeping for {to_sleep} seconds")
        time.sleep(to_sleep)
        now = datetime.now()


def main():
    app_main.setup_logging()
    while True:
        try:
            app_main.run()
        except Exception:
            log.exception("run failed, skipping this update")
        wait_until_next_run()


if __name__ == "__main__":
    main()
