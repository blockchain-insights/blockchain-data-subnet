import json
import sys

import bittensor as bt

mandatory_config = {}

def serialize(record):
    tmstamp = format(record['time'], "%Y-%m-%d %H:%M:%S.%03d")
    subset = {
        'timestamp': tmstamp,
        'level': record['level'].name,
        'message': record['message'],
    }
    subset.update(mandatory_config)
    subset.update(record['extra'])
    return json.dumps(subset)


def patching(record):
    record['message'] = serialize(record)


def custom_log_formatter(record):
    """Custom log formatter"""
    return "{message}\n"
logger = bt.btlogging.logger
logger = logger.patch(patching)
bt.logging.log_formatter = lambda record: ""
logger.add(sys.stdout, format=custom_log_formatter)

