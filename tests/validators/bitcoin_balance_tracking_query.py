

def build_balance_tracking_query(network, start_block, balance_end, diff=1):
    import random
    total_blocks = balance_end - start_block
    part_size = total_blocks // 8
    range_clauses = []

    for i in range(8):
        part_start = start_block + i * part_size
        if i == 7:
            part_end = balance_end
        else:
            part_end = start_block + (i + 1) * part_size - 1

        if (part_end - part_start) > diff:
            sub_range_start = random.randint(part_start, part_end - diff)
        else:
            sub_range_start = part_start

        sub_range_end = sub_range_start + diff
        range_clauses.append(f"SELECT generate_series({sub_range_start}, {sub_range_end}) AS block")

    combined_ranges = " UNION ALL ".join(range_clauses)

    final_query = f"""
    WITH block_heights AS (
        {combined_ranges}
    )
    SELECT SUM(block) 
    FROM balance_changes 
    WHERE block IN (SELECT block FROM block_heights)
    """
    query = final_query.strip()
    return query
