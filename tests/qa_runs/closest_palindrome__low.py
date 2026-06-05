def nearest_palindrome(n: str) -> str:
    L = len(n)
    num = int(n)
    candidates = set()

    # --- Boundary specials (handle digit-length crossings) ---
    # Largest (L-1)-digit palindrome = all nines: 9, 99, 999...
    candidates.add(10**(L - 1) - 1)
    # Smallest (L+1)-digit palindrome = 10...01: 11(for L=1->11), 101, 1001...
    candidates.add(10**L + 1)

    # --- Mirror-based candidates ---
    # A palindrome is fixed by its left half (ceil(L/2) digits).
    prefix = int(n[:(L + 1) // 2])
    for p in (prefix - 1, prefix, prefix + 1):
        s = str(p)
        if L % 2 == 0:
            pal = s + s[::-1]        # even length: full mirror
        else:
            pal = s + s[-2::-1]      # odd length: don't duplicate middle digit
        candidates.add(int(pal))

    # The answer must differ from n itself
    candidates.discard(num)

    # Pick closest; tie -> smaller value
    best = None
    for c in candidates:
        if c < 0:
            continue
        if (best is None
                or abs(c - num) < abs(best - num)
                or (abs(c - num) == abs(best - num) and c < best)):
            best = c
    return str(best)
