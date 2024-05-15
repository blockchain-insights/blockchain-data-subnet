from loguru import logger
import json
import sys

neuron_config = {}
logger.remove(0)

def serialize(record):
    if(neuron_config.get('uid') == None):
        return ''
    tmstamp = format(record['time'], "%Y-%m-%d %H:%M:%S.%03d")
    subset = {
        'timestamp': tmstamp, 
        'level': record['level'].name,
        'message': record['message'],
        **neuron_config, 
        **record['extra']
    }
    return json.dumps(subset)

def patching(record):
    record['extra']['serialized'] = serialize(record)
    
logger = logger.patch(patching)
logger.add(sys.stderr, format="{extra[serialized]}")