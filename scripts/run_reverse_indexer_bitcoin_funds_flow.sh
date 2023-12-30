#!/bin/bash
cd "$(dirname "$0")/../"
echo $(pwd)
export PYTHONPATH=$(pwd)

if [ -z "$BUFFER_MODE" ]; then
  export BUFFER_MODE=False
fi

if [ -z "$BUFFER_BLOCK_LIMIT"]; then
  export BUFFER_BLOCK_LIMIT=10
fi

if [ -z "$BUFFER_TX_LIMIT" ]; then
  export BUFFER_TX_LIMIT=1000
fi

if [ -z "$BITCOIN_NODE_RPC_URL" ]; then
    export BITCOIN_NODE_RPC_URL="http://daxtohujek446464:lubosztezhujek3446457@62.210.88.131:8332"
fi

if [ -z "$GRAPH_DB_URL" ]; then
    export GRAPH_DB_URL="bolt://localhost:7687"
fi

if [ -z "$GRAPH_DB_USER" ]; then
    export GRAPH_DB_USER="username"
fi

if [ -z "$GRAPH_DB_PASSWORD" ]; then
    export GRAPH_DB_PASSWORD="password"
fi

python3 neurons/miners/bitcoin/funds_flow/indexer_patch.py