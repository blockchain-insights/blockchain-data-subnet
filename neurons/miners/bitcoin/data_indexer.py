import psycopg2
from psycopg2.extras import execute_values
from decimal import Decimal
from datetime import datetime

"""
TODO:
- run pgsql in docker
- install pgsqlAdmin on localhost
- create init_db script for checkng if db exists and creating it if not, then creating database schema
- run that on startup script, but with parametors for blockchain name and db name so the tables get blockchain prefix bitcoin_blocks, bitcoin_transactions, bitcoin_vin, bitcoin_vout
- create DataIndexer class for inserting data into pgsql from bitcoin node
- run inserting tests

!! add extra address balance table for each address and update it on each block insert ( so we know the balances at given blocks )

!! indexing method should allow upserts so we can rerun indexer from 0 in case of some changes, or create another indexer for that ! aka repair indexer


yea... and we can say that the miner part is ready,
the validator will be querying miners for blockrangerange and then validating the blocks and then inserting them into the memgraph

=========

implement protocol for getting data blockchain + block range

"""


def get_latest_block_number(self):
    # Connect to your postgres database
    conn = psycopg2.connect("dbname=yourdbname user=youruser password=yourpassword")
    cursor = conn.cursor()

    try:
        # Assuming the table is indexed on block_height, this will be a fast operation
        cursor.execute(
            "SELECT block_height FROM Blocks ORDER BY block_height DESC LIMIT 1;"
        )
        result = cursor.fetchone()
        # If the table is empty, it will return None, so we return 0 in that case
        return result[0] if result else 0

    except Exception as e:
        print(f"An exception occurred: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def create_pgsql_from_block(self, block):
    # Connect to your postgres database
    conn = psycopg2.connect("dbname=yourdbname user=youruser password=yourpassword")
    cursor = conn.cursor()

    try:
        block_height = block["height"]
        block_hash = block["hash"]
        block_previous_hash = block.get("previousblockhash", None)
        timestamp = datetime.fromtimestamp(block["time"])
        nonce = block["nonce"]
        difficulty = block["difficulty"]

        # Insert the block using execute_values for batch processing
        block_data = [
            (
                block_height,
                block_hash,
                timestamp,
                block_previous_hash,
                nonce,
                difficulty,
            )
        ]
        execute_values(
            cursor,
            """
            INSERT INTO Blocks (block_height, block_hash, timestamp, previous_block_hash, nonce, difficulty)
            VALUES %s ON CONFLICT (block_height) DO NOTHING;
            """,
            block_data,
        )

        transactions = block["tx"]
        transaction_data = []
        vout_data = []
        vin_data = []

        for tx in transactions:
            tx_id = tx["txid"]
            fee_amount = Decimal(tx.get("fee", 0))
            transaction_data.append((tx_id, block_height, timestamp, fee_amount))

            for index, vout in enumerate(tx["vout"]):
                amount = Decimal(vout["value"])
                is_spent = False  # Assuming the output is not spent when created
                address = vout["scriptPubKey"].get("addresses", [""])[
                    0
                ]  # Taking the first address
                script_type = vout["scriptPubKey"].get("type", "unknown")
                vout_data.append((tx_id, index, amount, is_spent, address, script_type))

        # Batch insert for transactions and vouts
        execute_values(
            cursor,
            """
            INSERT INTO Transactions (tx_id, block_height, timestamp, fee_amount)
            VALUES %s ON CONFLICT (tx_id) DO NOTHING;
            """,
            transaction_data,
        )

        execute_values(
            cursor,
            """
            INSERT INTO VOUT (tx_id, index, amount, is_spent, address, script_type)
            VALUES %s ON CONFLICT (tx_id, index) DO NOTHING;
            """,
            vout_data,
        )

        # Commit after inserting blocks, transactions, and vouts
        conn.commit()

        # Build a mapping of (tx_id, index) to vout_id for the VOUTs that have been inserted
        cursor.execute(
            """
            SELECT vout_id, tx_id, index FROM VOUT WHERE tx_id IN %s;
            """,
            (tuple(set(vout[0] for vout in vout_data)),),
        )
        vout_mapping = {(row[1], row[2]): row[0] for row in cursor.fetchall()}

        # Now populate vin_data using the vout_mapping
        for tx in transactions:
            for vin in tx["vin"]:
                tx_id = tx["txid"]
                if "coinbase" in vin:
                    coinbase = vin["coinbase"]
                    sequence = None
                    vout_id = None  # Coinbase transactions don't reference a vout
                    vin_data.append((tx_id, vout_id, sequence, True, coinbase))
                else:
                    prev_tx_id = vin.get("txid")
                    prev_vout_index = vin.get("vout")
                    sequence = vin.get("sequence")
                    is_coinbase = False
                    coinbase = None
                    # Use the mapping to get vout_id
                    vout_id = vout_mapping.get((prev_tx_id, prev_vout_index))
                    if vout_id is not None:
                        vin_data.append(
                            (tx_id, vout_id, sequence, is_coinbase, coinbase)
                        )

        # Batch insert for vins
        execute_values(
            cursor,
            """
            INSERT INTO VIN (tx_id, vout_id, sequence, is_coinbase, coinbase)
            VALUES %s ON CONFLICT (tx_id, vout_id) DO NOTHING;
            """,
            vin_data,
        )

        # Final commit after inserting vins
        conn.commit()

        return True

    except Exception as e:
        conn.rollback()
        print(f"An exception occurred: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
