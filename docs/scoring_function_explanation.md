# Blockchain Insight Scoring Function

## Scoring Function Overview

Our scoring function is designed to provide a comprehensive evaluation of blockchain data through multiple key metrics:

- **Block Height Coverage ($s_{1}$):** Indicates the percentage of block coverage, offering insights into the comprehensiveness of the blockchain data.

- **Recency of Block ($s_{2}$):** Reflects the recency of the most recent block, helping users gauge the timeliness of the blockchain data.

- **Response Time ($s_{3}$):** Measures the time it takes to respond, serving as a crucial indicator of the blockchain's efficiency and responsiveness.

- **Weight Based on the Mined Blockchain ($s_{4}$):** Considers the specific blockchain mined (e.g., bitcoin, doge, etc.), providing contextual relevance to the scoring process.

### Scoring Formula

The overall score is determined by the weighted sum of these four scores, where $w_i$ represents the weight assigned to each respective metric. The formula is expressed as:

$$
\text{score} = \frac{\sum_{i=1}^{4} w_{i} \cdot s_{i}}{\sum_{i=1}^{4} w_{i}}$$

This formula encapsulates the essence of our scoring mechanism, offering a balanced and informative evaluation of blockchain insights.

### Weight Assignments

Currently, the weights are as follows:

- $(w_{1} = 15)$: Block Height Coverage
- $(w_{2} = 25)$: Recency of Block
- $(w_{3} = 10)$: Response Time
- $(w_{4} = 2)$ : Weight Based on the Mined Blockchain (bitcoin, ethereum, etc.)
- $(w_{5} = 49)$: Uptime

In other words, to achieve the highest possible score, a miner should index a broad range of recent blocks from a significant blockchain (such as bitcoin) and respond promptly.

## Safeguards to Ensure Miner Decentralization

To uphold decentralization within our network, we've established the following safeguards to prevent any participant from running more than 9 instances:

Any participant meeting the following criteria will receive a score of 0:

- Usage of an IP address by more than 9 miners
- Usage of a cold key by more than 9 miners

As our subnet expands to encompass other blockchains, we're devising a gradual reduction in this number to facilitate an increase in the number of memgraph instances.

## Score 0 if one of theses metrics are not met:

It's crucial to be aware that:

- A range of blocks less than 800'000 will result in a score of 0.

- A timeout response will result in a score of 0.

- Incorrect response to a query give a score of 0.

- The weights and the minimum range of blocks can be modified as network capabilities increase

## Uptime

Uptime is calculated on the time that a miner answer a query of any type and gives an exact value to the query.

Eachtime a miner timeout or gives an incorrect answer it's considered down and will be up only when the next query will not timeout and give a correct value

An Average of the following metrics are averaged:
- Uptime for the last 24 hours 
- Uptime for the last week (7 days)
- Uptime for the last Month (30 days)

## Deep Dive

### Scoring Function Implementation

Our scoring function is implemented through a set of Python functions to assess various aspects of blockchain data. Let's break down how each component contributes to the overall score.

### Block Height Coverage ($s_{1}$) Calculation

The `Block Height Coverage` function evaluates the coverage of indexed blocks within a blockchain. It considers the number of blocks covered as well as the minimum required blocks.

The function is illustrated in the graph below
<p align="center">
  <img src="./imgs/scoring/block_height_function.png" />
</p>

### Recency of Block ($s_{2}$) Calculation

`Recency of Block` measures the difference between the indexed end block height and the current blockchain block height. This function take into account the recency of the miner's last index block with respect to the most recent block of the worst performing miner. The final recency score is based on this difference.

The function is illustrated in the graph below

<p align="center">
  <img src="./imgs/scoring/recency_score_function.png" />
</p>

### Response Time ($s_{3}$) Calculation

The `Response Time` function calculates the response time score based on the process time and discovery timeout. It considers the ratio of process time to timeout and squares it to emphasize the impact of longer processing times.

The function is illustrated in the graph below

<p align="center">
  <img src="./imgs/scoring/process_time_function.png" />
</p>


### Weight Based on the Mined Blockchain ($s_{4}$) Calculation

The `Weight Based on the Mined Blockchain` function assigns a weight to the blockchain based on its importance and distribution among miners. The overall score is a combination of the network's importance and the distribution score.

The function is illustrated in the graph below

<p align="center">
  <img src="./imgs/scoring/blockchain_weight.png" />
</p>

----

In summary, the scoring function evaluates blockchain data based on the coverage, recency, response time, and the significance of the mined blockchain to provide a comprehensive and informative score.

## Further Work and Improvement

We understand the critical importance of fostering an evenly distributed miner incentivization system, as it significantly impacts the competitiveness and overall quality of our subnet. Given that blockchain miners operate within deterministic parameters, where responses are categorized as either correct or incorrect, our scoring mechanisms must prioritize miner performance.

To achieve this, we are planning to integrate the following components into our incentive structure:

- [ ] **Weights scoring for Organic Queries:** Organic queries will have 2x the weights of syntheric queries by integrating a receipt system that validators sign for organic queries.
- [ ] **Hardware metrics:** By incorporating hardware-specific data, we can assess the performance of miners in relation to their hardware capabilities.
- [ ] **Responses quality to organic queries:** Evaluating how effectively miners respond to real-world queries will provide valuable insights into their exactitude.
- [ ] **Dynamic weighting for scoring function:** Introducing adaptability into our scoring mechanism will allow for more nuanced evaluations.

### LLM (Large Language Model)

Additionally, with the new introduction of LLM (Large Language Models) capabilities on the miner side, we anticipate further enhancements to our scoring function, incorporating stochastic features such as:

- [ ] **Quality of query response explanations:** Assessing the clarity and depth of explanations provided alongside query responses.
- [ ] **LLM capability to answer user queries:** Leveraging multilingual and complexity-handling capabilities to improve response quality.
- [ ] **Scoring Tokens/sec:** Giving an indication of the performance of the miner and quality of the API used for the LLM Prompting and response.

By integrating these elements, we aim to create a robust and comprehensive incentivization framework that drives continual improvement in miner performance and fosters a vibrant and competitive ecosystem within our subnet.
