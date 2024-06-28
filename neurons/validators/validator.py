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

from neurons import logger
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
            else:
                with open(dev_config_path, 'w') as f:
                    yaml.safe_dump(config, f)

        return config

    def __init__(self, config=None):
        config=Validator.get_config()
        self.validator_config = ValidatorConfig().load_and_get_config_values()
        networks = self.validator_config.get_networks()
        self.nodes = {network : NodeFactory.create_node(network) for network in networks}
        self.block_height_cache = {network: self.nodes[network].get_current_block_height() for network in networks}
        super(Validator, self).__init__(config)
        self.sync_validator()
        self.uid_batch_generator = get_uids_batch(self, self.validator_config.sample_size)
        self.miner_uptime_manager = MinerUptimeManager(db_url=self.config.db_connection_string)
        self.benchmark_validator = BenchmarkValidator(self.dendrite, self.validator_config)
        
        immunity_period = self.subtensor.immunity_period(self.config.netuid)
        logger.info("Immunity period", immunity_period = immunity_period)
        self.miner_uptime_manager.immunity_period = immunity_period
        
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

            if response is not None and response.output is None:
                logger.info("Cross validation failed", miner_hotkey=hotkey, reason="output", miner_ip = response.axon.ip)
                return False, 128

            if response is None or response.output is None:
                logger.info("Cross validation failed", miner_hotkey=hotkey, reason="empty", miner_ip = response.axon.ip)
                return False, 128

            if not response.output == expected_response and not node.validate_challenge_response_output(challenge, response.output):
                logger.info("Cross validation failed",  miner_hotkey=hotkey, miner_ip = response.axon.ip, reason="expected_response", response_output=response.output, expected_output=expected_response)
                return False, response_time

            logger.info("Cross validation passed", miner_hotkey=hotkey, miner_ip = response.axon.ip)

            return True, response_time
        except Exception as e:
            logger.error(f"Cross validation error occurred", error=traceback.format_exc())
            return None, None

    def is_miner_metadata_valid(self, response: Discovery):
        hotkey = response.axon.hotkey
        ip = response.axon.ip
        
        hotkey_meta = self.metadata.get_metadata_for_hotkey(hotkey)
        if not (hotkey_meta and hotkey_meta['network']):
            logger.info("Validation failed", miner_hotkey=hotkey, reason="metadata_retrival", miner_ip = ip)
            return False

        ip_count = self.metadata.ip_distribution.get(ip, 0)
        coldkey_count = self.metadata.coldkey_distribution.get(hotkey, 0)
        if ip_count > MAX_MINER_INSTANCE:
            logger.info("Validation failed", miner_hotkey=hotkey, reason="ip_count", ip_count=ip_count, miner_ip = ip)
            return False
        if coldkey_count > MAX_MINER_INSTANCE:
            logger.info("Validation failed", miner_hotkey=hotkey, reason="coldkey_count", coldkey_count=coldkey_count, miner_ip = ip)
            return False

        return True
    
    def is_response_status_code_valid(self, response):
        hotkey = response.axon.hotkey
        status_code = response.axon.status_code
        status_message = response.axon.status_message
        if response.is_failure:
            logger.info("Discovery response failure", miner_hotkey=hotkey, reason="failure",  status_message=f"{status_message}", miner_ip = response.axon.ip)
        elif response.is_blacklist:
            logger.info("Discovery response failure", miner_hotkey=hotkey, reason="blacklist", status_message=f"{status_message}", miner_ip = response.axon.ip)
        elif response.is_timeout:
            logger.info("Discovery response failure", miner_hotkey=hotkey, reason="timeout", miner_ip = response.axon.ip)
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
                logger.info("Reward failed", miner_hotkey=hotkey, reason="status_code_invalid", score=float(score), miner_ip = response.axon.ip, miner_uid = uid_value)
                return score
            if not is_discovery_response_valid(response):
                self.miner_uptime_manager.down(uid_value, hotkey)
                logger.info("Reward failed", miner_hotkey=hotkey, reason="invalid_response", score=0, miner_ip = response.axon.ip, miner_uid = uid_value)
                return 0
            if not self.is_miner_metadata_valid(response):
                self.miner_uptime_manager.down(uid_value, hotkey)
                logger.info("Reward failed", miner_hotkey=hotkey, reason="metadata_invalid", score=0, miner_ip = response.axon.ip, miner_uid = uid_value)
                return 0

            output: DiscoveryOutput = response.output
            network = output.metadata.network
            start_block_height = output.start_block_height
            last_block_height = output.block_height

            if self.block_height_cache[network] - last_block_height < 6:
                logger.info("Reward failed", miner_hotkey=hotkey, reason="block_height_invalid", score=0, miner_ip = response.axon.ip, miner_uid = uid_value)
                return 0

            result, average_ping_time = ping(response.axon.ip, response.axon.port, attempts=10)
            if not result:
                logger.info("Ping Test failed", miner_hotkey=hotkey, reason="ping_test_failed", miner_ip = response.axon.ip, miner_uid = uid_value)
            else:
                logger.info("Ping Test passed", miner_hotkey=hotkey, average_ping_time=average_ping_time, miner_ip = response.axon.ip, miner_uid = uid_value)

            cross_validation_result, _ = self.cross_validate(response.axon, self.nodes[network], start_block_height, last_block_height)
            if cross_validation_result is None or not cross_validation_result:
                self.miner_uptime_manager.down(uid_value, hotkey)
                logger.info("Reward failed", miner_hotkey=hotkey, reason="cross_validation_failed", score=0, miner_ip = response.axon.ip, miner_uid = uid_value)
                return 0

            benchmark_result = benchmarks_result.get(uid_value)
            if benchmark_result is None:
                score = self.metagraph.T[uid]/4
                self.miner_uptime_manager.down(uid_value, hotkey)
                logger.info("Reward failed", miner_hotkey=hotkey, reason="benchmark_timeout", score=float(score), miner_ip = response.axon.ip, miner_uid = uid_value)
                return score

            response_time, benchmark_is_valid = benchmark_result
            if not benchmark_is_valid:
                self.miner_uptime_manager.down(uid_value, hotkey)
                logger.info("Reward failed", miner_hotkey=hotkey, reason="benchmark_failed", score=0, miner_ip = response.axon.ip, miner_uid = uid_value)
                return 0

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
            logger.error("Reward failed", miner_hotkey=hotkey, reason="exception", error=traceback.format_exc(), miner_ip = response.axon.ip, miner_uid = uid_value)
            return None
    def calculate_min_max_time(self, benchmarks_result, responses):
        max_time_response = 0
        min_time_response = self.validator_config.benchmark_timeout
        for item, response in zip(benchmarks_result.values(), responses):
            average_ping_time = ping(response.axon.ip, response.axon.port, attempts=10)[1]
            max_time_response = max(max_time_response, item[0] - average_ping_time)
            min_time_response = min(min_time_response, item[0] - average_ping_time)
        if(max_time_response == min_time_response): max_time_response += 0.1
        return min_time_response, max_time_response

    async def forward(self):
        try:
            uids = next(self.uid_batch_generator, None)
            if uids is None:
                self.uid_batch_generator = get_uids_batch(self, self.validator_config.sample_size)
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

            min_time, max_time = self.calculate_min_max_time(benchmarks_result, responses)
            self.scorer.config.min_time = min_time
            self.scorer.config.max_time = max_time

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
                logger.info("Forward failed", reason="no_valid_responses")
        except Exception as e:
            logger.error("Forward failed", reason="exception", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
        finally: pass

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
            logger.info("Validator running")
            time.sleep(bt.__blocktime__*10)


