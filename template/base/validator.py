# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

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


import copy
import time
import numpy as np
import asyncio
import argparse
import threading
import bittensor as bt

from typing import List
from traceback import print_exception

from template.base.neuron import BaseNeuron
from template.base.utils import weight_utils
from template.base.utils.weight_utils import process_weights_for_netuid
from template.mock import MockDendrite
from template.utils.config import add_validator_args

from neurons import logger

class BaseValidatorNeuron(BaseNeuron):
    """
    Base class for Bittensor validators. Your validator should inherit from this class.
    """

    neuron_type: str = "ValidatorNeuron"

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        super().add_args(parser)
        add_validator_args(cls, parser)

    def __init__(self, config=None):
        super().__init__(config=config)
        # Create asyncio event loop to manage async tasks.
        self.loop = asyncio.get_event_loop()

        # Instantiate runners
        self.should_exit: bool = False
        self.is_running: bool = False
        self.thread: threading.Thread = None
        self.lock = threading.RLock()
        # Save a copy of the hotkeys to local memory.
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)

        # Dendrite lets us send messages to other nodes (axons) in the network.
        if self.config.mock:
            self.dendrite = MockDendrite(wallet=self.wallet)
        else:
            self.dendrite = bt.dendrite(wallet=self.wallet)
        logger.info('dendrite', dendrite = f"{self.dendrite}")

        # Set up initial scoring weights for validation
        logger.info("Building validation weights.")
        zeroes = np.zeros_like(self.metagraph.S, dtype = np.float32)
        try:
            self.load_state()
            logger.info("Scores loaded from file")

            # Check if loaded scores have the same shape as metagraph's S
            if self.scores.shape != zeroes.shape:
                self.scores = zeroes
                logger.warning("Initialized scores to zeros due to score shape mismatch.")
        except:
            self.scores = zeroes
            logger.info(f"Initialized all scores to 0")


        # Init sync with the network. Updates the metagraph.
        self.sync()

        # Serve axon to enable external connections.
        if not self.config.neuron.axon_off:
            self.serve_axon()
        else:
            logger.warning("axon off, not serving ip to chain.")

    def serve_axon(self):
        """Serve axon to enable external connections."""

        logger.info("serving ip to chain...")
        try:
            self.axon = bt.axon(wallet=self.wallet, config=self.config)

            try:
                self.subtensor.serve_axon(
                    netuid=self.config.netuid,
                    axon=self.axon,
                )
                logger.info(f"Running validator", axon = f"{self.axon}", network = self.config.subtensor.chain_endpoint, netuid = self.config.netuid)
            except Exception as e:
                logger.error(f"Failed to serve Axon", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
                pass

        except Exception as e:
            logger.error(f"Failed to create Axon initialize", error = {'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
            pass

    async def concurrent_forward(self):
        coroutines = [
            self.forward()
            for _ in range(self.config.neuron.num_concurrent_forwards)
        ]
        await asyncio.gather(*coroutines)

    def run(self):
        """
        Initiates and manages the main loop for the miner on the Bittensor network. The main loop handles graceful shutdown on keyboard interrupts and logs unforeseen errors.

        This function performs the following primary tasks:
        1. Check for registration on the Bittensor network.
        2. Continuously forwards queries to the miners on the network, rewarding their responses and updating the scores accordingly.
        3. Periodically resynchronizes with the chain; updating the metagraph with the latest network state and setting weights.

        The essence of the validator's operations is in the forward function, which is called every step. The forward function is responsible for querying the network and scoring the responses.

        Note:
            - The function leverages the global configurations set during the initialization of the miner.
            - The miner's axon serves as its interface to the Bittensor network, handling incoming and outgoing requests.

        Raises:
            KeyboardInterrupt: If the miner is stopped by a manual interruption.
            Exception: For unforeseen errors during the miner's operation, which are logged for diagnosis.
        """

        # Check that validator is registered on the network.
        self.sync()

        logger.info(f"Validator starting")

        try:
            while True:
                try:
                    start_block = self.subtensor.get_current_block()
                    logger.info('running forward loop', start_block=start_block)
                    self.loop.run_until_complete(self.concurrent_forward())
                    self.sync()

                    if self.should_exit:
                        break

                    #end_block = self.subtensor.get_current_block()

                    #block_elapsed = end_block - start_block
                    #logger.info('running forward loop', block_elapsed = block_elapsed)

                    """
                    blocks_to_wait = 50
                    if block_elapsed < blocks_to_wait:
                        sleep_time = bt.__blocktime__ * (blocks_to_wait - block_elapsed)
                        logger.warning(f"Block elapsed is less than {blocks_to_wait} blocks, going to sleep", block_elapsed=block_elapsed,
                                       sleep_time=sleep_time)
                        time.sleep(sleep_time)
                    """

                    if self.should_exit:
                        break

                    self.step += 1

                except Exception as e:
                    logger.warning(f"Error in validator loop", error={'exception_type': e.__class__.__name__,'exception_message': str(e),'exception_args': e.args})
                    time.sleep(bt.__blocktime__ * 10)
        except KeyboardInterrupt:
            self.axon.stop()
            logger.success("Validator killed by keyboard interrupt.")
            exit()

        # In case of unforeseen errors, the validator will log the error and continue operations.
        except Exception as err:
            logger.error("Error during validation",error = str(err))
            logger.debug('error', error = print_exception(type(err), err, err.__traceback__))

    def run_in_background_thread(self):
        """
        Starts the validator's operations in a background thread upon entering the context.
        This method facilitates the use of the validator in a 'with' statement.
        """
        if not self.is_running:
            logger.debug("Starting validator in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
            logger.debug("Started")

    def stop_run_thread(self):
        """
        Stops the validator's operations that are running in the background thread.
        """
        if self.is_running:
            logger.debug("Stopping validator in background thread.")
            self.should_exit = True
            self.thread.join(5)
            self.is_running = False
            logger.debug("Stopped")

    def __enter__(self):
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Stops the validator's background operations upon exiting the context.
        This method facilitates the use of the validator in a 'with' statement.

        Args:
            exc_type: The type of the exception that caused the context to be exited.
                      None if the context was exited without an exception.
            exc_value: The instance of the exception that caused the context to be exited.
                       None if the context was exited without an exception.
            traceback: A traceback object encoding the stack trace.
                       None if the context was exited without an exception.
        """
        if self.is_running:
            logger.debug("Stopping validator in background thread.")
            self.should_exit = True
            self.thread.join(5)
            self.is_running = False
            logger.debug("Stopped")

    def set_weights(self):
        """
        Sets the validator weights to the metagraph hotkeys based on the scores it has received from the miners. The weights determine the trust and incentive level the validator assigns to miner nodes on the network.
        """
        # Check if self.scores contains any NaN values and log a warning if it does.
        if np.isnan(self.scores).any():
            logger.warning(
                f"Scores contain NaN values. This may be due to a lack of responses from miners, or a bug in your reward functions."
            )

        # Calculate the average reward for each uid across non-zero values.
        # Replace any NaN values with 0.
        norm = np.linalg.norm(self.scores, ord=1, axis=-1, keepdims=True) + np.finfo(np.float32).eps
        raw_weights = self.scores / norm
        logger.debug(f'Raw weights', raw_weights = raw_weights.tolist())

        # Process the raw weights to final_weights via subtensor limitations.
        (
            processed_weight_uids,
            processed_weights,
        ) = process_weights_for_netuid(
            uids=self.metagraph.uids,
            weights=raw_weights,
            netuid=self.config.netuid,
            subtensor=self.subtensor,
            metagraph=self.metagraph,
        )
        logger.debug(f'Processed weights', processed_weights = [(uid, weight) for uid, weight in zip(processed_weight_uids.tolist(), processed_weights.tolist())])

        # Convert to uint16 weights and uids.
        (
            uint_uids,
            uint_weights,
        ) = weight_utils.convert_weights_and_uids_for_emit(
            uids=processed_weight_uids, weights=processed_weights
        )

        uids_and_weights = list(
            zip(uint_uids, uint_weights)
            )
        
        logger.debug(f'Converted weights to uids', uids_and_weights = uids_and_weights)
        # Sort by weights descending.
        sorted_uids_and_weights = sorted(
            uids_and_weights, key=lambda x: x[1], reverse=True
        )
        
        logger.debug(f'sorted weights to uids', sorted_uids_and_weights = sorted_uids_and_weights)

        weight_log = {}
        for uid, weight in sorted_uids_and_weights:
            weight_log[str(uid)] = (
                str(round(weight, 4)),
                str(int(self.scores[uid].item())),
            )

        logger.info("Setting weights: ", weights=weight_log)

        # Set the weights on chain via our subtensor connection.
        result, msg = self.subtensor.set_weights(
            wallet=self.wallet,
            netuid=self.config.netuid,
            uids=processed_weight_uids,
            weights=processed_weights,
            wait_for_finalization=False,
            wait_for_inclusion=False,
            version_key=self.spec_version
        )
        logger.info("Setting weights result: ", result = result, msg = msg)

        with self.lock:
            self.last_weights_set_block = self.block
            logger.info('Set last_weights_set_block', last_weights_set_block = self.last_weights_set_block)
        if result is True:
            logger.info("set_weights on chain successfully!")
        else:
            logger.error("set_weights failed", return_msg = msg)
        
    def resync_metagraph(self):
        """Resyncs the metagraph and updates the hotkeys and moving averages based on the new metagraph."""
        logger.info("resync_metagraph()")

        # Copies state of metagraph before syncing.
        previous_metagraph = copy.deepcopy(self.metagraph)

        # Sync the metagraph.
        self.metagraph.sync(subtensor=self.subtensor)

        # Check if the metagraph axon info has changed.
        if previous_metagraph.axons == self.metagraph.axons:
            return

        logger.info(
            "Metagraph updated, re-syncing hotkeys, dendrite pool and moving averages"
        )
        # Zero out all hotkeys that have been replaced.
        for uid, hotkey in enumerate(self.hotkeys):
            if hotkey != self.metagraph.hotkeys[uid]:
                self.scores[uid] = 0  # hotkey has been replaced

        # Check to see if the metagraph has changed size.
        # If so, we need to add new hotkeys and moving averages.
        if len(self.hotkeys) < len(self.metagraph.hotkeys):
            # Update the size of the moving average scores.
            new_moving_average = np.zeros((self.metagraph.n))
            min_len = min(len(self.hotkeys), len(self.scores))
            new_moving_average[:min_len] = self.scores[:min_len]
            self.scores = new_moving_average

        # Update the hotkeys.
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)

    def update_scores(self, rewards: np.float32, uids: List[int]):
        """Performs exponential moving average on the scores based on the rewards received from the miners."""

        # Check if rewards contains NaN values.
        if np.isnan(rewards).any():
            logger.warning(f"NaN values detected in rewards", rewards = rewards.tolist())
            # Replace any NaN values in rewards with 0.
            rewards = np.nan_to_num(rewards, 0)

        # Check if `uids` is already a tensor and clone it to avoid the warning.
        if isinstance(uids, np.ndarray):
            uids_tensor = uids.copy()
        else:
            uids_tensor = np.array(uids)

        # Compute forward pass rewards, assumes uids are mutually exclusive.
        # shape: [ metagraph.n ]
        scattered_rewards: np.float32 = self.scores.copy()
        np.put(scattered_rewards, uids_tensor, rewards)
        logger.debug('scattered rewards', scattered_rewards = rewards.tolist())

        # Update scores with rewards produced by this step.
        # shape: [ metagraph.n ]
        alpha: float = self.config.neuron.moving_average_alpha
        self.scores: np.float32 = alpha * scattered_rewards + (
            1 - alpha
        ) * self.scores
        logger.debug(f"Updated moving avg scores", scores = self.scores.tolist())

    def save_state(self):
        """Saves the state of the validator to a file."""
        logger.info("Saving validator state.")

        # Save the state of the validator to file.
        np.savez(
            self.config.neuron.full_path + "/state.npz",
            step=self.step,
            scores=self.scores,
            hotkeys=self.hotkeys
        )

    def load_state(self):
        """Loads the state of the validator from a file."""
        # Load the state of the validator from file.
        state = np.load(self.config.neuron.full_path + "/state.npz")
        self.step = state["step"]
        self.scores = state["scores"]
