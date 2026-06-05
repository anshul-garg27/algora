## 1. Problem Understanding

I'm given a number as a **string** `n` (up to 18 digits, so it can exceed 64-bit range — that's why it's a string). I need to find the **palindrome integer closest to it in absolute value**, and crucially the answer **must NOT equal `n` itself**. If two palindromes are equally close, I return the **smaller** one.

Quick sanity check with the examples: `"123"` → `"121"` (122 isn't a palindrome, 121 is distance 2, next palindrome up is 131 at distance 8, so 121 wins). `"1"` → `"0"` (the closest palindrome that isn't 1 is 0; 2 is also distance 1 but on a tie we take the smaller, 0).

**Clarifying questions I'd ask:**
- Must the result be **strictly different** from `n`? (Yes — the classic version requires "not including itself.")
- Can the answer be **0 or negative**? (Standard version: result is a non-negative palindrome; 0 is allowed, negatives are not.)
- Return type — **string or int**? I'll return a string to match the input style and handle 18 digits safely.
- On a tie, **smaller** wins — confirmed by `"1"→"0"`.
- Are there leading zeros in input? (Assume no, it's a valid integer.)

> 💬 "So I'm given a number as a string because it can be up to 18 digits. I need the nearest palindrome to it, but it can't be the number itself, and if there's a tie I pick the smaller one. Let me confirm — the result should be a non-negative integer, and on a tie I return the smaller value, like 1 maps to 0 rather than 2, right?"

## 2. Understand It On Paper (slow, visual)

Let me make sure I really understand what "closest palindrome" means before getting clever.

A **palindrome** reads the same forwards and backwards: `121`, `1331`, `7`, `99`, `1001`.

The naive mental model: stand on the number line at `n`, walk left and walk right until you hit a palindrome on each side, take whichever is nearer.

```
            n = 123
 ... 111   121  [123]  131  141 ...
            ^     ^      ^
          dist=2       dist=8
          -> 121 wins
```

But walking one step at a time is hopeless when `n` is 18 digits — palindromes can be far apart. So I need to *generate candidates directly*.

**The key observation — a palindrome is decided by its first half.** Take the left half of the number and mirror it onto the right. That gives the palindrome "closest in shape" to `n`.

```
 n = 12345   (5 digits)
 left half (with middle) = "123"
 mirror first 2 of it onto the back:
   1 2 3 | mirror "12" -> "21"
   -> 1 2 3 2 1  = 12321
```

So `12321` is a great candidate — it shares the high digits with `n`, so it's very close.

But mirroring the prefix as-is isn't always the *closest*. Watch this case:

```
 n = 100      prefix = "10"
 mirror "1" -> "1"  giving 1 0 1 = 101   (distance 1, but 101 > 100)
 Is there something closer BELOW? 99 !  (distance 1, and smaller)
```

So the closest palindrome might come from the prefix, OR the prefix **+1**, OR the prefix **−1**. That's the "aha": only three prefix choices matter.

And there are two more sneaky edge cases that the prefix trick alone misses:

```
 n = 1000000  -> closest is 999999  (all nines, one digit shorter)
 n = 10       -> closest is 9
```
and
```
 n = 99   -> next palindrome up is 101 (one digit longer)
```

So I also throw in two "boundary" candidates: `99...9` (one digit shorter) and `100..001` (one digit longer).

**Constraints check:** len up to 18 ⇒ values up to ~10^18, which *overflows* signed 64-bit in some languages — in Python ints are unlimited so I'm safe, but I should still be careful and compute on strings/ints cleanly. There's no big-N loop here; the work is just building ~5 candidates and comparing. So target complexity is O(L) where L = number of digits. Trivial time, the whole difficulty is *not missing a candidate*.

## 3. Approach & Intuition

This is a **"construct the candidates, don't search"** problem. The pattern signal: the search space (all palindromes) is astronomically large, but the *closest* one must look almost identical to `n` in its high digits — so it's fully determined by the **first half**.

The reasoning out loud: the most significant digits dominate distance. To stay close to `n`, keep the top half and mirror it. The only freedom is nudging that half by `+1`, `0`, or `−1`. Plus the two length-boundary palindromes (all 9s below, `10...01` above) cover the cases where the digit count changes.

> 💬 "Brute force would walk outward from n until I hit a palindrome, but with 18 digits that's way too slow. The insight is that a palindrome is fully determined by its first half — so instead of searching, I'll *construct* a handful of candidates from the prefix, nudge it up and down by one, add the all-nines and the next-power boundary cases, and just pick the best. Five candidates, constant work."

## 4. Brute Force

The natural first idea: starting from `n`, check `n-1, n+1, n-2, n+2, …` outward, return the first palindrome found (handling the tie by checking the smaller side first).

- **Why it's natural:** directly encodes "closest" as walking the number line.
- **Why it fails at scale:** consecutive palindromes can be ~10^9 apart for 18-digit numbers (e.g. just above a number like `10^17`), so you'd loop an astronomical number of times. Checking each for palindrome-ness is O(L), but the number of checks is the killer.
- **Complexity:** worst case O(gap x L) where gap can be ~10^(L/2) — effectively exponential in digit count. Fine to *mention* as the baseline, not to submit.

> 💬 "Let me state the brute force to get a baseline: from n, expand outward checking each number for being a palindrome. Correct but potentially billions of steps for big inputs — so I'll optimise by generating candidates instead."

## 5. Optimal Approach

**1. Core idea in one sentence:** A palindrome is fixed by its first half, so build the answer by mirroring `n`'s first half — and also the half ±1 — then add the two length-boundary palindromes, and pick the closest (smaller on ties), excluding `n` itself.

**2. Why it works:** To be close to `n`, the high digits must match `n` as much as possible. Mirroring the prefix matches them exactly; the only adjustment that can ever help is bumping the prefix by ±1 (which rolls the middle digit). The all-9s and `10…01` candidates handle the rare cases where the closest palindrome has a *different number of digits*.

**3. The steps:**
1. Let `L = len(n)`. Take `prefix = first ceil(L/2) digits`.
2. From each of `prefix-1, prefix, prefix+1`, build a palindrome by mirroring (respect odd/even length).
3. Add boundary candidate `10^(L-1) - 1` = all nines (e.g. `999`).
4. Add boundary candidate `10^L + 1` = `100…001`.
5. From all candidates, drop any equal to `n`, then pick the one with smallest `|cand - n|`; tie → smaller value.

**4. Trace on a tiny example — `n = "123"`:**

```
n = 123,  L = 3,  half-length = ceil(3/2) = 2,  prefix = "12"
```

Build the three prefix-based palindromes. For odd length, mirror the prefix WITHOUT its last digit:

```
 prefix-1 = 11 -> mirror "1" onto back of "11" -> 1 1 1   = 111
 prefix   = 12 -> mirror "1" onto back of "12" -> 1 2 1   = 121
 prefix+1 = 13 -> mirror "1" onto back of "13" -> 1 3 1   = 131
```

Boundary candidates:

```
 all nines (L-1=2 digits): 99
 next power: 10^3 + 1     : 1001
```

Now score every candidate by distance to 123 (excluding 123 itself, which isn't in the list anyway):

| candidate | value | \|value − 123\| |
|---|---|---|
| 111 | 111 | 12 |
| 121 | 121 | **2** |
| 131 | 131 | 8 |
| 99  | 99  | 24 |
| 1001| 1001| 878 |

```
 closest distance = 2  -> 121   ✅
```

> 💬 "Prefix is '12'. I mirror it to get 121 — distance 2. I nudge the prefix down to 11 giving 111, and up to 13 giving 131 — both farther. I add 99 and 1001 for the length-change cases. 121 wins."

**Second trace — the tricky `n = "1"`** (shows why boundary + tie rules matter):

```
n = 1, L = 1, prefix = "1"
 prefix-1 = 0 -> 0
 prefix   = 1 -> 1   (== n, EXCLUDE)
 prefix+1 = 2 -> 2
 all nines (L-1 = 0 digits) -> 9? handled as 0/edge -> candidate 0
 next power 10^1 + 1 = 11
```

```
 valid candidates (drop 1): {0, 2, 11}
 |0-1| = 1 ,  |2-1| = 1 ,  |11-1| = 10
 tie between 0 and 2 at distance 1  ->  take SMALLER  -> 0  ✅
```

> 💬 "For n = 1, the prefix candidate 1 is n itself so I drop it. That leaves 0 and 2 both at distance 1 — tie — so I return the smaller, 0. The all-nines and next-power candidates are what guarantee I don't miss 0 and 11."

**5. Formal statement:** Candidate set C = { mirror(prefix+d) : d ∈ {−1,0,1} } ∪ { 10^(L−1) − 1, 10^L + 1 }. Answer = argmin over c in C\{n} of (|c − n|, c) under lexicographic comparison (distance first, then value).

Now let me implement and verify this.Two "expected" values in my own test list were wrong guesses (`1281` isn't even a palindrome, and for `88` the tie should pick the smaller `77`). Let me confirm the code is right with an independent brute-force checker.Zero mismatches across 20,000 random cases versus brute force, plus all the big/boundary cases check out. The approach from the opener held up exactly — no correction needed. Here's the final write-up.

## 6. Solution (runnable, commented code)

```python
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
```

## 7. Code Walkthrough

Tracing `n = "100"`:

1. `L = 3`, `num = 100`.
2. Boundary candidates: `10^2 - 1 = 99`, and `10^3 + 1 = 1001`. Set so far: `{99, 1001}`.
3. `prefix = int("10") = 10` (first `(3+1)//2 = 2` digits).
4. Loop `d = -1, 0, 1`:
   - `d=-1`: `p="9"`, odd length so mirror `p[-2::-1]` (empty) → `"9"` → `9`.
   - `d= 0`: `p="10"`, → `"10" + "1"` = `"101"` → `101`.
   - `d=+1`: `p="11"`, → `"11" + "1"` = `"111"` → `111`.
   - Set: `{99, 1001, 9, 101, 111}`.
5. `discard(100)` (not present), all non-negative.
6. Score by `(abs(c-100), c)`:

| c | abs(c−100) | tie-key |
|---|---|---|
| 9 | 91 | – |
| 99 | **1** | 99 |
| 101 | **1** | 101 |
| 111 | 11 | – |
| 1001 | 901 | – |

7. Tie at distance 1 between `99` and `101`; `min` on `(1, 99)` vs `(1, 101)` picks `99`. Returns `"99"`. ✅

> 💬 "Watch the tie at n=100: both 99 and 101 are distance 1. My comparison key is the pair (distance, value), so Python's min naturally breaks the tie toward the smaller value, 99 — which is exactly the rule."

## 8. Complexity Analysis

- **Time: O(L)** where L = number of digits (≤ 18). I build a constant number of candidates (5), and each costs O(L) to construct and compare as a string/int. No search loop.
- **Space: O(L)** for the handful of candidate strings/ints.
- **Contrast:** the brute force is up to O(gap x L) where the gap between consecutive palindromes can be ~10^(L/2) — astronomically worse. We replaced an outward *search* with direct *construction*.

## 9. Edge Cases & Pitfalls

Tested explicitly (all pass):
- **Single digit** `"1" → "0"`, `"9" → "8"`, `"0" → "1"` — the all-nines/`±1` candidates and the exclude-self rule matter most here.
- **Tie → smaller**: `"100" → "99"` (not 101), `"88" → "77"` (not 99).
- **Length shrink**: `"1000" → "999"`, `"10000" → "9999"`.
- **Length grow**: `"99" → "101"`, `"9999" → "10001"`.
- **Max 18 digits**: `"999999999999999999" → "1000000000000000001"`, `"1000000000000000000" → "999999999999999999"`.

Common pitfalls interviewers probe:
- **Forgetting to exclude `n` itself** — a palindrome input like `"121"` must return a *different* palindrome.
- **Missing the boundary candidates** — without `99...9` and `10...01` you fail cases like `"1000"` and `"99"`.
- **Tie handling** — returning the larger on a tie breaks `"1"` and `"100"`.
- **Odd vs even length mirroring** — for odd length you must drop the prefix's middle digit before reflecting, or you produce a wrong-length string.
- **Overflow** — in 64-bit languages an 18-digit `n` plus the `10^L+1` candidate can overflow; that's the whole reason input is a string. Python ints are unbounded, but I'd flag this explicitly in C++/Java.

> 💬 **30-second summary:** "A palindrome is determined by its first half, so I don't search — I construct. I take n's prefix and mirror it, and also mirror prefix±1 to catch the rollover cases. I add two boundary palindromes — all nines for when the answer is shorter, and 10…01 for when it's longer — to handle digit-count changes. Then I drop n itself and pick the candidate with the smallest absolute difference, breaking ties toward the smaller value. It's O(number of digits) time, and I keep everything as strings/big-ints so 18 digits never overflows."