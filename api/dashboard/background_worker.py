import schedule
import time
from infrastructure.database import get_hotkey_collection
from infrastructure.models import Hotkey, HotkeyType
from neurons.storage import get_miners_metadata, get_validator_metadata
from neurons.validators.validator import get_config

def background_task(subtensor):
    config = get_config()
    metagraph = subtensor.metagraph(config.netuid)
    metagraph.sync(subtensor=subtensor)

    min_stake_for_validator = 20000  # Minimum stake for a neuron to be considered a validator

    # Extract miner and validator hotkeys
    miner_hotkeys = [neuron.hotkey for neuron in metagraph.neurons
                     if neuron.axon_info.ip != '0.0.0.0' and neuron.stake < min_stake_for_validator]
    validator_hotkeys = [neuron.hotkey for neuron in metagraph.neurons
                         if neuron.axon_info.ip == '0.0.0.0' or neuron.stake >= min_stake_for_validator]

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

def dump_hotkeys_to_mongo(hotkey_list):
    hotkeys_collection = get_hotkey_collection()
    # Clear existing hotkeys
    hotkeys_collection.delete_many({})
    # Prepare new hotkeys for insertion
    hotkeys_to_insert = [hotkey.dict() for hotkey in hotkey_list]
    # Add new hotkeys to the collection
    if hotkeys_to_insert:
        hotkeys_collection.insert_many(hotkeys_to_insert)
def run_scheduler():
    # Schedule your task (e.g., every 10 minutes)
    schedule.every(1).minutes.do(background_task)

    while True:
        schedule.run_pending()
        time.sleep(1)