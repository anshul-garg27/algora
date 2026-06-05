def nearest_palindrome(n: str) -> str:
    L = len(n)
    num = int(n)

    candidates = set()
    # --- Boundary candidates (handle a change in digit count) ---
    candidates.add(10 ** (L - 1) - 1)   # all nines, one digit shorter: 9, 99, 999...
    candidates.add(10 ** L + 1)         # 10...01, one digit longer: 11, 101, 1001...

    # --- Prefix candidates: mirror (prefix-1), prefix, (prefix+1) ---
    # The first ceil(L/2) digits fully determine a palindrome of length L.
    prefix = int(n[:(L + 1) // 2])
    for d in (-1, 0, 1):
        p = str(prefix + d)
        if L % 2 == 0:
            cand = p + p[::-1]          # even length: mirror whole prefix
        else:
            cand = p + p[-2::-1]        # odd length: skip prefix's last (middle) digit
        if cand and not cand.startswith('-'):
            candidates.add(int(cand))

    # Result must differ from n, and must be non-negative.
    candidates.discard(num)
    candidates = [c for c in candidates if c >= 0]

    # Closest by absolute difference; tie -> smaller value.
    best = min(candidates, key=lambda c: (abs(c - num), c))
    return str(best)
