query_schema = """
A user asks about bitcoin transactions in natural language.
I want to convert the natural language query into a pre-defined query structure.
It will be a JSON object that is used for query search.
The query object structure is as follows.
{
  "type": <str> // type of query ("search" | "flow" | "aggregation" | null),
  "target": <str> ("Transaction" | null) // target,
  "where": <conditional object>,
  "limit": <int>, // number of results to return
  "skip": <int>, // always return 0
}

You first need to determine the type of the query.
The type can be one of "search", "flow", "aggregation", or null.
If the type is "search", you need to define the target to search.
It can be "Transaction", "Address" or null.
If you determine the target, you need to determine the conditional object.
The "where" conditional object for the target "Transaction" looks like this;
{
  "from_address": <str> // address from which the transaction goes
  "to_address": <str> // address to which the transaction goes
  "tx_id": <str> // transaction id
  "block_height_range": { // block height range
    "from": <int> // starting block height
    "to": <int> // ending block height
  }
  "amount_range": { // transaction amount range
    "from": <int> // starting amount
    "to": <int> // ending amount
  }
  "timestamp_range": { // transaction timestamp range
    "from": <int> // starting timestamp
    "to": <int> // ending timestamp
  }
}
The "where" conditional object for the target "Address" looks like this;
{
  "balance_range": { // account balance range
    "from": <int> // starting balance
    "to": <int> // ending balance
  }
}
Then, you need to determine "limit", which refers to how many results the user wants to get. If the user doesn't specify it, set it null.
You need to remove all the keys with value None in the generated JSON.
"""