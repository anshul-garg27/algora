def nearest_palindrome(n: str) -> str:
    L = len(n)
    num = int(n)

    candidates = set()
    # Boundary candidate 1: all 9s with L-1 digits (e.g. 99, 999) -> handles 1000 -> 999
    candidates.add(10 ** (L - 1) - 1)
    # Boundary candidate 2: 1 0...0 1 form = 10^L + 1 (e.g. 101, 1001) -> handles 99 -> 101
    candidates.add(10 ** L + 1)

    # Middle candidates from prefix-1, prefix, prefix+1
    prefix = int(n[: (L + 1) // 2])
    for p in (prefix - 1, prefix, prefix + 1):
        if p < 0:
            continue  # boundary candidates already cover this region
        s = str(p)
        if L % 2 == 0:
            pal = s + s[::-1]            # even length: full mirror
        else:
            pal = s + s[-2::-1]          # odd length: don't duplicate the middle digit
        candidates.add(int(pal))

    candidates.discard(num)                    # cannot return n itself
    candidates = {c for c in candidates if c >= 0}

    best = None
    for c in candidates:
        if best is None:
            best = c
            continue
        d_c, d_b = abs(c - num), abs(best - num)
        if d_c < d_b or (d_c == d_b and c < best):   # closer, or tie -> smaller
            best = c
    return str(best)


# ---- tests ----
checks = {
    "123": "121", "1": "0", "10": "9", "1000": "999",
    "0": "1", "11": "9",
}
for k, v in checks.items():
    got = nearest_palindrome(k)
    print(k, "->", got, "OK" if got == v else f"EXPECTED {v}")

print("18 nines:", nearest_palindrome("999999999999999999"))
print("1e17     :", nearest_palindrome("100000000000000000"))

# brute force validation
def is_pal(x):
    s = str(x); return s == s[::-1]

def brute(n):
    num = int(n)
    for d in range(0, 10**6):
        for cand in ((num - d, num + d) if d else (num,)):
            if cand >= 0 and cand != num and is_pal(cand):
                return str(cand)
    return None

import random
ok = True
for _ in range(30000):
    x = random.randint(0, 200000)
    if nearest_palindrome(str(x)) != brute(str(x)):
        print("MISMATCH", x, nearest_palindrome(str(x)), brute(str(x)))
        ok = False; break
print("random ok:", ok)
