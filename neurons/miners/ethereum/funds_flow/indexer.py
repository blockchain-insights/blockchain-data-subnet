import traceback
import os
import signal
import time
from math import floor
from neurons.setup_logger import setup_logger
from neurons.nodes.evm.ethereum.node import EthereumNode
from neurons.miners.ethereum.funds_flow.graph_creator import GraphCreator
from neurons.miners.ethereum.funds_flow.graph_indexer import GraphIndexer
from neurons.miners.ethereum.funds_flow.graph_search import GraphSearch

# Global flag to signal shutdown
shutdown_flag = False
MIN_BLOCKS_PER_QUERY = 10
BLOCKS_PER_QUERY_COUNT = 1000
TXS_PER_BLOCK_AVG = 0
CACHE_COUNT = 5000
tx = {'cacheCnt': 0, 'cacheTx': [], 'inprogress': False}

logger = setup_logger("EthereumIndexer")


def shutdown_handler(signum, frame):
    global shutdown_flag
    logger.info(
        "Shutdown signal received. Waiting for current indexing to complete before shutting down."
    )
    shutdown_flag = True


# Register the shutdown handler for SIGINT and SIGTERM
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


def log_txHash_crashed_by_memgraph(transaction):
    transactionHash = ''
    for tx in transaction:
        transactionHash += tx.tx_hash + '\n'
    f = open(f"eth_crashed_block_by_memgraph.txt", "a")
    f.write(transactionHash)
    f.close()


def log_blockHeight_crashed_by_rpc(block_height):
    f = open("eth_crashed_block_by_rpc.txt", "a")
    f.write(f"{block_height}\n")
    f.close()


def log_finished_thread_info(index, start, last, time):
    f = open("eth_finished_thread.txt", "a")
    f.write(f"Index: {index}, Rage({start}, {last}), Total Spent Time: {time}\n")
    f.close()


def single_index(_graph_creator, _graph_indexer, _graph_search, start_height: int, end_height: int, is_reverse_order: bool = False):
    global shutdown_flag, BLOCKS_PER_QUERY_COUNT
    ethereum_node = EthereumNode()

    start = start_height
    last = end_height
    direction = 1

    if not is_reverse_order:
        start = start_height if start_height < end_height else end_height
        last = end_height if end_height > start_height else start_height
    else:
        start = start_height if start_height > end_height else end_height
        last = end_height if end_height < start_height else start_height
        direction = -1

    start_time = time.time()
    buf_time = time.time()

    while not shutdown_flag and (last - start) * direction >= 0:
        to_block = min(start + BLOCKS_PER_QUERY_COUNT, last)
        try:
            blocks = ethereum_node.get_block_and_txs_from_graphql(start, to_block)
            txs_count = sum(len(block['transactions']) for block in blocks)
            blocks_with_txs = [block for block in blocks if block['transactions']]
            blocks = []
            avg_txs = txs_count / len(blocks_with_txs) if len(blocks_with_txs) > 0 else 0

            if avg_txs * len(blocks_with_txs) >= CACHE_COUNT:
                BLOCKS_PER_QUERY_COUNT = max(MIN_BLOCKS_PER_QUERY, BLOCKS_PER_QUERY_COUNT - 5)

            if txs_count == 0:
                start += direction + BLOCKS_PER_QUERY_COUNT
                continue

            logger.info("Blocks {} to {} have {} transactions".format(start, to_block, txs_count))

            for block in blocks_with_txs:
                in_memory_graph = _graph_creator.create_in_memory_graph_from_block_graphql(ethereum_node, block)
                new_transaction = in_memory_graph.transactions
                new_transaction_cnt = len(new_transaction)

                if new_transaction_cnt <= 0:
                    start += direction
                    continue

                tx['cacheCnt'] += new_transaction_cnt
                tx['cacheTx'] = tx['cacheTx'] + new_transaction

                if tx['cacheCnt'] > CACHE_COUNT or (last - start) * direction == 0:
                    tx['inprogress'] = True
                    success = _graph_indexer.create_graph_focused_on_funds_flow(tx['cacheTx'])

                    min_block_height_cache, max_block_height_cache = _graph_search.get_min_max_block_height_cache()
                    _graph_indexer.set_min_max_block_height_cache(min(min_block_height_cache, start), max(max_block_height_cache, start))

                    if success:
                        time_taken = time.time() - buf_time
                        formatted_tps = tx['cacheCnt'] / time_taken if time_taken > 0 else float("inf")
                        logger.info(f"[Main Thread] - Finished Block: {start}, TPS: {formatted_tps}, Spent time: {time.time() - start_time}\n")
                        start += min(to_block + direction, last)

                    else:
                        # sometimes we may have memgraph server connect issue catch all failed block so we can retry
                        log_txHash_crashed_by_memgraph(0, tx['cacheTx'])

                    tx['cacheTx'].clear()
                    tx['cacheCnt'] = 0
                    buf_time = time.time()
                    tx['inprogress'] = False

                    if shutdown_flag:
                        logger.info(f"Finished indexing block {start} before shutdown.")
                        break




        except Exception as e:
            logger.error(traceback.format_exc())
            logger.error(f"Exception {e.__traceback__.tb_lineno}")
            logger.error(f"Exception {e.__traceback__.tb_lasti}")
            logger.error(f"Exception {e.__traceback__.tb_frame.f_code}")
            logger.error(f"Exception {e.__dict__}")
            # sometimes we may have rpc server connect issue catch all failed block so we can retry
            log_blockHeight_crashed_by_rpc(start)
            #start += min(to_block + direction, last)
    
    logger.info(f"Finished Single Main Indexing from {start_height} to {end_height}")
    log_finished_thread_info(0, start_height, end_height, time.time() - start_time)



if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    graph_creator = GraphCreator()
    graph_indexer = GraphIndexer()
    ethereum_node = EthereumNode()
    graph_search = GraphSearch()

    graph_indexer.create_indexes()

    retry_delay = 60

    # Latest SUB Thread START, LAST Block Height
    sub_start_height = 0
    sub_last_height = 0
    sub_start_height_str = os.getenv('ETHEREUM_SUB_START_BLOCK_HEIGHT', None)
    sub_last_height_str = os.getenv('ETHEREUM_SUB_END_BLOCK_HEIGHT', None)

    graph_last_block_height = graph_indexer.get_latest_block_number()
    if sub_start_height_str:
        sub_start_height = int(sub_start_height_str)
        if graph_last_block_height > sub_start_height:
            sub_start_height = graph_last_block_height + 1
    else:
        sub_start_height = graph_last_block_height

    # Set Initial SUB Thread Min & Max Block Height
    indexed_min_block_height, indexed_max_block_height = graph_search.get_min_max_block_height_cache()
    if indexed_min_block_height == 0:
        indexed_min_block_height = sub_start_height
    graph_indexer.set_min_max_block_height_cache(indexed_min_block_height, indexed_max_block_height)

    logger.info(f"indexed_min_block_height: {indexed_min_block_height} - indexed_max_block_height: {indexed_max_block_height}")

    current_block_height = ethereum_node.get_current_block_height()
    logger.info(f"ETH node - Current block height: {current_block_height}")
    if sub_last_height_str:
        sub_last_height = int(sub_last_height_str)
        if current_block_height > sub_last_height:
            sub_last_height = current_block_height
    else:
        sub_last_height = current_block_height

    # Config Main Thread
    main_start_height = 0
    main_last_height = 0
    is_reverse_order = False
    main_start_height_str = os.getenv('ETHEREUM_MAIN_START_BLOCK_HEIGHT', None)
    main_last_height_str = os.getenv('ETHEREUM_MAIN_END_BLOCK_HEIGHT', None)
    is_reverse_order_str = os.getenv('ETHEREUM_MAIN_IN_REVERSE_ORDER', None)

    if main_start_height_str:
        main_start_height = int(main_start_height_str)
    if main_last_height_str:
        main_last_height = int(main_last_height_str)
    if is_reverse_order_str:
        is_reverse_order = bool(int(is_reverse_order_str))

    try:
        # Only Main Indexer running
        if main_start_height > 0 and main_last_height > 0:
            logger.info(f'-- Main thread is running for indexing based on min({main_start_height}) & max({main_last_height}) block numbers --')
            single_index(graph_creator, graph_indexer, graph_search, main_start_height, main_last_height, is_reverse_order)
        else:
            logger.error('ETHEREUM_MAIN_START_BLOCK_HEIGHT & ETHEREUM_MAIN_END_BLOCK_HEIGHT should be given by ENV')

    except Exception as e:
        logger.error(f"Retry failed with error: {e}")
        logger.info(f"Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
    finally:
        graph_indexer.close()
        graph_search.close()
        logger.info("Indexer stopped")
