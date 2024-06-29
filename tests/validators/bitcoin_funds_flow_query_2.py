
def build_funds_flow_query(network, start_block, end_block, diff=1):
    import random
    total_blocks = end_block - start_block
    part_size = total_blocks // 8
    range_clauses = []
    for i in range(8):
        part_start = start_block + i * part_size
        if i == 7:
            part_end = end_block
        else:
            part_end = start_block + (i + 1) * part_size - 1
        if (part_end - part_start) > diff:
            sub_range_start = random.randint(part_start, part_end - diff)
        else:
            sub_range_start = part_start
        sub_range_end = sub_range_start + diff
        range_clauses.append(f"range({sub_range_start}, {sub_range_end})")
    combined_ranges = " + ".join(range_clauses)
    final_query = f"""
    WITH {combined_ranges} AS block_heights
    UNWIND block_heights AS block_height
    MATCH (t:Transaction)
    WHERE t.block_height = block_height
    WITH t
    MATCH (sender:Address)-[sent1:SENT]->(t)-[sent2:SENT]->(receiver:Address)
    WITH SUM(sent1.value_satoshi + sent2.value_satoshi) AS total_value, COUNT(sender) AS sender_count, COUNT(receiver) AS receiver_count, COUNT(t) AS transaction_count
    RETURN total_value + sender_count + receiver_count + transaction_count AS output
    """
    query = final_query.strip()
    return query