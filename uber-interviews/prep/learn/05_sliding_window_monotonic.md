# LEARN: Sliding Window + Monotonic Deque/Stack

*Why this matters: "longest subarray with |diff| ≤ limit" was an ELIMINATION
round at Uber twice; the BPS "valid intervals with forbidden pairs" question
(in a 2026 offer loop) is pure sliding window; monotonic structures power the
OA hard questions.*

## Sliding window in plain words

You're looking for the best **contiguous** chunk satisfying some condition.
Instead of testing all O(n²) chunks, keep a window [left, right] and slide:
- grow `right` one step at a time,
- while the window is INVALID, shrink from `left`,
- record the best valid window.

This works only when validity is **monotone in shrinking**: if a window is
invalid, every bigger window containing it is also invalid (so shrinking is
the only fix). Always check this property in your head before committing.

```python
left = 0
for right in range(n):
    add(nums[right])                  # extend
    while invalid():
        remove(nums[left]); left += 1 # shrink
    best = max(best, right - left + 1)
```

## Worked example 1: the Uber elimination round (2x)

> Longest subarray where max - min ≤ limit.

Problem: `invalid()` needs the window's max and min — how to get them in O(1)
as the window slides? Answer: **monotonic deques** (next section). One deque
holds indices with DECREASING values (front = window max), the other
INCREASING (front = window min). Each index enters and leaves each deque once
→ O(n) total. Full code: `../solutions/arrays_windows.py`.

## Worked example 2: forbidden pairs (BPS round, 2026 offer loop)

> n items in a row; m forbidden pairs (u,v) cannot both be inside the chosen
> interval. Count valid intervals [L, R].

The unlock (the candidate who got the offer said exactly this): for each
right endpoint R, there's a **minimum allowed left boundary**: if a forbidden
pair (u, v) with u < v ≤ R exists, then L must be > u. So:
`minL(R) = 1 + max(u over pairs with v ≤ R)`, maintained as a running max
while sweeping R. Valid intervals ending at R = `R - minL(R) + 1`. O(n + m).
Sliding window where the "shrink" is driven by a precomputed running max —
windows don't always shrink via a while loop.

## Monotonic stack in plain words

A stack you keep sorted by popping everything that breaks the order before
pushing. Classic use: **next greater element** — pop all smaller elements
when a new value arrives; whatever pops has found its "next greater".

```python
stack = []                      # indices, values decreasing
nge = [-1] * n
for i, x in enumerate(nums):
    while stack and nums[stack[-1]] < x:
        nge[stack.pop()] = i
    stack.append(i)
```

Each element pushes once, pops once → O(n). That amortized argument is a
sentence interviewers want to hear.

## Where Uber pushed it further (OA hard, asked 2x)

> K-th next greater element index, for every i.

The plain stack gives the 1st next greater. For k-th, the stack alone dies —
you need the offline trick: process values largest-first and use a BIT to ask
"k-th set index to my right" (`../solutions/arrays_windows.py` →
`kth_next_greater`). In the OA, recognizing "this is next-greater family but
k-th = BIT/offline" quickly is the whole game; a brute O(n²) partial score is
a fine fallback — bank it, then optimize.

## How to choose between the tools

| Question smell | Tool |
|---|---|
| best contiguous chunk, condition monotone | sliding window |
| window max/min needed | + monotonic deque |
| next/previous greater/smaller | monotonic stack |
| k-th next greater, order-statistics with indices | BIT / offline |
| count subarrays with constraint per right endpoint | running-max left bound |

## Mistakes that cost offers

- Using sliding window when validity is NOT monotone (e.g., "sum equals
  exactly X" with negatives) — it silently returns wrong answers.
- Deque cleanup with the wrong comparison (`<` vs `<=`) — decide whether
  equal values stay; for max-deque pop `<=` to keep deque strictly
  decreasing... then re-derive once on paper, don't memorize blindly.
- Forgetting to evict deque fronts that left the window (compare INDEX, not
  value).
- Off-by-one on window length (`right - left + 1` — write it once, reuse).

## Practice ladder

1. LC 239 Sliding Window Maximum (deque drill)
2. LC 1438 Longest Subarray |diff| ≤ limit (the Uber elimination question)
3. LC 496/503 Next Greater Element I/II (stack drill)
4. LC 907 Sum of Subarray Minimums (stack, harder)
5. The forbidden-pairs question (re-derive minL sweep from memory)
6. K-th next greater: read then re-implement `../solutions/arrays_windows.py`
