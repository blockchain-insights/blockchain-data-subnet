import json
import traceback
from collections import Counter
from random import randint

from protocols.llm_engine import MODEL_TYPE_BALANCE_TRACKING, MODEL_TYPE_FUNDS_FLOW

from insights import protocol
from neurons import logger
import numpy as np


class BenchmarkValidator:
    def __init__(self, dendrite, validator_config):
        self.dendrite = dendrite
        self.validator_config = validator_config

    def run_benchmarks(self, filtered_responses):
        try:
            response_processor = ResponseProcessor(self.validator_config)
            grouped_responses = response_processor.group_responses(filtered_responses)
            logger.info("Run benchmarks", groups=len(grouped_responses))
            results = {}

            for network, main_group in grouped_responses.items():
                for label, group_info in main_group.items():
                    benchmark_query_script_vars = {
                        'network': network,
                        'start_block': group_info['common_start'],
                        'end_block': group_info['common_end'],
                        'balance_end': group_info['balance_end'],
                        'diff': self.validator_config.benchmark_funds_flow_query_diff - randint(0, 100),
                    }
                    responses = group_info['responses']
                    self.run_benchmark_type(MODEL_TYPE_FUNDS_FLOW, self.validator_config.get_benchmark_funds_flow_query_script(network).strip(), benchmark_query_script_vars, responses, results)

            for network, main_group in grouped_responses.items():
                for label, group_info in main_group.items():
                    benchmark_query_script_vars = {
                        'network': network,
                        'start_block': group_info['common_start'],
                        'end_block': group_info['common_end'],
                        'balance_end': group_info['balance_end'],
                        'diff': self.validator_config.benchmark_balance_tracking_query_diff - randint(0, 100),
                    }
                    responses = group_info['responses']
                    self.run_benchmark_type(MODEL_TYPE_BALANCE_TRACKING, self.validator_config.get_benchmark_balance_tracking_script(network).strip(), benchmark_query_script_vars, responses, results)

            return results
        except Exception as e:
            logger.error("Run benchmark failed", error=traceback.format_exc())
            return {}

    def run_benchmark_type(self, benchmark_type, benchmark_query_script, benchmark_query_script_vars, responses, results):
        exec(benchmark_query_script, benchmark_query_script_vars)
        benchmark_query = benchmark_query_script_vars['query']
        benchmark_results = self.execute_benchmarks(responses, benchmark_query, benchmark_type)

        if benchmark_results:
            try:
                filtered_result = [response_output for _, _, response_output in benchmark_results]
                most_common_result, _ = Counter(filtered_result).most_common(1)[0]
                for uid_value, response_time, result in benchmark_results:
                    if uid_value not in results:
                        results[uid_value] = {}
                    results[uid_value][benchmark_type] = (response_time, result == most_common_result)

                    if benchmark_type == MODEL_TYPE_BALANCE_TRACKING:
                        logger.info("DEBUG - run_benchmark_type ", responses=[{'miner_hotkey': r.axon.hotkey, 'last_block': r.output.balance_model_last_block} for r, _ in responses if r.output is not None] , results=results)

            except Exception as e:
                logger.error(f"Run benchmark failed", benchmark_type = benchmark_type, error=traceback.format_exc())

    def execute_benchmarks(self, responses, benchmark_query, query_type):
        results = []
        for response, uid in responses:
            result = self.run_benchmark(response, uid, benchmark_query, query_type)
            results.append(result)

        filtered_run_results = [result for result in results if result[2] is not None]
        logger.info("Executing benchmark", responses=len(responses), results=len(filtered_run_results), benchmark_query=benchmark_query)
        return filtered_run_results

    def run_benchmark(self, response, uid, benchmark_query="RETURN 1", query_type=MODEL_TYPE_FUNDS_FLOW):
        try:
            uid_value = int(uid) if isinstance(uid, np.ndarray) and uid.size == 1 else int(uid)
            output = response.output
            benchmark_response = self.dendrite.query(
                response.axon,
                protocol.Benchmark(network=output.metadata.network, query=benchmark_query, query_type=query_type),
                deserialize=False,
                timeout=self.validator_config.benchmark_timeout,
            )

            if benchmark_response is None or benchmark_response.output is None:
                logger.info("Run benchmark failed", miner_hotkey=response.axon.hotkey, miner_uid = uid_value, miner_ip = response.axon.ip, reason = "benchmark timed out")
                return None, None, None

            response_time = benchmark_response.dendrite.process_time
            logger.info("Run benchmark", miner_hotkey=response.axon.hotkey, response_time=response_time, output=benchmark_response.output, miner_uid=uid_value, miner_ip = response.axon.ip)
            return uid_value, response_time, benchmark_response.output
        except Exception as e:
            logger.error("Run benchmark failed", error=traceback.format_exc(), reason="exception", miner_hotkey=response.axon.hotkey, miner_uid = uid_value, miner_ip = response.axon.ip)
            return None, None, None


class ResponseProcessor:
    def __init__(self, validator_config):
        self.validator_config = validator_config

    def group_responses(self, responses):
        network_grouped_responses = {}
        for resp, uid in responses:
            net = resp.output.metadata.network
            network_grouped_responses.setdefault(net, []).append((resp, uid))

        chunk_size = self.validator_config.benchmark_query_chunk_size

        for network, items in network_grouped_responses.items():
            sorted_by_ip = sorted(items, key=lambda x: x[0].axon.ip)
            chunks = [[] for _ in range(chunk_size)]  # 5 lists to store chunk
            for i in range(len(sorted_by_ip)):
                group = sorted_by_ip[i]
                chunk_index = i % chunk_size
                chunks[chunk_index].append(group)
            network_grouped_responses[network] = [chunk for chunk in chunks if len(chunk) > 0]

        new_groups = {}

        for network, items in network_grouped_responses.items():
            for i in range(len(items)):
                min_start = min(resp.output.start_block_height for resp, _ in items[i])
                min_end = min(resp.output.block_height for resp, _ in items[i])
                balance_end = min(resp.output.balance_model_last_block for resp, _ in items[i])
                new_groups.setdefault(network, {})[i] = {
                    'common_start': min_start,
                    'common_end': min_end,
                    'balance_end': balance_end,
                    'responses': [resp for resp in items[i]]
                }

                logger.info("Benchmark group", network=network, chunk=i, start=min_start, end=min_end, groups=f"{[(resp.axon.ip, resp.axon.hotkey) for resp, _ in items[i]]}")

        return new_groups
