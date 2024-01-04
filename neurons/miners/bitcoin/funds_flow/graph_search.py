import os
import typing

from neo4j import GraphDatabase


class GraphSearch:
    def __init__(
        self,
        graph_db_url: str = None,
        graph_db_user: str = None,
        graph_db_password: str = None,
    ):
        if graph_db_url is None:
            self.graph_db_url = (
                os.environ.get("GRAPH_DB_URL") or "bolt://localhost:7687"
            )
        else:
            self.graph_db_url = graph_db_url

        if graph_db_user is None:
            self.graph_db_user = os.environ.get("GRAPH_DB_USER") or ""
        else:
            self.graph_db_user = graph_db_user

        if graph_db_password is None:
            self.graph_db_password = os.environ.get("GRAPH_DB_PASSWORD") or ""
        else:
            self.graph_db_password = graph_db_password

        self.driver = GraphDatabase.driver(
            self.graph_db_url,
            auth=(self.graph_db_user, self.graph_db_password),
        )

    def execute_query(self, network, query):
        # TODO: Implement this
        return []

    def get_block_transaction(self, block_height):
        with self.driver.session() as session:
            data_set = session.run(
                """
                MATCH (t:Transaction { block_height: $block_height })
                RETURN t.block_height AS block_height, COUNT(t) AS transaction_count
                """,
                block_height=block_height
            )
            result = data_set.single()
            return {
                "block_height": result["block_height"],
                "transaction_count": result["transaction_count"]
            }

    def get_run_id(self):
        records, summary, keys = self.driver.execute_query("RETURN 1")
        return summary.metadata.get('run_id', None)

    def get_block_transactions(self, block_heights: typing.List[int]):
        with self.driver.session() as session:
            query = """
                UNWIND $block_heights AS block_height
                MATCH (t:Transaction { block_height: block_height })
                RETURN block_height, COUNT(t) AS transaction_count
            """
            data_set = session.run(query, block_heights=block_heights)

            results = []
            for record in data_set:
                results.append({
                    "block_height": record["block_height"],
                    "transaction_count": record["transaction_count"]
                })

            return results

    def get_block_range(self):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Transaction)
                RETURN MAX(t.block_height) AS latest_block_height, MIN(t.block_height) AS start_block_height
                """
            )
            single_result = result.single()

            if single_result[0] is None:
                return {
                    'latest_block_height': 0,
                    'start_block_height':0
                }

            return {
                'latest_block_height': single_result[0],
                'start_block_height': single_result[1]
            }

    def get_latest_block_number(self):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Transaction)
                RETURN MAX(t.block_height) AS latest_block_height
                """
            )
            single_result = result.single()
            if single_result[0] is None:
                return 0
            return single_result[0]


    def get_block_ranges(self):
        """
        This function generates block ranges from a memgraph indexing data.

        Returns:
           output (list): A list of dictionaries indicating the start_block_height and the end_block_height.
        """

        ranges = []

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (b:Block)
                RETURN DISTINCT b.block_height AS height
                ORDER BY height ASCENDING
                """
            )

            for record in result:
                ranges.append(
                    record['height']
                )

        # handle an empty list
        if not ranges:
            return []

        result = []
        start = ranges[0]
        end = start

        # Iterate over the list of integers
        for i in range(1, len(ranges)):
            # Check if the current integer is consecutive
            if ranges[i] == end + 1:
                end = ranges[i]
            else:
                # If not consecutive, save the previous range and start a new one
                result.append({'start_block_height': start, 'end_block_height': end})
                start = ranges[i]
                end = start

        return result
