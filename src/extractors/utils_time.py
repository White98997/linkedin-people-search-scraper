thonimport random
import time

def get_random_delay(min_delay=1, max_delay=3):
    return random.uniform(min_delay, max_delay)

def sleep_with_random_delay():
    time.sleep(get_random_delay())