from insights.protocol import NETWORK_BITCOIN
from neurons.nodes.bitcoin.node import BitcoinNode
from abc import ABC, abstractmethod

class Node(ABC):
    def __init__(self, node_rpc_url: str = None):
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


def get_node(network: str) -> Node:
    return {
        NETWORK_BITCOIN : BitcoinNode()
    }.get(network)
    