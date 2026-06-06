import os, sys

# Complete the 'countBalancedNumbers' function below.
# Returns a STRING; accepts INTEGER_ARRAY p.

def countBalancedNumbers(p):
    n = len(p)
    pos = [0] * (n + 1)          # pos[value] = 0-based index of value in p
    for i, v in enumerate(p):
        pos[v] = i

    res = []
    mn = n + 1                   # running min position of values 1..k
    mx = -1                      # running max position of values 1..k
    for k in range(1, n + 1):
        idx = pos[k]
        if idx < mn:
            mn = idx
        if idx > mx:
            mx = idx
        # values 1..k are k distinct cells; contiguous iff span == k
        res.append('1' if mx - mn == k - 1 else '0')
    return ''.join(res)


if __name__ == '__main__':
    data = sys.stdin.read().split()
    idx = 0
    p_count = int(data[idx]); idx += 1
    p = [int(data[idx + i]) for i in range(p_count)]
    print(countBalancedNumbers(p))
