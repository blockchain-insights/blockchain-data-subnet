def find_gaps_in_ranges(ranges):
    # Sort the ranges by starting block
    sorted_ranges = sorted(ranges, key=lambda x: x["start_block_height"])
    # Initialize variables
    gaps = []
    previous_end = None
    # Iterate through the ranges to find gaps
    for rn in sorted_ranges:
        if previous_end is not None and rn["start_block_height"] > previous_end + 1:
            # Found a gap
            gaps.append(
                {
                    "start_block_height": previous_end + 1,
                    "end_block_height": rn["start_block_height"] - 1,
                }
            )
        previous_end = rn["end_block_height"]
    return gaps


def create_ranges_from_list(numbers):
    if not numbers:
        return []
    # Sort the list
    sorted_numbers = sorted(numbers)
    # Initialize the first range
    ranges = []
    start = sorted_numbers[0]
    end = start
    # Iterate through the list
    for number in sorted_numbers[1:]:
        if number == end + 1:
            # Continue the range
            end = number
        else:
            # End the current range and start a new one
            ranges.append({"start_block_height": start, "end_block_height": end})
            start = end = number
    # Add the last range
    ranges.append({"start_block_height": start, "end_block_height": end})
    return ranges


def subtract_ranges_from_large_range(max_height, ranges):
    # Sort the ranges by their start heights
    sorted_ranges = sorted(ranges, key=lambda x: x["start_block_height"])
    # Initialize the current height
    current_height = 1
    # Store the remaining numbers
    remaining_numbers = []
    # Iterate through the ranges
    for block_range in sorted_ranges:
        start, end = block_range["start_block_height"], block_range["end_block_height"]
        # Add the gap between the current height and the start of the range
        remaining_numbers.extend(range(current_height, start))
        # Update the current height to be the end of this range
        current_height = end + 1
    # Add remaining numbers after the last range
    remaining_numbers.extend(range(current_height, max_height + 1))
    return remaining_numbers


def total_items_in_ranges(ranges):
    total_count = 0
    for rn in ranges:
        count = rn["end_block_height"] - rn["start_block_height"] + 1
        total_count += count
    return total_count


def remove_specific_integers(array, integers_to_remove):
    return [x for x in array if x not in integers_to_remove]
