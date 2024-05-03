import logging
from dataclasses import dataclass, field
from typing import List, Dict
from decimal import Decimal
import asyncio
from Crypto.Hash import SHA256

from web3.providers.base import JSONBaseProvider
from web3.providers import HTTPProvider
from web3 import Web3
from eth_abi import abi

from neurons.nodes.evm.ethereum.node import EthereumNode

@dataclass
class Block:
    block_number: int
    block_hash: str
    timestamp: int # Unix epoch time
    parent_hash: str
    nonce: int
    difficulty: int
    transactions: List["Transaction"] = field(default_factory=list)

@dataclass
class Account:
    address: str
    balance: str
    timestamp: int # Unix epoch time

@dataclass
class Transaction:
    block_hash: str
    block_number: int
    tx_hash: str
    timestamp: int # Unix epoch time
    gas_used: str
    checksum: str # validation checksum for miner
    from_address: Account
    to_address: Account
    value_wei: str
    symbol: str = "ETH" # ETH, USDT, USDC, ...

@dataclass
class Block:
    hash: str
    number: str
    nonce: str
    timestamp: str
    parent: str
    difficulty: str
    transactionCount: str
    transactions: List[Transaction]

@dataclass
class GraphQlBlock:
    number: int
    hash: str
    timestamp: int # Unix epoch time
    parent_hash: str
    nonce: int
    difficulty: int
    transactions: List["GraphQlTransaction"] = field(default_factory=list)

@dataclass
class GraphQlLog:
    topics: List[str]
    data: str
    account: str

@dataclass
class GraphQlTransaction:
    block_hash: str
    block_number: int
    tx_hash: str
    timestamp: int # Unix epoch time
    gas_used: str
    gas_price: str
    checksum: str # validation checksum for miner
    from_address: Account
    to_address: Account
    value_wei: str
    raw_receipt: str
    symbol: str = "ETH" # ETH, USDT, USDC, ...
    logs: List[GraphQlLog] = field(default_factory=list)




class GraphCreator:
    def __init__(self):
        self.tokenTypes = {}

    def create_graphqltransaction_from_graphql_request(self, tx, block: GraphQlBlock) -> GraphQlTransaction:
        logs = [GraphQlLog(topics=log['topics'], data=log['data'], account=log['account']['address']) for log in tx['logs']]
        if tx is None:
            logging.error(f"{block}")

        from_address = Account(
            address=tx['from']['address'],
            balance=tx['from']['balance'],
            timestamp=block.timestamp,
        )
        to_address = Account(
            address=tx['to']['address'] if tx['to'] else "None",
            balance=tx['to']['balance'] if tx['to'] else "0",
            timestamp=block.timestamp,
        )

        binary_address = tx['hash'] + block.hash + from_address.address + to_address.address
        checksum = sha256_result = SHA256.new(binary_address.encode('utf-8')).hexdigest()

        return GraphQlTransaction(
            logs=logs,
            gas_used=tx['gasUsed'],
            gas_price=tx['gasPrice'],
            from_address=from_address,
            to_address=to_address,
            tx_hash=tx['hash'],
            value_wei=tx['value'],
            raw_receipt=tx['rawReceipt'],
            block_number=block.number,
            block_hash=block.hash,
            timestamp=block.timestamp,
            checksum=checksum
        )

    def create_in_memory_graph_from_block_graphql(self, ethereum_node, block_data) -> GraphQlBlock:
        from dotenv import load_dotenv
        load_dotenv()

        data = block_data

        block = GraphQlBlock(
            number=int(data["number"], 0),
            hash=data["hash"],
            timestamp=int(data["timestamp"], 0),
            parent_hash=data["parent"]["hash"],
            nonce=data["nonce"],
            difficulty=data["difficulty"],
            transactions=[]
        )

        txs = [self.create_graphqltransaction_from_graphql_request(tx, block) for tx in data['transactions']]

        for idx, tx in enumerate(txs):
            if (tx.from_address.address and tx.to_address.address and tx.value_wei
                    and tx.from_address.address is not None and tx.from_address.address is not None):

                if int(tx.value_wei, 0) > 0:
                    block.transactions.append(tx)

                # Append native token transactions
                if int(tx.value_wei, 0) == 0:
                    if tx.logs and len(tx.logs) > 0:
                        log = tx.logs[0]
                        if log.topics and len(log.topics) > 2:
                            try:
                                contract_address = Web3.to_checksum_address(log.account)
                                symbol = ''
                                if contract_address not in self.tokenTypes:
                                    symbol = ethereum_node.get_symbol_name(contract_address)
                                    self.tokenTypes.update({contract_address: symbol})
                                else:
                                    symbol = self.tokenTypes[contract_address]

                                from_address = abi.decode(['address'], bytes.fromhex(log.topics[1][2:]))
                                to_address = abi.decode(['address'], bytes.fromhex(log.topics[2][2:]))
                                from_address = ''.join(from_address)
                                to_address = ''.join(to_address)

                                if from_address is None:
                                    continue
                                if to_address is None:
                                    continue

                                from_account = Account(
                                    address=from_address,
                                    timestamp=block.timestamp,
                                    balance='0'
                                )

                                to_account = Account(
                                    address=to_address,
                                    timestamp=block.timestamp,
                                    balance='0'
                                )

                                value = abi.decode(['uint256'], bytes.fromhex(log.data[2:]))

                                binary_address = tx.tx_hash + tx.block_hash + from_address + to_address
                                checksum = sha256_result = SHA256.new(binary_address.encode('utf-8')).hexdigest()

                                tx.from_address = from_account
                                tx.to_address = to_account
                                tx.value_wei = value
                                tx.symbol = symbol

                                block.transactions.append(tx)
                            except Exception as e:
                                logging.error(f"Failed to create tx {e}")
                                continue

        return block