import traceback
from collections import Counter
from random import shuffle, randint
from typing import List, Tuple, Dict

import numpy as np
from sklearn.cluster import KMeans

import bittensor as bt
from insights import protocol
from insights.protocol import DiscoveryOutput, Discovery


class BenchmarkValidator:
    def __init__(self, dendrite, validator_config):
        self.dendrite = dendrite
        self.validator_config = validator_config

    def run_benchmarks(self, filtered_responses):
        bt.logging.info(f"Starting benchmarking for {len(filtered_responses)} filtered responses.")
        response_processor = ResponseProcessor(self.validator_config)
        grouped_responses = response_processor.group_responses(filtered_responses)
        bt.logging.info(f"Grouped responses into {len(grouped_responses)} groups.")
        results = {}

        for network, main_group in grouped_responses.items():
            for label, group_info in main_group.items():
                benchmark_query_script = self.validator_config.get_benchmark_query_script(network).strip()
                for chunk in group_info['responses']:
                    benchmark_query_script_vars = {
                        'network': network,
                        'start_block': group_info['common_start'],
                        'end_block': group_info['common_end'],
                        'diff': self.validator_config.benchmark_query_diff - randint(0, 100),
                    }
                    exec(benchmark_query_script, benchmark_query_script_vars)
                    benchmark_query = benchmark_query_script_vars['query']
                    benchmark_results = self.execute_benchmarks(chunk, benchmark_query)

                    if benchmark_results:
                        try:
                            filtered_result = [response_output for _, _, response_output in benchmark_results]
                            most_common_result, _ = Counter(filtered_result).most_common(1)[0]
                            for uid_value, response_time, result in benchmark_results:
                                results[uid_value] = (response_time, result == most_common_result)
                        except Exception as e:
                            bt.logging.error(f"Error occurred during benchmarking: {traceback.format_exc()}")

        return results

    def execute_benchmarks(self, responses, benchmark_query):
        bt.logging.info(f"Executing {benchmark_query=} query for {len(responses)} responses.")
        results = []
        for response, uid in responses:
            result = self.run_benchmark(response, uid, benchmark_query)
            results.append(result)

        filtered_run_results = [result for result in results if result[2] is not None]
        bt.logging.info(f"Filtered {len(filtered_run_results)} valid benchmark results.")
        return filtered_run_results

    def run_benchmark(self, response, uid, benchmark_query="RETURN 1"):
        try:
            uid_value = uid.item() if uid.numel() == 1 else int(uid.numpy())
            output = response.output
            benchmark_response = self.dendrite.query(
                response.axon,
                protocol.Benchmark(network=output.metadata.network, query=benchmark_query),
                deserialize=False,
                timeout=self.validator_config.benchmark_timeout,
            )

            if benchmark_response is None or benchmark_response.output is None:
                bt.logging.debug(f"Benchmark validation failed for {response.axon.hotkey}")
                return None, None, None

            response_time = benchmark_response.dendrite.process_time
            bt.logging.info(f"Benchmark validation passed for {response.axon.hotkey} with response time {response_time}, output: {benchmark_response.output}, uid: {uid_value}")
            return uid_value, response_time, benchmark_response.output
        except Exception as e:
            bt.logging.error(f"Error occurred during benchmarking {response.axon.hotkey}: {traceback.format_exc()}")
            return None, None, None

class ResponseProcessor:
    def __init__(self, validator_config):
        self.validator_config = validator_config

    def group_responses(self, responses):
        network_grouped_responses = {}
        for resp, uid in responses:
            net = resp.output.metadata.network
            network_grouped_responses.setdefault(net, []).append((resp, uid))

        new_groups = {}
        chunk_size = self.validator_config.benchmark_query_chunk_size
        for network, items in network_grouped_responses.items():
            data = np.array([(resp.output.start_block_height, resp.output.block_height) for resp, _ in items])
            try:
                kmeans = KMeans(n_clusters=self.validator_config.benchmark_cluster_size, random_state=0).fit(data)
                labels = kmeans.labels_
            except ValueError as e:
                bt.logging.error(f"Error clustering data for network {network}: {e}")
                continue

            grouped_responses = {}
            for label, item in zip(labels, items):
                grouped_responses.setdefault(label, []).append(item)

            for label, group in grouped_responses.items():
                shuffle(group)
                chunked_groups = []
                ip_to_chunk_map = {}

                for resp, uid in group:
                    resp_ip = resp.axon.ip
                    if resp_ip in ip_to_chunk_map:
                        chunked_groups[ip_to_chunk_map[resp_ip]].append((resp, uid))
                    else:
                        # Assign to a new or existing chunk that hasn't reached size limit
                        placed = False
                        for idx, chunk in enumerate(chunked_groups):
                            if len(chunk) < chunk_size:
                                chunk.append((resp, uid))
                                ip_to_chunk_map[resp_ip] = idx
                                placed = True
                                break
                        if not placed:
                            chunked_groups.append([(resp, uid)])
                            ip_to_chunk_map[resp_ip] = len(chunked_groups) - 1

                min_start = min(resp.output.start_block_height for resp, uid in group)
                min_end = min(resp.output.block_height for resp, uid in group)
                new_groups.setdefault(network, {})[label] = {
                    'common_start': min_start,
                    'common_end': min_end,
                    'responses': chunked_groups,
                }

                bt.logging.info(f"Grouped {len(group)} responses for network {network} with label {label} into {len(chunked_groups)} chunks. Common start: {min_start}, common end: {min_end}.")

        for i in new_groups:
            for j in new_groups[i]:
                idx = 0
                for response in new_groups[i][j]['responses']:
                    details = [(response.axon.ip, response.axon.hotkey) for (response, uid) in response]
                    bt.logging.info(f"Network {network}, Label {label}, Chunk {idx+1}: Contains Responses {details}")

        return new_groups