import unittest
import os

from insights import protocol
from neurons.miners.bitcoin.funds_flow.utils.query_builder import QueryBuilder

class TestGraphSearch(unittest.TestCase):
    def test_build_search_query(self):
        # test case 1
        query = protocol.Query(type=protocol.QUERY_TYPE_SEARCH, target='Transaction', limit=20)
        cypher_query = QueryBuilder.build_query(query)
        self.assertEqual(cypher_query, "MATCH (t:Transaction)\nRETURN t\nLIMIT 20;")
        
        # test case 2
        query = protocol.Query(type=protocol.QUERY_TYPE_SEARCH, target='Transaction', limit=20, where={
            "tx_id": "0123456789"
        })
        cypher_query = QueryBuilder.build_query(query)
        self.assertEqual(cypher_query, 'MATCH (t:Transaction{tx_id: "0123456789"})\nRETURN t\nLIMIT 20;')
        
if __name__ == '__main__':
    unittest.main()
