from bitcoinrpc.authproxy import AuthServiceProxy
from neurons.nodes.abstract_node import Node

import os


class BitcoinNode(Node):
    def __init__(self):
        self.node_rpc_url = os.environ.get("BITCOIN_NODE_RPC_URL", "http://bitcoinrpc:rpcpassword@127.0.0.1:8332")


    def get_current_block_height(self):
        rpc_connection = AuthServiceProxy(self.node_rpc_url)
        try:
            return rpc_connection.getblockcount()
        finally:
            rpc_connection._AuthServiceProxy__conn.close()  # Close the connection


    def get_block_by_height(self, block_height):
        rpc_connection = AuthServiceProxy(self.node_rpc_url)
        try:
            block_hash = rpc_connection.getblockhash(block_height)
            return rpc_connection.getblock(block_hash, 2)
        finally:
            rpc_connection._AuthServiceProxy__conn.close()  # Close the connection


    def validate_data_sample(self, data_sample):
        block_data = self.get_block_by_height(data_sample['block_height'])
        is_valid = len(block_data["tx"]) == data_sample["transaction_count"]
        return is_valid
        