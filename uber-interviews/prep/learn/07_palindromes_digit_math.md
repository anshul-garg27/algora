# LEARN: Palindromes & Digit Math — Uber's odd little obsession

*Why this matters: 4 distinct palindrome questions ran at Uber last year —
Closest Palindrome 3x (incl. a bar-raiser), Next Palindrome > N, Minimum
Appends to Make Palindrome, Longest Palindromic Substring. Cheap points if
drilled; an edge-case bloodbath if not.*

## The mental model: palindromes are determined by their LEFT HALF

Take n = `12345`. Any palindrome "shaped like" n is the left half `123`
mirrored: `12321`. That's the whole trick — you never search numbers, you
search **halves**, and there are only a handful of relevant ones.

Mirroring code (memorize the parity handling):
```python
s = str(half)
pal_even = s + s[::-1]        # "12" -> "1221"
pal_odd  = s + s[-2::-1]      # "123" -> "12321"  (middle digit not doubled)
```

## Closest Palindrome — the candidate-set method (the ONLY safe way)

Why ad-hoc digit surgery fails: the answer can come from THREE different
"families", and patching cases one by one (what most candidates do) always
misses one. The bar-raiser probes exactly those misses.

The 5 candidates (for n with L digits, half = first ⌈L/2⌉ digits):
1. mirror(half) — same shape
2. mirror(half − 1) — e.g., 12345 → 12221  (covers "round down")
3. mirror(half + 1) — e.g., 12345 → 12421  (covers "round up")
4. 10^(L−1) − 1 = 99…9 (one digit SHORTER — covers 1000 → 999)
5. 10^L + 1 = 10…01 (one digit LONGER — covers 99 → 101)

Then: drop n itself, pick min by `(abs(c − n), c)` — the tuple handles the
tie→smaller rule for free. Full code: `../solutions/dp_math.py`.

Walk these by hand ONCE each (they're the interviewer's probe list):
`"10"→9, "11"→9, "99"→101, "100"→99, "1000"→999, "1"→0, "12121"→12021`.

Why candidates 2/3 need the boundary candidates 4/5 as backup: decrementing
the half can shrink it (`10`→`9`), and the naive mirror of `"9"` doesn't have
the right length — 99…9 catches every such case. Say this when asked "prove
your set is sufficient."

## Next palindrome strictly greater than N (asked at Uber as its own question)

Same machinery, smaller set: {mirror(half), mirror(half+1), 10^L + 1},
keep only candidates > N, take min. Example from the round: 123 → 131.

## Minimum appends to make a palindrome (Uber phone screen)

> Append characters at the END of s to make it a palindrome; minimize count.

Reframe (the unlock): find the **longest palindromic SUFFIX** of s; everything
before it must be mirrored and appended. `"google"` → longest pal suffix is
`"e"`? No — check: suffixes `e, le, gle, ogle, oogle, google`; longest
palindromic one is `"e"`... wait, `"gog"` isn't a suffix. Answer = len(s) −
len(longest pal suffix) = 5. Brute O(n²) check is interview-fine; mention
KMP on `reverse(s) + '#' + s` for O(n) as the optimization.
(Mirror question — appends at FRONT → longest palindromic PREFIX.)

## Longest Palindromic Substring (senior coding round, 2025-12)

Expand-around-center, O(n²)/O(1) — the right interview answer. For each of
the 2n−1 centers (letters + gaps), expand while equal. Mentioning "Manacher
exists, O(n), I wouldn't code it here" = senior polish, zero risk.

```python
def longest_pal(s):
    best = ""
    for c in range(2 * len(s) - 1):
        l, r = c // 2, c // 2 + (c % 2)
        while l >= 0 and r < len(s) and s[l] == s[r]:
            l -= 1; r += 1
        if r - l - 1 > len(best):
            best = s[l + 1:r]
    return best
```

## Mistakes that cost offers

- Walking ±1 from n checking is-palindrome — O(n) per step, dies on 18-digit
  inputs; the bar-raiser asks for big inputs specifically to kill this.
- Forgetting "answer ≠ n itself" when n is already a palindrome.
- Mixing up which half mirrors (always the LEFT half wins — it's the more
  significant side).
- int/str juggling bugs — convert once at the boundary, work in ONE domain.

## Practice ladder

1. LC 5 Longest Palindromic Substring
2. LC 564 Find the Closest Palindrome (drill until all 7 probe cases pass
   first try)
3. GfG Next Palindrome
4. LC 214 Shortest Palindrome (the KMP-prefix trick, mirrored)
5. Mock: `../mocks/dsa_03_closest_palindrome.py`
