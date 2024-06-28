from typing import Optional

import insights

from neurons import logger
import bittensor as bt
from bittensor.extrinsics import serving
from pydantic import BaseModel
from insights.protocol import get_network_id, get_model_id, VERSION
from neurons.docker_utils import get_docker_image_version

class Metadata(BaseModel):
    def to_compact(self):
        return ','.join(f"{key}:{repr(getattr(self, key))}" for key in self.__dict__)

class MinerMetadata(Metadata):
    sb: Optional[int] #start_block_height
    lb: Optional[int] #end_block_height
    n: Optional[int] #network
    mt: Optional[int] #model_type
    cv: Optional[str] #code_version
    
    @staticmethod
    def from_compact(compact_str):
        data_dict = {}
        for item in compact_str.split(','):
            key, value = item.split(':', 1)
            data_dict[key] = value.strip("'")
        return MinerMetadata(**data_dict)

class ValidatorMetadata(Metadata):
    b: int
    v: Optional[int]
    di: str
    cv: Optional[str] #code_version

    @staticmethod
    def from_compact(compact_str):
        data_dict = {}
        for item in compact_str.split(','):
            key, value = item.split(':', 1)
            data_dict[key] = value.strip("'")
        return ValidatorMetadata(**data_dict)

def get_commitment_wrapper(subtensor, netuid, _, hotkey, block=None):
    def get_commitment():
        metadata = serving.get_metadata(subtensor, netuid, hotkey, block)
        if metadata is None:
            return None
        commitment = metadata["info"]["fields"][0]
        hex_data = commitment[list(commitment.keys())[0]][2:]
        return bytes.fromhex(hex_data).decode()

    return get_commitment()

def store_miner_metadata(config, graph_search, wallet, start_block, last_block):
    def get_metadata():
        return MinerMetadata(
            sb=start_block,
            lb=last_block,
            n=get_network_id(config.network),
            mt=get_model_id(config.model_type),
            cv=insights.__version__
        )

    try:
        subtensor = bt.subtensor(config=config)
        logger.info("Storing miner metadata")
        metadata = get_metadata()
        subtensor.commit(wallet, config.netuid, Metadata.to_compact(metadata))
        logger.success("Stored miner metadata", metadata = metadata.to_compact())
        
    except bt.errors.MetadataError as e:
        logger.warning("Skipping storing miner metadata", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
    except Exception as e:
        logger.warning(f"Skipping storing miner metadata", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})

def store_validator_metadata(config, wallet, uid):
    def get_commitment(netuid: int, uid: int, block: Optional[int] = None) -> str:
        metadata = serving.get_metadata(subtensor, netuid, hotkey, block)
        if metadata is None:
            return None
        commitment = metadata["info"]["fields"][0]
        hex_data = commitment[list(commitment.keys())[0]][2:]
        return bytes.fromhex(hex_data).decode()
    
    try:
        subtensor = bt.subtensor(config=config)
        logger.info("Storing validator metadata")

        docker_image = get_docker_image_version()
        metadata = ValidatorMetadata(
            b=subtensor.block,
            di=docker_image,
            cv=insights.__version__
        )

        hotkey= wallet.hotkey.ss58_address


        subtensor.get_commitment = get_commitment

        existing_commitment = subtensor.get_commitment(config.netuid, uid)
        if existing_commitment is not None:
            dual_miner = MinerMetadata.from_compact(existing_commitment)
            if dual_miner.sb is not None:
                logger.info("Skipping storing validator metadata, as this is a dual hotkey for miner and validator", metadata = metadata.to_compact())
                return

        subtensor.commit(wallet, config.netuid, metadata.to_compact())
        logger.success("Stored validator metadata", metadata = metadata.to_compact())
    except bt.errors.MetadataError as e:
        logger.warning("Skipping storing validator metadata", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
    except Exception as e:
        logger.warning("Skipping storing validator metadata", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})

def get_miners_metadata(config, metagraph):
    def get_commitment(netuid: int, uid: int, block: Optional[int] = None) -> str:
        metadata = serving.get_metadata(subtensor, netuid, hotkey, block)
        if metadata is None:
            return None
        commitment = metadata["info"]["fields"][0]
        hex_data = commitment[list(commitment.keys())[0]][2:]
        return bytes.fromhex(hex_data).decode()

    subtensor = bt.subtensor(config=config)
    subtensor.get_commitment = get_commitment
    miners_metadata = {}
    
    logger.info("Getting miners metadata")
    for axon in metagraph.axons:
        if axon.is_serving:
            hotkey = axon.hotkey
            try:
                metadata_str = subtensor.get_commitment(config.netuid, 0)
                if metadata_str is None:
                    continue
                metadata = MinerMetadata.from_compact(metadata_str)
                miners_metadata[hotkey] = metadata
            except:
                logger.warning("Error while getting miner metadata, Skipping...", miner_hotkey = hotkey)
                continue

    return miners_metadata