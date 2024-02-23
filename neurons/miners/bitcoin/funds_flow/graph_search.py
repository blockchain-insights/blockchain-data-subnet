import os
import typing
from neo4j import GraphDatabase

from neurons.utils import is_malicious


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

    def execute_query(self, query):
        with self.driver.session() as session:
            if not is_malicious(query):
                result = session.run(query)
                return result
            else:
                return None


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

    def solve_challenge(self, in_total_amount: int, out_total_amount: int, tx_id_last_4_chars: str) -> str:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Transaction {out_total_amount: $out_total_amount})
                WHERE t.in_total_amount = $in_total_amount AND t.tx_id ENDS WITH $tx_id_last_4_chars
                RETURN t.tx_id;
                """,
                in_total_amount=in_total_amount,
                out_total_amount=out_total_amount,
                tx_id_last_4_chars=tx_id_last_4_chars
            )
            single_result = result.single()
            if single_result is None or single_result[0] is None:
                return None
            return single_result[0]

    def get_schema(self):
        with self.driver.session() as session:
            nodes_result = session.run(
                """
                MATCH (APP_INTERNAL_EXEC_VAR)
                WITH APP_INTERNAL_EXEC_VAR
                LIMIT 10000
                RETURN DISTINCT 
                count(APP_INTERNAL_EXEC_VAR)  AS count,
                labels(APP_INTERNAL_EXEC_VAR) AS labels,
                keys(APP_INTERNAL_EXEC_VAR)   AS properties;
                """
            )
            nodes = process_query_results(nodes_result)

            relations_result = session.run(
                """
                MATCH ()-[e]->()
                WITH e
                LIMIT 10000 
                RETURN DISTINCT 
                count(e)  AS count,
                labels(startNode(e)) AS startNodeLabels,
                type(e)   AS label,
                labels(endNode(e)) AS endNodeLabels,
                keys(e)   AS properties;
                """
            )
            relations = process_query_results(relations_result)

            return {'nodes': nodes, 'relations': relations}


def process_query_results(results_cursor, exclude_fields=None):
    """
    Processes the results from a Cypher query execution and transforms them into a list of dictionaries.

    Parameters:
    - results_cursor: The cursor containing results from the graph query execution.
    - exclude_fields: A list of field names to exclude from the results. Defaults to None.

    Returns:
    A list of dictionaries, each representing a record from the query results, excluding specified fields.
    """
    if exclude_fields is None:
        exclude_fields = []

    processed_results = []
    for record in results_cursor:
        record_dict = {}
        for key in record.keys():
            if key not in exclude_fields:
                # Special handling for 'labels' and 'properties' to ensure they are lists
                if key in ['labels', 'startNodeLabels', 'endNodeLabels', 'properties'] and not isinstance(record[key], list):
                    record_dict[key] = [record[key]]
                else:
                    record_dict[key] = record[key]
        processed_results.append(record_dict)

    return processed_results