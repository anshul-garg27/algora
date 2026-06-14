# CRIB SHEET — DSA Round (45-60 min, read before the call)

## The protocol
- **Min 0-5:** clarify (input size! duplicates? empty? multiple answers?).
  Input size decides your complexity target — say that out loud.
- **Min 5-12:** brute force stated + complexity → name the bottleneck →
  propose optimal → get a nod BEFORE coding.
- **Min 12-35:** code with narration. Comments first, then fill.
- **Min 35-45:** trace example by hand, edge cases, run, complexity recap.

## The 5 rules from real Uber debriefs
1. **Shortest path ⇒ BFS/Dijkstra, NEVER DFS** (a candidate passed all tests
   with DFS and still got negative feedback).
2. Complexity stated **unprompted**, every solution.
3. Bank a working version before optimizing — but ANNOUNCE the optimal plan.
4. A follow-up is ALWAYS coming: k-th variant, deletion variant, streaming
   variant, thread-safe variant. Leave 10 minutes for it.
5. If they push optimization before you've coded baseline: "Let me state the
   optimal approach now and code it directly" — be flexible.

## Pattern triggers (10-second recognition)
| Smell | Reach for |
|---|---|
| connections added over time / fully connected | **DSU** (+ say: can't delete) |
| spreads from many sources / nearest X | multi-source BFS |
| order from constraints / prerequisites | topo sort (Kahn's) |
| straight-line distances per direction in grid | 4 sweeps, not BFS |
| best contiguous chunk | sliding window (+ deques for max/min) |
| next/k-th greater | monotonic stack / BIT offline |
| top-K / stream | size-K min-heap |
| take from ends / two players | minimax diff DP |
| cost over a range w/ chosen root/split | interval DP (+sum term!) |
| closest/next palindrome | candidate set (5 candidates) |
| maximize X with monotone feasibility | binary search on answer |

## Uber's repeat list (if one of these appears, you've seen it)
Closest palindrome · alien dictionary · DSU ride logs (+cancel) · robots &
blockers · haunted house · file-system APIs · optimal BST · predict winner ·
fire escape · min edge reversals · longest subarray ≤ limit · sorted squares
k-th · course schedule · hit counter / TTL store / getRandom.

## Stuck? (in order)
Restate problem → smaller example by hand → "what structure makes the slow
part O(1)/O(log n)?" → state trade-off question to interviewer (costs less
than silence).
