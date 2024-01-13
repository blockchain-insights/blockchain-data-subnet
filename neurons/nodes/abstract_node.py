from insights.protocol import NETWORK_BITCOIN, NETWORK_DOGE

from abc import ABC, abstractmethod

import concurrent

class Node(ABC):
    def __init__(self):
       pass


    @abstractmethod
    def get_current_block_height(self):
        pass


    @abstractmethod
    def get_block_by_height(self, block_height):
        pass


    @abstractmethod
    def validate_data_sample(self, data_sample):
        pass


    def validate_all_data_samples(self, data_samples, min_samples=10):
        if len(data_samples) < min_samples:
            return False
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Creating a future for each data sample validation
            futures = [executor.submit(self.validate_data_sample(sample)) for sample in data_samples]

            for future in concurrent.futures.as_completed(futures):
                if not future.result():
                    return False  # If any data sample is invalid, return False immediately
        return True 
