def merge_sort(items, key, reverse=False):
    if len(items) <= 1:
        return list(items)
    middle = len(items) // 2
    left = merge_sort(items[:middle], key, reverse)
    right = merge_sort(items[middle:], key, reverse)
    result, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        take_left = a >= b if reverse else a <= b
        if take_left:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
