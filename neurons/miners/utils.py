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
    if not isinstance(numbers, list) or not all(isinstance(i, int) for i in numbers):
        return "Invalid input"
    if not numbers:
        return []
    sorted_numbers = sorted(set(numbers))  # removing duplicates with set
    ranges = []
    start = end = sorted_numbers[0]
    for number in sorted_numbers[1:]:
        if number == end + 1:
            end = number
        else:
            ranges.append({"start_block_height": start, "end_block_height": end})
            start = end = number
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


def next_largest_excluded(block_ranges, number):
    res = number
    if not block_ranges:
        res = 1

    for block_range in block_ranges:
        if block_range['start_block_height'] <= number <= block_range['end_block_height']:
            res = block_range['end_block_height'] + 1

    return res


def get_ranges_from_block_heights(block_heights):
    result = []
    start = block_heights[0]
    end = start

    # Iterate over the list of integers
    for i in range(1, len(block_heights)):
        # Check if the current integer is consecutive
        if block_heights[i] == end + 1:
            end = block_heights[i]
        else:
            # If not consecutive, save the previous range and start a new one
            result.append({'start_block_height': start, 'end_block_height': end})
            start = block_heights[i]
            end = start

    return result


def range_equality(first, second):
    if len(first) != len(second):
        return False
    for i in range(len(first)):
        if first[i] != second[i]:
            return False
    return True

