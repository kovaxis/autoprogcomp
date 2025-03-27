import time
from datetime import datetime, timedelta

from app import main
from app.settings import config


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
        print(f"sleeping for {to_sleep} seconds")
        time.sleep(to_sleep)
        now = datetime.now()


def recurrent():
    while True:
        wait_until_next_run()
        print("updating spreadsheet...")
        main.main()


if __name__ == "__main__":
    recurrent()
