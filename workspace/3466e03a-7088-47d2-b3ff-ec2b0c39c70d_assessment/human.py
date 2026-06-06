import sys

def countBalancedNumbers(p):
    n = len(p)
    pos = [0] * (n + 1)
    for i in range(n):
        pos[p[i]] = i

    lo = pos[1]
    hi = pos[1]
    ans = ['1']
    for k in range(2, n + 1):
        x = pos[k]
        if x < lo:
            lo = x
        elif x > hi:
            hi = x
        ans.append('1' if hi - lo == k - 1 else '0')
    return ''.join(ans)


if __name__ == '__main__':
    data = sys.stdin.read().split()
    n = int(data[0])
    p = list(map(int, data[1:1 + n]))
    print(countBalancedNumbers(p))
