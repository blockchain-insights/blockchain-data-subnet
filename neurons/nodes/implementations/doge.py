from neurons.nodes.abstract_node import Node

class DogeNode(Node):
    def __init__(self):
        pass


    def get_current_block_height(self):
        raise NotImplementedError()

    
    def get_block_by_height(self, block_height):
        raise NotImplementedError()


    def validate_data_sample(self, data_sample):
        raise NotImplementedError()

        