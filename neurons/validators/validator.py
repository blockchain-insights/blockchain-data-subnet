# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 aph5nt
import concurrent
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import time
import argparse
import traceback

import torch
import bittensor as bt
import os
import yaml

import insights
from insights.protocol import Discovery, DiscoveryOutput, MAX_MINER_INSTANCE

from neurons.remote_config import ValidatorConfig
from neurons.nodes.factory import NodeFactory
from neurons.storage import store_validator_metadata
from neurons.validators.benchmark import BenchmarkValidator
from neurons.validators.scoring import Scorer
from neurons.validators.uptime import MinerUptimeManager
from neurons.validators.utils.metadata import Metadata
from neurons.validators.utils.ping import ping
from neurons.validators.utils.synapse import is_discovery_response_valid
from neurons.validators.utils.uids import get_uids_batch
from template.base.validator import BaseValidatorNeuron

from neurons.loguru_logger import logger

class Validator(BaseValidatorNeuron):

    @staticmethod
    def get_config():

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--alpha", default=0.9, type=float, help="The weight moving average scoring.py."
        )

        parser.add_argument("--netuid", type=int, default=15, help="The chain subnet uid.")
        parser.add_argument("--dev", action=argparse.BooleanOptionalAction)

        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)

        config = bt.config(parser)
        config.db_connection_string = os.environ.get('DB_CONNECTION_STRING', '')

        dev = config.dev
        if dev:
            dev_config_path = "validator.yml"
            if os.path.exists(dev_config_path):
                with open(dev_config_path, 'r') as f:
                    dev_config = yaml.safe_load(f.read())
                config.update(dev_config)
                bt.logging.info(f"config updated with {dev_config_path}")
                logger.info('config updated', dev_config_path=f"{dev_config_path}")

            else:
                with open(dev_config_path, 'w') as f:
                    yaml.safe_dump(config, f)
                bt.logging.info(f"config stored in {dev_config_path}")
                logger.info('config stored', dev_config_path=f"{dev_config_path}")

        return config

    def __init__(self, config=None):
        config=Validator.get_config()
        self.validator_config = ValidatorConfig().load_and_get_config_values()
        networks = self.validator_config.get_networks()
        self.nodes = {network : NodeFactory.create_node(network) for network in networks}
        self.block_height_cache = {network: self.nodes[network].get_current_block_height() for network in networks}
        super(Validator, self).__init__(config)
        self.sync_validator()
        self.uid_batch_generator = get_uids_batch(self, self.config.neuron.sample_size)
        self.miner_uptime_manager = MinerUptimeManager(db_url=self.config.db_connection_string)
        self.benchmark_validator = BenchmarkValidator(self.dendrite, self.validator_config)
        
    def cross_validate(self, axon, node, start_block_height, last_block_height):
        try:
            challenge, expected_response = node.create_challenge(start_block_height, last_block_height)
            
            response = self.dendrite.query(
                axon,
                challenge,
                deserialize=False,
                timeout=self.validator_config.challenge_timeout,
            )

            hotkey = response.axon.hotkey

            response_time = response.dendrite.process_time
            bt.logging.info(f"({hotkey=}) Cross validation response time: {response_time}, status_code: {response.axon.status_code}")
            logger.info("Cross validation succeded", miner_hotkey=f"{hotkey}", cross_validation_response_time=f"{response_time}", status_code=f"{response.axon.status_code}")

            if response is not None and response.output is None:
                bt.logging.debug(f"({hotkey=}) Cross validation failed")
                logger.debug("Cross validation failed", miner_hotkey=f"{hotkey}")
                return False, 128

            if response is None or response.output is None:
                bt.logging.debug("Cross validation failed")
                logger.debug("Cross validation failed")
                return False, 128

            # if the miner's response is different from the expected response and validation failed
            if not response.output == expected_response and not node.validate_challenge_response_output(challenge, response.output):
                bt.logging.debug(f"({hotkey=}) Cross validation failed: {response.output=}, {expected_response=}")
                logger.debug("Cross validation failed", miner_hotkey=f"{hotkey}", output=f"{response.output}", expected_response=f"{expected_response}")
                return False, response_time

            bt.logging.info(f"({hotkey=}) Cross validation passed: {response.output=}, {expected_response=}")
            logger.info('Cross validation passed', miner_hotkey=f"{hotkey}", output=f"{response.output}", expected_response=f"{expected_response}")
            
            return True, response_time
        except Exception as e:
            bt.logging.error(f"Cross validation error occurred: {e}")
            logger.error(f"Cross validation error occured", error=f"{e}")
            return None, None

    def is_miner_metadata_valid(self, response: Discovery):
        hotkey = response.axon.hotkey
        ip = response.axon.ip
        
        hotkey_meta = self.metadata.get_metadata_for_hotkey(hotkey)

        if not (hotkey_meta and hotkey_meta['network']):
            bt.logging.info(f'({hotkey=}) Validation Failed: unable to retrieve miner metadata')
            logger.info('Validation failed: unable to retrieve miner metadata', miner_hotkey=f"{hotkey}")
            return False

        ip_count = self.metadata.ip_distribution.get(ip, 0)
        coldkey_count = self.metadata.coldkey_distribution.get(hotkey, 0)

        bt.logging.info(f"({hotkey=}) 🔄 Processing response from miner {ip}")
        logger.info('🔄 Processing response from miner', miner_hotkey=f"{hotkey}")
        if ip_count > MAX_MINER_INSTANCE:
            bt.logging.info(f'({hotkey=}) Validation Failed: {ip_count} ips')
            logger.info('Validation Failed', miner_hotkey=f"{hotkey}", ip_count=f"{ip_count}")
            return False
        if coldkey_count > MAX_MINER_INSTANCE:
            bt.logging.info(f'({hotkey=}) Validation Failed: Coldkey has {coldkey_count} hotkeys')
            logger.info('Validation Failed. Coldkey has several hotkeys.', miner_hotkey=f"{hotkey}", coldkey_count=f"{coldkey_count}")
            return False
        
        bt.logging.info(f'({hotkey=}) Hotkey has {ip_count} ip, {coldkey_count} hotkeys for its coldkey')
        logger.info('Hotkey has several IPs, hotkeys for its coldkey', miner_hotkey=f"{hotkey}", ip_count=f"{ip_count}", coldkey_count=f"{coldkey_count}")

        return True
    
    def is_response_status_code_valid(self, response):
            hotkey = response.axon.hotkey
            status_code = response.axon.status_code
            status_message = response.axon.status_message
            if response.is_failure:
                bt.logging.info(f"({hotkey=}) Discovery response: Failure,  returned {status_code=}: {status_message=}")
                logger.info('Discovery response: Failure', miner_hotkey=f"{hotkey}", status_code=f"{status_code}", status_message=f"{status_message}")
            elif response.is_blacklist:
                bt.logging.info(f"({hotkey=}) Discovery response: Blacklist, returned {status_code=}: {status_message=}")
                logger.info("Discovery response: Blacklist", miner_hotkey=f"{hotkey}", status_code=f"{status_code}", status_message=f"{status_message}")
            elif response.is_timeout:
                bt.logging.info(f"({hotkey=}) Discovery response: Timeout")
                logger.info('Discovery response: Timeout', miner_hotkey=f"{hotkey}")
            return status_code == 200

    def is_response_valid(self, response: Discovery):
        if not self.is_response_status_code_valid(response):
            return False
        if not is_discovery_response_valid(response):
            return False
        if not self.is_miner_metadata_valid(response):
            return False
        return True

    def get_reward(self, response: Discovery, uid: int, benchmarks_result):
        try:
            hotkey = response.axon.hotkey
            uid_value = uid.item() if uid.numel() == 1 else int(uid.numpy())

            if not self.is_response_status_code_valid(response):
                score = self.metagraph.T[uid]/4
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.debug(f'({hotkey=}) Discovery Response error, setting score to {score}')
                logger.debug("Discovery Response error, setting score", miner_hotkey=f"{hotkey}", score=f"{score}")
                return score
            if not is_discovery_response_valid(response):
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.debug(f'({hotkey=}) Discovery Response invalid {response}')
                logger.debug('Discovery Response invalid', miner_hotkey=f"{hotkey}", response=f"{response}")
                return 0
            if not self.is_miner_metadata_valid(response):
                self.miner_uptime_manager.down(uid_value, hotkey)
                return 0

            output: DiscoveryOutput = response.output
            network = output.metadata.network
            start_block_height = output.start_block_height
            last_block_height = output.block_height

            if self.block_height_cache[network] - last_block_height < 6:
                bt.logging.info(f"({hotkey=}) Indexed block cannot be higher than current_block - 6")
                logger.info('Indexed block cannot be higher than current_block - 6', miner_hotkey=f"{hotkey}")
                return 0

            result, average_ping_time = ping(response.axon.ip, response.axon.port, attempts=10)
            if not result:
                bt.logging.info(f"({hotkey=}) Ping Test failed, setting score to avg_ping_time=0..")
                logger.info('Pint Test failed, setting score to avg_ping_time=0..', miner_hotkey=f"{hotkey}")
            else:
                bt.logging.info(f"({hotkey=}) Ping Test: average ping time: {average_ping_time} seconds")
                logger.info('Ping Test: average ping time', miner_hotkey=f"{hotkey}", average_ping_time=f"{average_ping_time}")

            cross_validation_result, _ = self.cross_validate(response.axon, self.nodes[network], start_block_height, last_block_height)

            if cross_validation_result is None:
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.debug(f"({hotkey=}) Cross-Validation: Timeout skipping response")
                logger.debug('Cross-validation: Timeout skipping response', miner_hotkey=f"{hotkey}")
                return None
            if not cross_validation_result:
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.info(f"({hotkey=}) Cross-Validation: Test failed")
                logger.info('Cross-Validation: Test failed', miner_hotkey=f"{hotkey}")
                return 0
            bt.logging.info(f"({hotkey=}) Cross-Validation: Test passed")
            logger.info('Cross-Validation: Test passed', miner_hotkey=f"{hotkey}")

            benchmark_result = benchmarks_result.get(uid_value)
            if benchmark_result is None:
                score = self.metagraph.T[uid]/4
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.info(f"({hotkey=}) Benchmark-Validation: Timeout skipping response")
                logger.info("Benchmark-Validation: Timeout skipping response", miner_hotkey=f"{hotkey}")
                return score

            response_time, benchmark_is_valid = benchmark_result
            if not benchmark_is_valid:
                self.miner_uptime_manager.down(uid_value, hotkey)
                bt.logging.info(f"({hotkey=}) Benchmark-Validation: Test failed")
                logger.info("Benchmark-Validation: Test failed", miner_hotkey=f"{hotkey}")
                return 0

            bt.logging.info(f"({hotkey=}) Benchmark-Validation: Test passed")
            logger.info("Benchmark-Validation: Test passed", miner_hotkey=f"{hotkey}")

            response_time = response_time - average_ping_time

            self.miner_uptime_manager.up(uid_value, hotkey)
            uptime_score = self.miner_uptime_manager.get_uptime_scores(hotkey)

            score = self.scorer.calculate_score(
                hotkey,
                network,
                response_time,
                start_block_height,
                last_block_height,
                self.block_height_cache[network],
                self.metadata.network_distribution,
                uptime_score['average'],
                self.metadata.worst_end_block_height,
            )

            return score
        except Exception as e:
            bt.logging.error(f"Error occurred during cross-validation: {traceback.format_exc()}")
            logger.error("Error occurred during cross-validation", error=f"{traceback.format_exc()}")
            return None

    async def forward(self):
        try:
            uids = next(self.uid_batch_generator, None)
            if uids is None:
                self.uid_batch_generator = get_uids_batch(self, self.config.neuron.sample_size)
                uids = next(self.uid_batch_generator, None)

            axons = [self.metagraph.axons[uid] for uid in uids]

            responses = self.dendrite.query(
                axons,
                Discovery(),
                deserialize=True,
                timeout=self.validator_config.discovery_timeout,
            )

            responses_to_benchmark = [(response, uid) for response, uid in zip(responses, uids) if self.is_response_valid(response)]
            benchmarks_result = self.benchmark_validator.run_benchmarks(responses_to_benchmark)

            self.block_height_cache = {network: self.nodes[network].get_current_block_height() for network in self.networks}

            rewards = [
                self.get_reward(response, uid, benchmarks_result) for response, uid in zip(responses, uids)
            ]

            filtered_data = [(reward, uid) for reward, uid in zip(rewards, uids) if reward is not None]

            if filtered_data:
                rewards, uids = zip(*filtered_data)

                rewards = torch.FloatTensor(rewards)
                self.update_scores(rewards, uids)
            else:
                bt.logging.info('Skipping update_scores() as no responses were valid')
                logger.info('Skipping update_scores() as no responses were valid')
        except Exception as e:
            bt.logging.error(f"Error occurred during forward: {traceback.format_exc()}")
            logger.error("Error occurred during forward", error=f"{traceback.format_exc()}")

    def sync_validator(self):
        self.metadata = Metadata.build(self.metagraph, self.config)
        self.validator_config = ValidatorConfig().load_and_get_config_values()
        self.scorer = Scorer(self.validator_config)
        self.networks = self.validator_config.get_networks()
        self.block_height_cache = {network: self.nodes[network].get_current_block_height() for network in self.networks}
        if self.validator_config.version_update is True and self.validator_config.version != insights.__version__:
            exit(3)

    def resync_metagraph(self):
        super(Validator, self).resync_metagraph()
        self.sync_validator()

    def send_metadata(self):
        store_validator_metadata(self.config, self.wallet, self.uid)


if __name__ == "__main__":
    from dotenv import load_dotenv
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    load_dotenv()

    with Validator() as validator:
        while True:
            bt.logging.info("Validator running")
            logger.info("Validator running")
            time.sleep(bt.__blocktime__*10)


