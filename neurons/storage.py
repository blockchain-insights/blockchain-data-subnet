from typing import Optional, List

import insights

import bittensor as bt
from bittensor.extrinsics import serving
from pydantic import BaseModel
from protocols.blockchain import get_network_id
from neurons import logger

class Metadata(BaseModel):
    def to_compact(self):
        return ','.join(f"{key}:{repr(getattr(self, key))}" for key in self.__dict__)

class MinerMetadata(Metadata):
    sb: Optional[int] #start_block_height
    lb: Optional[int] #end_block_height
    bl: Optional[int] #balance_model_last_block_height
    n: Optional[int] #network
    cv: Optional[str] #code_version
    lv: Optional[str] #lllm engine version
    
    @staticmethod
    def from_compact(compact_str):
        data_dict = {}
        for item in compact_str.split(','):
            key, value = item.split(':', 1)
            data_dict[key] = value.strip("'")
        return MinerMetadata(**data_dict)

class ValidatorMetadata(Metadata):
    cv: Optional[str] #code_version
    ip: Optional[str] #api_ip


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


def store_miner_metadata(self):
    try:
        discovery = self.llm.discovery_v1(network=self.config.network)

        start_block = discovery['funds_flow_model_start_block']
        last_block = discovery['funds_flow_model_ast_block']
        balance_model_last_block = discovery['balance_model_last_block']
        llm_version = discovery['llm_engine_version']

        logger.info(f"Storing miner metadata")

        metadata = MinerMetadata(
            sb=start_block,
            lb=last_block,
            bl=balance_model_last_block,
            n=get_network_id(self.config.network),
            cv=insights.__version__,
            lv=llm_version
        )
        self.subtensor.commit(self.wallet, self.config.netuid, Metadata.to_compact(metadata))
        logger.success(f"Stored miner metadata: {metadata}")
        
    except bt.errors.MetadataError as e:
        logger.warning("Skipping storing miner metadata", error={'exception_type': e.__class__.__name__, 'exception_message': str(e), 'exception_args': e.args})
    except Exception as e:
        logger.warning(f"Skipping storing miner metadata", error={'exception_type': e.__class__.__name__, 'exception_message': str(e), 'exception_args': e.args})

def store_validator_metadata(self):
    def get_commitment(netuid: int, uid: int, block: Optional[int] = None) -> str:
        metadata = serving.get_metadata(subtensor, netuid, hotkey, block)
        if metadata is None:
            return None
        commitment = metadata["info"]["fields"][0]
        hex_data = commitment[list(commitment.keys())[0]][2:]
        return bytes.fromhex(hex_data).decode()
    
    try:
        subtensor = bt.subtensor(config=self.config)
        logger.info(f"Storing validator metadata")
        metadata =  ValidatorMetadata(
            ip=self.metagraph.axons[self.uid].ip,
            cv=insights.__version__,
        )

        hotkey= self.wallet.hotkey.ss58_address
        subtensor.get_commitment = get_commitment

        existing_commitment = subtensor.get_commitment(self.config.netuid, self.uid)
        if existing_commitment is not None:
            try:
                dual_miner = MinerMetadata.from_compact(existing_commitment)
                if dual_miner.sb is not None:
                    logger.info("Skipping storing validator metadata, as this is a dual hotkey for miner and validator", metadata = metadata.to_compact())
                    return
            except Exception as e:
                logger.warning("Error while getting miner metadata, Continuing as validator...", miner_hotkey=hotkey)

        subtensor.commit(self.wallet, self.config.netuid, metadata.to_compact())
        logger.success("Stored validator metadata", metadata = metadata.to_compact())
    except bt.errors.MetadataError as e:
        logger.warning("Skipping storing validator metadata", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
    except Exception as e:
        logger.warning(f"Skipping storing validator metadata,", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})

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
            except Exception as e:
                logger.warning("Error while getting miner metadata, Skipping...", miner_hotkey = hotkey)
                continue

    return miners_metadata