import argparse
import os

import bittensor as bt
from bitcoinrpc.authproxy import AuthServiceProxy
from neurons.nodes.utils import index_blocks_by_height

parser = argparse.ArgumentParser()
bt.logging.add_args(parser)


class DogecoinNode:
    def __init__(
            self,
            node_rpc_url: str = None,
            buffer_mode: bool = None,
            buffer_block_limit: int = None,
            buffer_tx_limit: int = None
    ):
        if node_rpc_url is None:
            self.node_rpc_url = (
                os.environ.get("NODE_RPC_URL")
                or "http://doge:doge@127.0.0.1:44555"
            )
        else:
            self.node_rpc_url = node_rpc_url

        if buffer_mode is None:
            self.buffer_mode = (
                os.environ.get("BUFFER_MODE") or False
            )

        if buffer_block_limit is None:
            self.buffer_block_limit = (
                os.environ.get("BUFFER_BLOCK_LIMIT") or 1
            )

        if buffer_tx_limit is None:
            self.buffer_tx_limit = (
                os.environ.get("BUFFER_TX_LIMIT") or 100
            )

        if buffer_mode:
            self.buffer = []
            self.overflow_buffer = []
            self.current_tx_count = 0

    def get_current_block_height(self):
        rpc_connection = AuthServiceProxy(self.node_rpc_url)
        return rpc_connection.getblockcount()

    def get_block_by_height(self, block_height):
        rpc_connection = AuthServiceProxy(self.node_rpc_url)
        block_hash = rpc_connection.getblockhash(block_height)
        block_data = rpc_connection.getblock(block_hash, True)

        full_transactions = []
        for txid in block_data["tx"]:
            tx = rpc_connection.getrawtransaction(txid, True)
            full_transactions.append(tx)

        # Construct the final structure similar to Bitcoin's verbose getblock output
        block_data["tx"] = full_transactions

        # bt.logging.info("Block data: {}".format(block_data))
        return block_data

    def buffered_get_blocks_by_height(self, block_heights):
        rpc_connection = AuthServiceProxy(self.node_rpc_url)
        call_arrays = [["getblockhash", i] for i in block_heights]
        block_hashes = rpc_connection.batch_(call_arrays)

        blocks_call_arrays = [["getblock", h, True] for h in block_hashes]
        blocks_data = rpc_connection.batch_(blocks_call_arrays)

        tx_hashes = []

        for b in blocks_data:
            for t in b['tx']:
                tx_hashes.append(t)

        txs_call_array = [["getrawtransaction", tx, True] for tx in tx_hashes]
        txs_data = rpc_connection.batch_(txs_call_array)

        txs_count = txs_data.count()
        blocks_data = index_blocks_by_height(txs_data, blocks_data)

        if txs_count < self.buffer_tx_limit:
            self.buffer = blocks_data

        return blocks_data




