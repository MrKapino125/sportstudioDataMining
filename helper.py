#mostly created by chatGPT

def str_to_int(string):
    string_without_dots = string.replace('.', '')
    return int(string_without_dots)


def add_dots_to_int(integer):
    # Convert the integer to a string
    string_without_dots = str(integer)

    # Calculate the position to start adding dots
    num_digits = len(string_without_dots)
    num_dots = (num_digits - 1) // 3

    # Initialize the result string
    result = ''

    # Calculate the number of digits before the first dot
    first_part_length = num_digits % 3 if num_digits % 3 != 0 else 3

    # Add the first part of the string (which might not have 3 digits)
    result += string_without_dots[:first_part_length]

    # Add dots and the remaining parts of the string
    for i in range(first_part_length, num_digits, 3):
        result += '.' + string_without_dots[i:i + 3]

    return result


def sort_dict_by_values_and_games(means, games):
    greater_than_5 = {}
    less_than_or_equal_5 = {}

    for club, value in means.items():
        if games.get(club, 0) > 5:
            greater_than_5[club] = value
        else:
            less_than_or_equal_5[club] = value

    sorted_greater_than_5 = dict(sorted(greater_than_5.items(), key=lambda x: x[1], reverse=True))
    sorted_less_than_or_equal_5 = dict(sorted(less_than_or_equal_5.items(), key=lambda x: x[1], reverse=True))

    return {**sorted_greater_than_5, **sorted_less_than_or_equal_5}
