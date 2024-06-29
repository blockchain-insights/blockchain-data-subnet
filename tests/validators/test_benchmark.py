import inspect
import json
import re
import unittest
from random import randint
from unittest.mock import Mock
from neurons.validators.benchmark import ResponseProcessor
from tests.validators import bitcoin_funds_flow_query_2, bitcoin_funds_flow_query, bitcoin_balance_tracking_query


class BenchmarkQueryRegex(unittest.TestCase):

    def test_funds_flow_query_generation(self):
        diff = 1
        function_code = inspect.getsource(bitcoin_funds_flow_query.build_funds_flow_query) + f"\nquery = build_funds_flow_query(network, start_block, end_block, {diff})"
        with open('funds_flow_query_script.json', 'w') as file:
            json.dump({"code": function_code}, file)

        query_script = ""
        with open('funds_flow_query_script.json', 'r') as file:
            data = json.load(file)
            query_script = data['code']

        query = bitcoin_funds_flow_query.build_funds_flow_query('bitcoin', 1, 835000, diff)
        benchmark_query_script_vars = {
            'network': 'bitcoin',
            'start_block': 1,
            'end_block': 835000,
            'diff': diff,
        }

        exec(query_script, benchmark_query_script_vars)
        generated_query = benchmark_query_script_vars['query']
        print(generated_query)

        pattern = f"WITH\s+(?:range\(\d+,\s*\d+\)\s*\+\s*)*range\(\d+,\s*\d+\)\s+AS\s+block_heights\s+UNWIND\s+block_heights\s+AS\s+block_height\s+MATCH\s+p=\((sender:Address)\)-\[(sent1:SENT)\]->\((t:Transaction)\)-\[(sent2:SENT)\]->\((receiver:Address)\)\s+WHERE\s+t\.block_height\s+=\s+block_height\s+RETURN\s+SUM\(sent1\.value_satoshi\+sent2\.value_satoshi\)\s*\+\s*count\(sender\)\s*\+\s*count\(receiver\)\s*\+\s*count\(t\)\s+as\s+output"
        print(pattern)

        with open('funds_flow_query_regex.json', 'w') as file:
            json.dump({"regex": pattern}, file)

        regex = re.compile(pattern)
        match = regex.fullmatch(generated_query)

        self.assertIsNotNone(match)  # Updated assertion to check if the match is not None

    def test_funds_flow_query_generation_2(self):
        diff = 256
        function_code = inspect.getsource(bitcoin_funds_flow_query_2.build_funds_flow_query) + f"\nquery = build_funds_flow_query(network, start_block, end_block, {diff})"
        with open('funds_flow_query_script_2.json', 'w') as file:
            json.dump({"code": function_code}, file)

        query_script = ""
        with open('funds_flow_query_script_2.json', 'r') as file:
            data = json.load(file)
            query_script = data['code']

        query = bitcoin_funds_flow_query_2.build_funds_flow_query('bitcoin', 1, 835000, diff)
        benchmark_query_script_vars = {
            'network': 'bitcoin',
            'start_block': 1,
            'end_block': 835000,
            'diff': diff,
        }

        exec(query_script, benchmark_query_script_vars)
        generated_query = benchmark_query_script_vars['query']
        print(generated_query)

        pattern = r"WITH\s+(?:range\(\d+,\s*\d+\)\s*\+\s*)*range\(\d+,\s*\d+\)\s+AS\s+block_heights\s+UNWIND\s+block_heights\s+AS\s+block_height\s+MATCH\s+\(t:Transaction\)\s+WHERE\s+t\.block_height\s+=\s+block_height\s+WITH\s+t\s+MATCH\s+\(sender:Address\)-\[sent1:SENT\]->\(t\)-\[sent2:SENT\]->\(receiver:Address\)\s+WITH\s+SUM\(sent1\.value_satoshi\s*\+\s*sent2\.value_satoshi\)\s+AS\s+total_value,\s+COUNT\(sender\)\s+AS\s+sender_count,\s+COUNT\(receiver\)\s+AS\s+receiver_count,\s+COUNT\(t\)\s+AS\s+transaction_count\s+RETURN\s+total_value\s*\+\s*sender_count\s*\+\s*receiver_count\s*\+\s*transaction_count\s+AS\s+output"

        print(pattern)

        with open('funds_flow_query_regex_2.json', 'w') as file:
            json.dump({"regex": pattern}, file)

        regex = re.compile(pattern)
        match = regex.fullmatch(generated_query)

        self.assertIsNotNone(match)  # Updated assertion to check if the match is not None

    def test_balance_tracking_query_generation(self):
        diff = 256
        function_code = inspect.getsource(bitcoin_balance_tracking_query.build_balance_tracking_query) + f"\nquery = build_balance_tracking_query(network, start_block, balance_end, {diff})"
        with open('balance_tracking_query_script.json', 'w') as file:
            json.dump({"code": function_code}, file)

        query_script = ""
        with open('balance_tracking_query_script.json', 'r') as file:
            data = json.load(file)
            query_script = data['code']

        query = bitcoin_balance_tracking_query.build_balance_tracking_query('bitcoin', 1, 835000, diff)
        benchmark_query_script_vars = {
            'network': 'bitcoin',
            'start_block': 1,
            'end_block': 835000,
            'balance_end': 835000, # Changed 'end_block' to 'balance_end
            'diff': diff,
        }

        exec(query_script, benchmark_query_script_vars)
        generated_query = benchmark_query_script_vars['query']
        print(generated_query)

        pattern = "WITH\s+block_heights\s+AS\s+\(\s*SELECT\s+generate_series\(\d+,\s*\d+\)\s+AS\s+block\s+(?:UNION\s+ALL\s+SELECT\s+generate_series\(\d+,\s*\d+\)\s+AS\s+block\s+)+\)\s+SELECT\s+SUM\(\s*block\s*\)\s+FROM\s+balance_changes\s+WHERE\s+block\s+IN\s+\(SELECT\s+block\s+FROM\s+block_heights\)"
        print(pattern)

        with open('balance_query_regex.json', 'w') as file:
            json.dump({"regex": pattern}, file)

        regex = re.compile(pattern)
        match = regex.fullmatch(generated_query)

        self.assertIsNotNone(match)  # Updated assertion to check if the match is not None


class TestResponseProcessor(unittest.TestCase):
    def setUp(self):
        self.validator_config = Mock()
        self.validator_config.benchmark_query_chunk_size = 32
        self.processor = ResponseProcessor(self.validator_config)

    def generate_ips(self, num_ips):
        ips = []
        for _ in range(num_ips):
            ip = ".".join(map(str, (randint(0, 255) for _ in range(4))))
            ips.append(ip)
        return ips

    def test_group_responses(self):
        # Create mock responses
        responses = []
        ips = self.generate_ips(100)
        for i in range(len(ips)):
            response = Mock()
            response.axon.ip = ips[i]
            response.axon.hotkey = f'hotkey_{i}'
            response.output.metadata.network = 'bitcoin'
            response.output.start_block_height = i
            response.output.block_height = i + 10
            response.output.balance_model_last_block = i + 20
            responses.append((response, i))

        # Call the method under test
        result = self.processor.group_responses(responses)

        # Assert the expected output
        self.assertEqual(len(result), 1)  # Only one network 'bitcoin'
        self.assertEqual(len(result['bitcoin']), self.validator_config.benchmark_query_chunk_size)  # 5 groups
        for i, group_info in result['bitcoin'].items():
            self.assertEqual(group_info['common_start'], i)
            self.assertEqual(group_info['common_end'], i + 10)
            self.assertEqual(group_info['balance_end'], i + 20)
            self.assertEqual(len(group_info['responses']), 1)  # Each group has 1 response

if __name__ == '__main__':
    unittest.main()