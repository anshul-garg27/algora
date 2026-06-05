## 1. Problem Understanding

We're given a number as a string `n`. We need to find the **palindrome** (reads the same forwards and backwards) that is closest to `n` by absolute difference — but it must NOT equal `n` itself. If two palindromes are equally close, return the **smaller** one.

Examples: `"123" -> "121"` (121 is distance 2, the next palindrome 131 is distance 8). `"1" -> "0"` (single digits: closest different palindrome is one less).

**Clarifying questions to ask:**
- Can the answer equal `n`? → No, it must be the *closest* one that is different.
- Is `n` always non-negative? → Yes, digits only, no sign. Length 1 to 18.
- Output format — string? → Yes, return as string.
- For ties, "smaller" means smaller numeric value? → Yes.
- Can `n` have leading zeros? → Assume no (standard integer string).

> 💬 "So I need the nearest palindrome to this number, not counting the number itself, and on a tie I pick the smaller one. Let me confirm — `n` is a non-negative integer string up to 18 digits, and I return a string, right?"

## 2. Understand It On Paper

The key realization: a palindrome is fully determined by its **left half**. The right half is just the mirror of the left. So to find a *close* palindrome, I should take the left half of `n`, and mirror it onto the right — that gives a palindrome very near `n`.

Let me make it concrete with `n = "12345"` (5 digits).

```
n = 1 2 3 4 5
        ^ middle
left half (with middle) = "123"
mirror left onto right:  1 2 3 2 1  -> "12321"
```

So `12321` is one strong candidate. But is it the closest? Not always — the closest palindrome might come from nudging the middle up or down.

```
prefix "123" -> palindrome 12321
prefix "124" (+1) -> palindrome 12421
prefix "122" (-1) -> palindrome 12221
```

These three cover the cases where keeping, increasing, or decreasing the middle gives the nearest match.

But there are **two nasty edge cases** the mirror approach misses:

**Edge A — crossing a digit-length boundary downward.** Take `n = "1000"`.
```
n = 1 0 0 0
mirror of "10" -> 1 0 0 1 = 1001  (bigger than 1000, distance 1)
but 999 is a palindrome, distance 1 too, and it's SMALLER -> wins on tie
```
999 = "all nines" with one fewer digit. The mirror method never produces it.

**Edge B — crossing upward (like 9...9 + 1).** Take `n = "99"`.
```
mirror -> 99 itself (not allowed)
next up: 101 (one more digit) distance 2
down: 9?  -> actually 100...001 pattern
```
The candidate here is `10...01` (one more digit), e.g. `101`.

So the complete candidate set is:
- Mirror of prefix
- Mirror of (prefix + 1)
- Mirror of (prefix - 1)
- `10^(L-1) + 1`  → smallest (L+1)-digit palindrome, like `101`, `1001`
- `10^(L-1) - 1`  → largest (L-1)-digit palindrome, all nines like `9`, `99`, `999`

**Constraint note:** length up to 18 digits → numbers up to ~10^18, which exceeds 32-bit but fits Python int (arbitrary precision) and 64-bit. No overflow worry in Python, but I'll mention it for languages like Java/C++ (use `long`, careful near 10^18).

## 3. Approach & Intuition

The pattern: "closest palindrome" screams **construct candidates, don't search**. Searching outward number-by-number is way too slow (could be billions away). Instead, a palindrome is locked by its first half — so I generate a *small fixed set* of candidate palindromes built from the first half of `n`, plus the two boundary specials (all-nines and 100..001), then just pick the best.

> 💬 "Instead of scanning numbers one at a time, I'll use the fact that a palindrome is determined by its left half. I'll build a handful of candidates by mirroring the prefix and nudging it ±1, plus two edge candidates for the digit-length boundaries, then choose the closest."

Layman version:
> 💬 "Think of a palindrome as folding a number in half — the left side decides everything. So I take `n`'s left side, fold it over, and also try bumping it up and down by one. The only weird cases are around round numbers like 1000, where '999' sneaks in, so I add those two specials explicitly."

## 4. Brute Force

The naive idea: start at `n`, walk outward — check `n-1`, `n+1`, `n-2`, `n+2`, … and return the first palindrome (handling the tie by checking the smaller side first).

```
for d = 1, 2, 3, ...:
    if isPalindrome(n-d): candidate_low
    if isPalindrome(n+d): candidate_high
    return appropriately
```

It's the natural first instinct and easy to explain. But the nearest palindrome can be far: for `n = 10^17`, the closest is about that far from many non-palindromes... actually distances are usually small, BUT worst cases and verifying each number's palindrome-ness make it unreliable, and conceptually it's O(distance × digits) with unbounded distance.

> 💬 "I'd start by mentioning the brute force — scan outward from n until I hit a palindrome — just to have a baseline, then I'll immediately move to the candidate-construction method which is O(number of digits)."

## 5. Optimal Approach

**1. The core idea in one sentence:** A palindrome is fixed by its left half, so the closest palindrome must be the mirror of `n`'s prefix, or that prefix ±1, or one of two digit-boundary specials — generate all five and pick the best.

**2. Why it works:** Any palindrome near `n` shares almost all of `n`'s high-order digits (those dominate the value). The high-order digits ARE the prefix, and mirroring fixes the low half. Changing the prefix by more than 1 moves you farther than these candidates, so ±1 around the prefix captures every near miss — except length-boundary jumps, which the all-9s and 10..01 specials cover.

**3. The steps:**
1. Let `L = len(n)`, `prefix = first ceil(L/2) digits`.
2. Add boundary candidates: `10^L + 1` (like 1001 for L=3→ actually 10^(L-1)... see code) and `10^(L-1) - 1` (all nines).
3. For each of `prefix-1, prefix, prefix+1`: mirror it into a full palindrome of the right length, add to candidates.
4. Remove any candidate equal to `n` and any that's invalid.
5. Pick candidate with smallest `abs(cand - n)`, breaking ties by smaller value.

**4. Trace on a tiny example: `n = "123"` (L=3, prefix = "12").**

```
n = 123,  L = 3,  prefix = "12"
```

Boundary specials:
```
all nines (L-1 digits) = 99
10..01 (L+1 digits)    = 1001
```

Mirror prefix and ±1 (odd length → drop prefix's last digit when mirroring):
```
prefix-1 = 11 -> mirror -> 1 1 1   = 111
prefix   = 12 -> mirror -> 1 2 1   = 121
prefix+1 = 13 -> mirror -> 1 3 1   = 131
```

Candidate set with distances from 123:
```
candidate | value | |cand - 123|
   99     |   99  |    24
  1001    | 1001  |   878
  111     |  111  |    12
  121     |  121  |     2   <-- closest
  131     |  131  |     8
```

> 💬 "121 wins with distance 2. Notice the mirror of the prefix itself was the answer here — the ±1 and boundary candidates were just safety nets."

**Now the tricky one: `n = "1000"` (L=4, prefix = "10").**

```
all nines (3 digits) = 999
10..01 (5 digits)    = 10001
prefix-1 = 9  -> mirror(4 digits) -> 0990? -> 9009  (treat as 9, pad) 
prefix   = 10 -> mirror -> 1 0 0 1 = 1001
prefix+1 = 11 -> mirror -> 1 1 1 1 = 1111
```

Distances from 1000:
```
candidate | value | |cand - 1000|
  999     |  999  |    1   <-- tie, and SMALLER
 10001    |10001  | 9001
  1001    | 1001  |    1   <-- tie
  1111    | 1111  |  111
```

> 💬 "Here 999 and 1001 are both distance 1 — a tie. The rule says return the smaller, so 999 wins. This is exactly why the all-nines special candidate is essential; the mirror method alone would have given 1001."

**5. Formal statement / invariant:** The optimal palindrome P minimizes `|P - n|` over all palindromes P ≠ n. The candidate set { mirror(prefix-1), mirror(prefix), mirror(prefix+1), 10^(L-1)-1, 10^(L-1)+1 } provably contains the minimizer, because outside ±1 of the prefix every palindrome is strictly farther, and length changes are covered by the two specials.

Now let me implement and verify it.My code flagged `"1283"` — but my *test expectation* was wrong: `1281` isn't even a palindrome. The mirror of prefix "12" is `1221` (dist 62) and prefix+1 gives `1331` (dist 48), so `1331` is correct. Let me fix the bogus test and confirm the brute-force cross-check passes.All cases pass, including a 20,000-case brute-force cross-check against numbers up to 99,999. The approach from the opener held up — no algorithmic change needed (only a typo in my own test expectation).

## 6. Solution (runnable, commented code)

```python
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
```

## 7. Code Walkthrough

Trace `n = "1000"`:
- `L = 4`, `num = 1000`.
- Specials: `10^3 - 1 = 999`, `10^4 + 1 = 10001`.
- `prefix = int("10") = 10`.
- Loop over `9, 10, 11` (even length, full mirror): `9 -> "9"+"9" = 99`... wait, `str(9)="9"`, mirror `"9"+"9"="99"` → but that's only 2 digits; it's still a valid palindrome candidate (99, dist 901). `10 -> "10"+"01" = 1001`. `11 -> "11"+"11" = 1111`.
- Candidates: `{999, 10001, 99, 1001, 1111}`, discard `1000` (not present).
- Distances: 999→1, 1001→1 (tie), others larger. Tie broken toward smaller → `999`.

> 💬 "I build five candidates, drop n itself, then sweep once tracking the closest, preferring the smaller value on ties."

## 8. Complexity Analysis

- **Time: O(L)** where L is the number of digits. We build a constant number (5) of candidates, each O(L) to construct (string mirror + int parse), then a constant-size scan. No searching.
- **Space: O(L)** for the candidate strings/ints.
- Contrast: brute force is O(distance × L) with unbounded distance — could blow up; the candidate method is linear in digit count regardless.

## 9. Edge Cases & Pitfalls

- **Single digit** (`"1"`→`"0"`, `"9"`→`"8"`): handled — `10^0 - 1 = 0` and mirror of prefix-1 covers it. Tested.
- **All nines** (`"99"`→`"101"`, `"999..."`): mirror equals n (discarded), so the `10^L+1` special wins. Tested up to 18 digits.
- **Power-of-ten boundaries** (`"1000"`→`"999"`, `"100"`→`"99"`): the all-nines special is essential and wins the tie as the smaller value. Tested.
- **Tie handling**: must prefer the *smaller* number — easy to get backwards. Tested via `1000`.
- **`n` itself is a palindrome** (`"123...321"`): must exclude it — that's the `discard(num)`. Common bug: returning `n`.
- **Odd vs even length mirroring**: off-by-one on whether the middle digit is duplicated — the `s[-2::-1]` vs `s[::-1]` split. Classic mistake.
- **Overflow** (in Java/C++): 18 digits exceeds 32-bit; use 64-bit `long` and watch the `10^L+1` special near the top of the range. Python is immune.

> 💬 **30-second summary:** "A palindrome is determined by its left half, so I generate five candidates — the mirror of n's prefix, the prefix plus and minus one mirrored, and two boundary specials, all-nines and 10…01 for digit-length crossings. I drop n itself, then pick the one with smallest absolute difference, breaking ties toward the smaller value. It's O(number of digits), and I verified it against a brute-force scan on 20,000 random cases."