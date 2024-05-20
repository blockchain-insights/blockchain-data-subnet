import argparse
import os
import re
import time
import torch
import typing
import traceback
from random import sample

import yaml

import bittensor as bt

from insights import protocol


# import base miner class which takes care of most of the boilerplate
from template.base.miner import BaseMinerNeuron

from neurons.miners import blacklist
from insights.protocol import MODEL_TYPE_FUNDS_FLOW, NETWORK_BITCOIN, NETWORK_ETHEREUM, QueryOutput
from neurons.storage import store_miner_metadata
from neurons.remote_config import MinerConfig
from neurons.nodes.factory import NodeFactory
from neurons.miners.query import get_graph_search, get_graph_indexer


class Miner(BaseMinerNeuron):
    """
    Your miner neuron class. You should use this class to define your miner's behavior. In particular, you should replace the forward function with your own logic. You may also want to override the blacklist and priority functions according to your needs.

    This class inherits from the BaseMinerNeuron class, which in turn inherits from BaseNeuron. The BaseNeuron class takes care of routine tasks such as setting up wallet, subtensor, metagraph, logging directory, parsing config, etc. You can override any of the methods in BaseNeuron if you need to customize the behavior.

    This class provides reasonable default behavior for a miner such as blacklisting unrecognized hotkeys, prioritizing requests based on stake, and forwarding requests to the forward function. If you need to define custom
    """
    
        
    @staticmethod
    def get_config():

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--network",
            default=NETWORK_BITCOIN,
            help="Set miner's supported blockchain network.",
        )
        parser.add_argument(
            "--model_type",
            type=str,
            default=MODEL_TYPE_FUNDS_FLOW,
            help="Set miner's supported model type.",
        )

        parser.add_argument("--netuid", type=int, default=15, help="The chain subnet uid.")
        parser.add_argument("--dev", action=argparse.BooleanOptionalAction)

        
        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        bt.axon.add_args(parser)

        config = bt.config(parser)
        config.blacklist  = dict(force_validator_permit=True, allow_non_registered=False)
        config.wait_for_sync = os.environ.get('WAIT_FOR_SYNC', 'False')=='True'
        config.graph_db_url = os.environ.get('GRAPH_DB_URL', 'bolt://localhost:7687')
        config.graph_db_user = os.environ.get('GRAPH_DB_USER', 'user')
        config.graph_db_password = os.environ.get('GRAPH_DB_PASSWORD', 'pwd')
        
        dev = config.dev
        if dev:
            dev_config_path = "miner.yml"
            if os.path.exists(dev_config_path):
                with open(dev_config_path, 'r') as f:
                    dev_config = yaml.safe_load(f.read())
                config.update(dev_config)
                #bt.logging.info(f"config updated", config_path = dev_config_path)

            else:
                with open(dev_config_path, 'w') as f:
                    yaml.safe_dump(config, f)
                #bt.logging.info(f"config stored", config_path = dev_config_path)

        return config
    
    def __init__(self, config=None):
        config = Miner.get_config()
        
        super(Miner, self).__init__(config=config)
        
        self.last_weight_update = self.block - 1000
        self.request_timestamps: dict = {}
        
        self.axon = bt.axon(wallet=self.wallet, port=self.config.axon.port)        
        # Attach determiners which functions are called when servicing a request.
        bt.logging.info(f"Attaching forwards functions to miner axon.")
        self.axon.attach(
            forward_fn=self.block_check,
            blacklist_fn=self.block_check_blacklist,
            priority_fn=self.block_check_priority,
        ).attach(
            forward_fn=self.discovery,
            blacklist_fn=self.discovery_blacklist,
            priority_fn=self.discovery_priority,
        ).attach(
            forward_fn=self.challenge,
            blacklist_fn=self.challenge_blacklist,
            priority_fn=self.challenge_priority,
        ).attach(
            forward_fn=self.benchmark,
            blacklist_fn=self.benchmark_blacklist,
            priority_fn=self.benchmark_priority,
        )

        bt.logging.info(f"Axon created", axon = f"{self.axon}")

        self.graph_search = get_graph_search(config)

        self.miner_config = MinerConfig().load_and_get_config_values()        
    
    async def block_check(self, synapse: protocol.BlockCheck) -> protocol.BlockCheck:
        try:
            block_heights = synapse.blocks_to_check
            data_samples = self.graph_search.get_block_transactions(block_heights)
            synapse.output = protocol.BlockCheckOutput(
                data_samples=data_samples,
            )
            bt.logging.info(f"Serving miner random block check output", output = f"{synapse.output}")
        except Exception as e:
            bt.logging.error('error', error = traceback.format_exc())
            synapse.output = None
        return synapse
            
    async def discovery(self, synapse: protocol.Discovery ) -> protocol.Discovery:
        try:
            start_block, last_block = self.graph_search.get_min_max_block_height_cache()
            
            synapse.output = protocol.DiscoveryOutput(
                metadata=protocol.DiscoveryMetadata(
                    network=self.config.network,
                    model_type=self.config.model_type
                ),
                start_block_height=start_block,
                block_height=last_block,
            )
            bt.logging.info("Serving miner discovery output",
                            output = {
                                'metadata' : {
                                    'network' : synapse.output.metadata.network, 
                                    'model_type' : synapse.output.metadata.model_type, 
                                    'graph_schema' : synapse.output.metadata.graph_schema
                                },
                                'block_height' : synapse.output.block_height,
                                'start_block_height' : synapse.output.start_block_height,
                                'run_id' : synapse.output.run_id,
                                'version' : synapse.output.version})
        except Exception as e:
            bt.logging.error('error', error = traceback.format_exc())
            synapse.output = None
        return synapse

    async def challenge(self, synapse: protocol.Challenge ) -> protocol.Challenge:
        try:
            bt.logging.info("challenge recieved", synapse = {'version' : synapse.version, 'in_total_amount' : synapse.in_total_amount, 'out_total_amount' : synapse.out_total_amount, 'tx_id_last_4_chars' : synapse.tx_id_last_4_chars, 'checksum' : synapse.checksum, 'output' : synapse.output})

            if self.config.network == NETWORK_BITCOIN:
                synapse.output = self.graph_search.solve_challenge(
                    in_total_amount=synapse.in_total_amount,
                    out_total_amount=synapse.out_total_amount,
                    tx_id_last_4_chars=synapse.tx_id_last_4_chars
                )
            if self.config.network == NETWORK_ETHEREUM:
                synapse.output = self.graph_search.solve_challenge(
                    checksum=synapse.checksum,
                )

            bt.logging.info(f"Serving miner challenge", output = f"{synapse.output}")

        except Exception as e:
            bt.logging.error('error', error = traceback.format_exc())
            synapse.output = None
        return synapse

    async def benchmark(self, synapse: protocol.Benchmark) -> protocol.Benchmark:
        try:
            bt.logging.info(f"Executing benchmark query", query = synapse.query)
            pattern = self.miner_config.get_benchmark_query_regex(self.config.network)
            regex = re.compile(pattern)
            match = regex.fullmatch(synapse.query)
            if match is None:
                bt.logging.error("Invalid benchmark query", query = synapse.query)
                synapse.output = None
            else:
                result = self.graph_search.execute_benchmark_query(cypher_query=synapse.query)
                synapse.output = result[0]

            bt.logging.info(f"Serving miner benchmark output", output = f"{synapse.output}")
        except Exception as e:
            bt.logging.error('error', error = traceback.format_exc())
        return synapse

    async def block_check_blacklist(self, synapse: protocol.BlockCheck) -> typing.Tuple[bool, str]:
        return blacklist.base_blacklist(self, synapse=synapse)

    async def discovery_blacklist(self, synapse: protocol.Discovery) -> typing.Tuple[bool, str]:
        return blacklist.discovery_blacklist(self, synapse=synapse)

    async def challenge_blacklist(self, synapse: protocol.Challenge) -> typing.Tuple[bool, str]:
        return blacklist.base_blacklist(self, synapse=synapse)

    async def benchmark_blacklist(self, synapse: protocol.Benchmark) -> typing.Tuple[bool, str]:
        return blacklist.base_blacklist(self, synapse=synapse)

    def base_priority(self, synapse: bt.Synapse) -> float:
        caller_uid = self.metagraph.hotkeys.index(
            synapse.dendrite.hotkey
        ) 
        prirority = float(
            self.metagraph.S[caller_uid]
        )
        bt.logging.trace("Prioritizing hotkey", hotkey = synapse.dendrite.hotkey, priority = prirority)
        return prirority
    
    async def block_check_priority(self, synapse: protocol.BlockCheck) -> float:
        return self.base_priority(synapse=synapse)

    async def discovery_priority(self, synapse: protocol.Discovery) -> float:
        return self.base_priority(synapse=synapse)

    async def challenge_priority(self, synapse: protocol.Challenge) -> float:
        return self.base_priority(synapse=synapse)

    async def benchmark_priority(self, synapse: protocol.Benchmark) -> float:
        return self.base_priority(synapse=synapse)

    def resync_metagraph(self):
        self.miner_config = MinerConfig().load_and_get_config_values()
        super(Miner, self).resync_metagraph()
        
    def should_set_weights(self) -> bool:
        
        # Don't set weights on initialization.
        if self.step == 0:
            return False

        # Check if enough epoch blocks have elapsed since the last epoch.
        if self.miner_config.set_weights == False:
            return False

        # Define appropriate logic for when set weights.
        if self.block - self.last_weight_update > self.miner_config.set_weights_frequency:
            self.last_weight_update = self.block
            return True
        return False
    
    def set_weights(self):
        """
        Self-assigns a weight of 1 to the current miner (identified by its UID) and
        a weight of 0 to all other peers in the network. The weights determine the trust level the miner assigns to other nodes on the network.

        Raises:
            Exception: If there's an error while setting weights, the exception is logged for diagnosis.
        """
        try:
            # --- query the chain for the most current number of peers on the network
            chain_weights = torch.zeros(
                self.subtensor.subnetwork_n(netuid=self.metagraph.netuid)
            )
            chain_weights[self.uid] = 1

            # --- Set weights.
            self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.metagraph.netuid,
                uids=torch.arange(0, len(chain_weights)),
                weights=chain_weights.to("cpu"),
                wait_for_inclusion=False,
                version_key=self.spec_version
            )

        except Exception as e:
            bt.logging.error("Failed to set weights on chain", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})

        bt.logging.info(f"Set weights", weights = chain_weights)
    
    def should_send_metadata(self):        
        return (
            self.block - self.last_message_send
        ) > self.miner_config.store_metadata_frequency
    
    def send_metadata(self):
        start_block, last_block = self.graph_search.get_min_max_block_height_cache()
        store_miner_metadata(self.config, self.graph_search, self.wallet, start_block, last_block)

def wait_for_blocks_sync():
        is_synced=False

        config = Miner.get_config()
        if not config.wait_for_sync:
            bt.logging.info(f"Skipping graph sync.")
            return is_synced
        
        miner_config = MinerConfig().load_and_get_config_values()
        delta = miner_config.get_blockchain_sync_delta(config.network)
        bt.logging.info(f"Waiting for graph model to sync with blockchain.")
        while not is_synced:
            try:
                graph_indexer = get_graph_indexer(config)
                node = NodeFactory.create_node(config.network)

                latest_block_height = node.get_current_block_height()
                current_block_height = graph_indexer.get_latest_block_number()
                delta = latest_block_height - current_block_height
                if delta < 100:
                    is_synced = True
                    bt.logging.success(f"Graph model is synced with blockchain.")
                else:
                    bt.logging.info(f"Graph Sync", current_block_height = current_block_height, latest_block_height = latest_block_height)
                    time.sleep(bt.__blocktime__ * 12)
            except Exception as e:
                bt.logging.error('error', error = traceback.format_exc())
                time.sleep(bt.__blocktime__ * 12)
                bt.logging.info(f"Failed to connect with graph database. Retrying...")
                continue
        return is_synced

# This is the main function, which runs the miner.
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    wait_for_blocks_sync()
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running")
            time.sleep(bt.__blocktime__*2)

