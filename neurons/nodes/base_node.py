from insights.protocol import NETWORK_BITCOIN, NETWORK_DOGE
from neurons.nodes.bitcoin.node import BitcoinNode
from neurons.nodes.doge.node import DogeNode

from abc import ABC, abstractmethod

import concurrent

class Node(ABC):
    def __init__(self):
       pass


    @abstractmethod
    def get_current_block_height(self):
        pass


    @abstractmethod
    def get_block_by_height(self, block_height):
        pass


    @abstractmethod
    def validate_data_sample(self, data_sample):
        pass


    def validate_all_data_samples(self, data_samples, min_samples=10):
        if len(data_samples) < min_samples:
            return False
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Creating a future for each data sample validation
            futures = [executor.submit(self.validate_data_sample(sample)) for sample in data_samples]

            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    return False  # If any data sample is invalid, return False immediately
        return True 


    @classmethod
    def create_from_network(cls, network: str) -> 'Node':
        node_class = {
            NETWORK_BITCOIN: BitcoinNode,
            NETWORK_DOGE : DogeNode
            # Add other networks and their corresponding classes as needed
        }.get(network)

        if node_class is None:
            raise ValueError(f"Unsupported network: {network}")
        
        return node_class()
    