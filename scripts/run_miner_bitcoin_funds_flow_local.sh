#!/bin/bash
cd "$(dirname "$0")/../"
echo "$PWD"

export PYTHONPATH=$PWD

if [ -z "$NETUID" ]; then
    export NETUID=1
fi

if [ -z "$WALLET_NAME" ]; then
    export WALLET_NAME=miner
fi

if [ -z "$WALLET_HOTKEY" ]; then
    export WALLET_HOTKEY=default
fi

if [ -z "$GRAPH_DB_URL" ]; then
    export GRAPH_DB_URL="bolt://localhost:7687"
fi

if [ -z "$GRAPH_DB_USER" ]; then
    export GRAPH_DB_USER=""
fi

if [ -z "$GRAPH_DB_PASSWORD" ]; then
    export GRAPH_DB_PASSWORD=""
fi

if [ -z "$SUBTENSOR_CHAIN_ENDPOINT" ]; then
    export SUBTENSOR_CHAIN_ENDPOINT="ws://0.0.0.0:9944"
fi

if [ -z "$WAIT_FOR_SYNC" ]; then
    export WAIT_FOR_SYNC="True"
fi

if [ -z "$BITCOIN_NODE_RPC_URL" ]; then
    export BITCOIN_NODE_RPC_URL="http://bitcoinrpc:rpcpassword@127.0.0.1:8332"
fi

python3 neurons/miners/miner.py --network bitcoin --model_type funds_flow --wallet.name "$WALLET_NAME" --wallet.hotkey "$WALLET_HOTKEY" --netuid "$NETUID" --subtensor.chain_endpoint "$SUBTENSOR_CHAIN_ENDPOINT" --logging.debug --logging.trace
