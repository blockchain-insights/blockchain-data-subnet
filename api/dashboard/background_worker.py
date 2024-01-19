import os

import schedule
import time
import bittensor as bt
from infrastructure.database import get_hotkey_collection
from infrastructure.models import Hotkey, HotkeyType
from neurons.storage import get_miners_metadata, get_validator_metadata
from neurons.validators.validator import get_config

def background_task():
    config = get_config()

    if os.getenv("API_TEST_MODE") == "True":
        # Local development settings
        config.subtensor.network = 'test'
        config.subtensor.chain_endpoint = None
        config.wallet.hotkey = 'default'
        config.wallet.name = 'validator'
        config.netuid = 59

        # set environment variables
        os.environ['GRAPH_DB_URL'] = 'bolt://localhost:7687'
        os.environ['GRAPH_DB_USER'] = 'user'
        os.environ['GRAPH_DB_PASSWORD'] = 'pwd'

    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    metagraph.sync(subtensor=subtensor)
    bt.logging.info("metagraph sync complete", config.netuid)
    min_stake_for_validator = 20000  # Minimum stake for a neuron to be considered a validator

    # Extract miner and validator hotkeys
    miner_hotkeys = [neuron.hotkey for neuron in metagraph.neurons
                     if neuron.axon_info.ip != '0.0.0.0' and neuron.stake < min_stake_for_validator]
    validator_hotkeys = [neuron.hotkey for neuron in metagraph.neurons
                         if neuron.axon_info.ip == '0.0.0.0' or neuron.stake >= min_stake_for_validator]
    bt.logging.info(miner_hotkeys)
    bt.logging.info(validator_hotkeys)
    # Get miner and validator metadata
    miners_metadata = get_miners_metadata(config, subtensor, metagraph)
    validators_metadata = get_validator_metadata(config, subtensor, metagraph)
    # Map hotkeys to their metadata and type
    hotkeys_with_metadata = []

    for hotkey in miner_hotkeys:
        metadata = miners_metadata.get(hotkey)
        # If metadata is not found, it will be None (which will become null in MongoDB)
        metadata_str = str(metadata) if metadata is not None else None
        hotkeys_with_metadata.append(
            Hotkey(hotkey=hotkey, hotkeyMetadata=metadata_str, hotkeyType=HotkeyType.MINER.value))

    for hotkey in validator_hotkeys:
        metadata = validators_metadata.get(hotkey)
        # If metadata is not found, it will be None (which will become null in MongoDB)
        metadata_str = str(metadata) if metadata is not None else None
        hotkeys_with_metadata.append(
            Hotkey(hotkey=hotkey, hotkeyMetadata=metadata_str, hotkeyType=HotkeyType.VALIDATOR.value))
    # Store the data in MongoDB
    dump_hotkeys_to_mongo(hotkeys_with_metadata)
    bt.logging.info("hotkeys dumped to the db")


def dump_hotkeys_to_mongo(hotkey_list):
    try:
        hotkeys_collection = get_hotkey_collection()

        # Clear existing hotkeys
        delete_result = hotkeys_collection.delete_many({})
        bt.logging.info(f"Deleted {delete_result.deleted_count} old hotkeys.")

        # Prepare new hotkeys for insertion
        hotkeys_to_insert = [hotkey.dict() for hotkey in hotkey_list]

        # Add new hotkeys to the collection
        if hotkeys_to_insert:
            insert_result = hotkeys_collection.insert_many(hotkeys_to_insert)
            bt.logging.info(f"Inserted {len(insert_result.inserted_ids)} new hotkeys.")
    except Exception as e:
        bt.logging.info(f"An error occurred: {e}")
def run_scheduler():
    # Schedule your task (e.g., every 10 minutes)
    schedule.every(1).minutes.do(background_task)

    while True:
        schedule.run_pending()
        time.sleep(1)