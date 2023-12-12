from typing import Optional, List, Dict
import bittensor as bt
from pydantic import BaseModel, Field

# Model types
MODEL_TYPE_FUNDS_FLOW = "funds_flow"

# Networks
NETWORK_BITCOIN = "bitcoin"
NETWORK_LITECOIN = "litecoin"
NETWORK_DOGE = "doge"
NETWORK_DASH = "dash"
NETWORK_ZCASH = "zcash"
NETWORK_BITCOIN_CASH = "bitcoin_cash"

NETWORKS = [ NETWORK_BITCOIN, NETWORK_LITECOIN, NETWORK_DOGE, NETWORK_DASH, NETWORK_ZCASH, NETWORK_BITCOIN_CASH ]
MODELS = [ MODEL_TYPE_FUNDS_FLOW ]

class MinerDiscoveryMetadata(BaseModel):
    network: str = Field(..., description="Network type", enum=NETWORKS)
    model_type: str = Field(..., description="Model type", enum=MODELS)
    graph_schema: Optional[Dict] = Field(None, description="Graph schema")

class MinerDiscoveryOutput(BaseModel):
    metadata: MinerDiscoveryMetadata = Field(..., description="Metadata about the miner discovery")
    data_samples: List[Dict] = Field(..., description="List of data samples")
    block_height: int = Field(..., description="Block height")
    start_block_height: int = Field(..., description="Start block height")

class MinerDiscovery(bt.Synapse):
    output: MinerDiscoveryOutput = Field(..., description="Output of the miner discovery")

    def deserialize(self):
        return self


class MinerQuery(bt.Synapse):
    network: str = None
    model_type: str = None
    query: str = None
    output: Optional[List[Dict]] = None

    def deserialize(self) -> List[Dict]:
        return self.output


class MinerQuery(bt.Synapse):
    network: str = Field(..., description="Network type", enum=NETWORKS)
    model_type: str = Field(..., description="Model type", enum=MODELS)
    query: str = Field(..., description="Cypher Query")
    output: Optional[List[Dict]] = Field(None, description="Query output")

    def deserialize(self) -> List[Dict]:
        # Implement deserialization logic if necessary
        return self.output