import os
import signal
import time
import traceback

from neurons.miners.bitcoin.funds_flow.graph_search import GraphSearch
from neurons.setup_logger import setup_logger
from neurons.nodes.bitcoin.node import BitcoinNode
from neurons.nodes.dogecoin.node import DogecoinNode
from neurons.miners.bitcoin.funds_flow.graph_creator import GraphCreator
from neurons.miners.bitcoin.funds_flow.graph_indexer import GraphIndexer
from neurons.miners.utils import (
    subtract_ranges_from_large_range,
    create_ranges_from_list,
    total_items_in_ranges,
    remove_specific_integers,
    next_largest_excluded
)

# Global flag to signal shutdown
shutdown_flag = False
logger = setup_logger("Indexer")


def shutdown_handler(signum, frame):
    global shutdown_flag
    logger.info(
        "Shutdown signal received. Waiting for current indexing to complete before shutting down."
    )
    shutdown_flag = True


def index_blocks(_rpc_node, _graph_creator, _graph_indexer, start_h, r_data):
    global shutdown_flag
    skip_blocks = 6

    while not shutdown_flag:
        current_block_height = _rpc_node.get_current_block_height() - 6
        if current_block_height - skip_blocks < 0:
            logger.info("Waiting min 6 for blocks to be mined.")
            time.sleep(10)
            continue

        if start_h > current_block_height or start_h >= current_block_height - skip_blocks:
            logger.info(
                f"Waiting for new blocks. Current height is {current_block_height}."
            )
            time.sleep(30)
            continue

        block_height = start_h
        while block_height <= current_block_height - skip_blocks:
            block = _rpc_node.get_block_by_height(block_height)
            num_transactions = len(block["tx"])
            start_time = time.time()
            in_memory_graph = _graph_creator.create_in_memory_graph_from_block(block)
            success = _graph_indexer.create_graph_focused_on_money_flow(in_memory_graph)
            end_time = time.time()
            time_taken = end_time - start_time
            node_block_height = rpc_node.get_current_block_height()
            progress = block_height / node_block_height * 100
            formatted_num_transactions = "{:>4}".format(num_transactions)
            formatted_time_taken = "{:6.2f}".format(time_taken)
            formatted_tps = "{:8.2f}".format(
                num_transactions / time_taken if time_taken > 0 else float("inf")
            )
            formatted_progress = "{:6.2f}".format(progress)

            if time_taken > 0:
                logger.info(
                    "Block {:>6}: Processed {} transactions in {} seconds {} TPS Progress: {}%".format(
                        block_height,
                        formatted_num_transactions,
                        formatted_time_taken,
                        formatted_tps,
                        formatted_progress,
                    )
                )
            else:
                logger.info(
                    "Block {:>6}: Processed {} transactions in 0.00 seconds (  Inf TPS). Progress: {}%".format(
                        block_height, formatted_num_transactions, formatted_progress
                    )
                )

            int_index = r_data["unindexed_ranges"].index(block_height)

            if success:
                r_data["total_blocks_indexed"] += 1

                r_data["unindexed_ranges"] = remove_specific_integers(
                    r_data["unindexed_ranges"], [block_height]
                )

                # indexer flooding prevention
                threshold = int(os.getenv('BLOCK_PROCESSING_TRANSACTION_THRESHOLD', 500))
                if num_transactions > threshold:
                    delay = float(os.getenv('BLOCK_PROCESSING_DELAY', 1))
                    logger.info(f"Block tx count above {threshold}, slowing down indexing by {delay} seconds to prevent flooding.")
                    time.sleep(delay)

            else:
                logger.error(f"Failed to index block {block_height}.")
                time.sleep(30)

            if shutdown_flag:
                logger.info(f"Finished indexing block {block_height} before shutdown.")
                break

            start_h = r_data["unindexed_ranges"][int_index]


# Register the shutdown handler for SIGINT and SIGTERM
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    network = os.getenv('NETWORK')
    rpc_node = None

    if network == 'bitcoin':
        rpc_node = BitcoinNode()
    elif network == 'doge':
        rpc_node = DogecoinNode()
    else:
        logger.error(f"Network {network} not supported; exiting")
        exit()

    logger.info(f"Indexing {network}...")

    graph_creator = GraphCreator()
    graph_search = GraphSearch()
    graph_indexer = GraphIndexer()

    start_height_str = os.getenv("BITCOIN_START_BLOCK_HEIGHT", None)
    logger.info(f"Start height env var: {start_height_str}")
    last_indexed_block = graph_indexer.get_latest_block_number()
    logger.info(f"Last indexed block: {last_indexed_block}")
    latest_block_height = rpc_node.get_current_block_height()
    logger.info(f"Latest block height: {latest_block_height}")

    range_data = {
        "indexed_ranges": [],
        "unindexed_ranges": [],
        "blocks_to_index": [],
        "total_blocks_indexed": 0,
    }


    logger.info("Fetching indexed block ranges.")
    range_data["indexed_ranges"] = graph_search.get_block_ranges()
    # logger.info(f'Indexed ranges: {range_data["indexed_ranges"]}')

    # this one is the actual array of integers to index
    range_data["unindexed_ranges"] = subtract_ranges_from_large_range(
        latest_block_height, range_data["indexed_ranges"]
    )

    range_data["blocks_to_index"] = create_ranges_from_list(
        range_data["unindexed_ranges"]
    )

    range_data["total_blocks_indexed"] = total_items_in_ranges(
        range_data["indexed_ranges"]
    )

    logger.info("Total blocks indexed: " + str(range_data["total_blocks_indexed"]))

    retry_delay = 60
    # purpose of this indexer is to index FROM to infinity only
    while True:
        try:
            logger.info("Starting indexer")
            graph_last_block_height = graph_indexer.get_latest_block_number() + 1
            logger.info(f"Latest indexed block: {graph_last_block_height}")

            if start_height_str is not None:
                start_height = next_largest_excluded(range_data["blocks_to_index"], int(start_height_str))
            else:
                start_height = range_data["unindexed_ranges"][0]

            logger.info(f"Starting from block height: {start_height}")
            logger.info(f"Current node block height: {rpc_node.get_current_block_height()}")
            logger.info(f"Latest indexed block height: {graph_last_block_height}")

            logger.info("Creating indexes...")
            graph_indexer.create_indexes()
            logger.info("Starting indexing blocks...")
            index_blocks(rpc_node, graph_creator, graph_indexer, start_height, range_data)
            break
        except Exception as e:
            ## traceback.print_exc()
            logger.error(f"Retry failed with error: {e}")
            logger.info(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        finally:
            graph_indexer.close()
            logger.info("Indexer stopped")