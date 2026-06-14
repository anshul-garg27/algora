# LEARN: DP Patterns Uber Actually Asks

*Why this matters: Uber's DP questions cluster into THREE specific families —
interval DP (Optimal BST: "toughest screening round", asked 2x), game theory
minimax (asked 2x), and grid DP (multiple OAs/screens). Generic DP grinding
is inefficient; drill these three.*

## How to think about any DP (the 4 questions)

1. **State**: what's the minimum info that makes the rest of the problem
   independent of how I got here? (e.g., "interval [i..j] remains")
2. **Choice**: what decision do I make at this state? (e.g., "pick root r")
3. **Recurrence**: cost of choice + solved subproblems.
4. **Base + order**: smallest states first (or memoize and forget the order).

In the interview, SAY these four explicitly. The May-2026 candidate who
passed the OBST screening described exactly this narration.

## Family 1: Interval DP — Optimal BST (the screening killer)

> Sorted words + search frequencies. Build a BST (inorder = sorted order)
> minimizing Σ freq × depth (1-based).

The two unlocks, in order:
1. **"Words are a red herring — sorted order fixes the BST's inorder; only
   the SHAPE is free, so only frequencies matter."** Saying this early is the
   difference between 40 minutes of progress and 40 minutes of flailing.
2. When root r is chosen for interval [i..j], BOTH subtrees sink one level
   deeper → "+ sum(freq[i..j])" pays for that depth increase:

```
dp[i][j] = min over r in [i..j] of dp[i][r-1] + dp[r+1][j] + sum(freq[i..j])
```

O(n³) with prefix sums; mention "Knuth's optimization → O(n²)" without coding
it. Full code: `../solutions/dp_math.py`.

Interval DP recognition: "the answer for a RANGE built by choosing a split /
root / last operation inside it". Siblings: burst balloons, matrix chain,
stone merging.

## Family 2: Game theory minimax — Predict the Winner (asked 2x)

> Two players alternately take a number from either END of an array; both
> play optimally. Does player 1 win / what's their best total?

The unlock: track the **score DIFFERENCE**, not two scores.
`f(i, j)` = (my total − opponent total) when subarray [i..j] remains and it's
my turn. After I pick, the OPPONENT faces f of the rest — so I subtract:

```
f(i, j) = max( nums[i] - f(i+1, j),     # take left
               nums[j] - f(i, j-1) )    # take right
```

"Both optimal" is encoded automatically: the recursion always maximizes for
whoever's turn it is, and the minus sign flips perspective. Explain THAT
sentence — it's what the interviewer is listening for.

Player 1's total from the diff: `p1 = (sum + f(0, n-1)) // 2`.

Follow-ups Uber used: reconstruct the moves (walk the table along argmax);
"k picks per turn" (state gains nothing — same recurrence, k transitions).

## Family 3: Grid DP — min path sum + variants

> Min cost path top-left → (x, y), moves: down, right, **and diagonal**
> (the diagonal is Uber's twist; asked 2x as screening).

`dp[i][j] = cost[i][j] + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])`. O(nm),
O(m) space if you keep one row. The Uber phone screen accepted the plain
version coded cleanly in ~10 minutes — this family is about SPEED and edge
rows, not insight. Drill until it's mechanical.

Related Uber grid DP: Dungeon Game variant (2026 onsite — work BACKWARD from
the end: state = min health needed entering cell; forward DP fails because
health clamps), and Shopping Offers (memo on the needs-tuple).

## Recognizing which family in 10 seconds

| Smell | Family |
|---|---|
| "minimize total cost of building a tree/merging a range" | interval DP |
| "two players, optimal play, take from ends" | minimax diff |
| "min/max path through grid, limited directions" | grid DP |
| "resource that clamps (health, fuel floor)" | grid DP **backward** |

## Mistakes that cost offers

- OBST: forgetting the `+ sum(i..j)` term (treating depth as free) — the #1
  bug; sanity-check with 2 elements by hand BEFORE coding.
- Minimax: tracking both players' scores as state (explodes); track the diff.
- Writing `@lru_cache` on lists (unhashable) — convert to tuples/indices.
- Recursion depth: n=2000 intervals → iterate by span instead of recursing.
- Not stating complexity per family: O(n³)/O(n²ᵏ)/O(nm) respectively.

## Practice ladder

1. LC 64 Minimum Path Sum (+ add the diagonal yourself)
2. LC 486 Predict the Winner → then LC 877 Stone Game
3. GfG Optimal BST → re-derive the recurrence on paper, then code in 25 min
4. LC 174 Dungeon Game (backward DP)
5. LC 312 Burst Balloons (interval DP depth)
6. LC 1547 Cut a Stick (interval DP speed run)
