import traceback
from collections import Counter
from random import randint
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
                    query_type = np.random.choice(['funds_flow', 'balance'])
                    if query_type == 'funds_flow':
                        benchmark_query_script = self.validator_config.get_benchmark_cypher_query_script(network).strip()
                    else:
                        benchmark_query_script = self.validator_config.get_benchmark_sql_query_script(network).strip()
                    benchmark_query_script_vars = {
                        'network': network,
                        'start_block': group_info['common_start'],
                        'end_block': group_info['common_end'],
                        'diff': self.validator_config.benchmark_query_diff - randint(0, 100),
                    }
                    responses = group_info['responses']
                    exec(benchmark_query_script, benchmark_query_script_vars, query_type)
                    benchmark_query = benchmark_query_script_vars['query']
                    benchmark_results = self.execute_benchmarks(responses, benchmark_query)

                    if benchmark_results:
                        try:
                            filtered_result = [response_output for _, _, response_output in benchmark_results]
                            most_common_result, _ = Counter(filtered_result).most_common(1)[0]
                            for uid_value, response_time, result in benchmark_results:
                                results[uid_value] = (response_time, result == most_common_result)
                        except Exception as e:
                            logger.error("Run benchmark failed", error=traceback.format_exc())

            return results
        except Exception as e:
            logger.error("Run benchmark failed", error=traceback.format_exc())
            return {}

    def execute_benchmarks(self, responses, benchmark_query, query_type):
        results = []
        for response, uid in responses:
            result = self.run_benchmark(response, uid, benchmark_query, query_type)
            results.append(result)

        filtered_run_results = [result for result in results if result[2] is not None]
        logger.info("Executing benchmark", responses=len(responses), results=len(filtered_run_results), benchmark_query=benchmark_query)
        return filtered_run_results

    def run_benchmark(self, response, uid, benchmark_query="RETURN 1", query_type):
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
                logger.info("Run benchmark failed", hotkey=response.axon.hotkey)
                return None, None, None

            response_time = benchmark_response.dendrite.process_time
            logger.info("Run benchmark", hotkey=response.axon.hotkey, response_time=response_time, output=benchmark_response.output, uid=uid_value)
            return uid_value, response_time, benchmark_response.output
        except Exception as e:
            logger.error("Run benchmark failed", error=traceback.format_exc())
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
                new_groups.setdefault(network, {})[i] = {
                    'common_start': min_start,
                    'common_end': min_end,
                    'responses': [resp for resp in items[i]]
                }

                logger.info("Benchmark group", network=network, chunk=i, start=min_start, end=min_end, groups=f"{[(resp.axon.ip, resp.axon.hotkey) for resp, _ in items[i]]}")

        return new_groups
