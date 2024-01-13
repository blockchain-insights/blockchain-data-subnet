import unittest
from unittest.mock import MagicMock
from neurons.nodes.implementations.bitcoin import BitcoinNode
from neurons.nodes.implementations.doge import DogeNode
from neurons.nodes.node_utils import create_node_from_network

class TestNode(unittest.TestCase):

    def setUp(self):
        pass

    def test_create_from_network_bitcoin(self):
        node = create_node_from_network("bitcoin")
        self.assertIsInstance(node, BitcoinNode)

    def test_create_from_network_doge(self):
        node = create_node_from_network("doge")
        self.assertIsInstance(node, DogeNode)

    def test_create_from_network_invalid(self):
        with self.assertRaises(ValueError):
            create_node_from_network("invalid_network")


    def test_validate_all_data_samples_invalid(self):
        node = create_node_from_network("bitcoin")
        data_samples = [1] * 8
        result = node.validate_all_data_samples(data_samples)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
