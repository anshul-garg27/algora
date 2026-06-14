# LEARN: Heaps, Top-K, and Streaming — the pattern that bridges DSA and HLD

*Why this matters: "top K items from a stream" appeared at Uber as a DSA
question, a phone-screen coding question, AND ~10 system design rounds.
Same idea, three altitudes. Learn it once, use it everywhere.*

## Heaps in plain words

A heap is a bag that can always hand you its smallest item in O(log n).
Python's `heapq` is a MIN-heap. For a max-heap, push negatives.

The counter-intuitive rule that solves 80% of top-K:
**"Top K largest" → keep a MIN-heap of size K.**
Why: the heap's smallest element is the "entry bar" — a new item either beats
the bar (pop, push) or doesn't (ignore). After the stream, the heap IS the
top K. O(n log k), and only O(k) memory — say both.

```python
import heapq

def top_k(stream, k):
    heap = []
    for x in stream:
        if len(heap) < k:
            heapq.heappush(heap, x)
        elif x > heap[0]:
            heapq.heapreplace(heap, x)
    return sorted(heap, reverse=True)
```

## The Uber DSA version (Onsite, Feb 2025)

> `addCustomer(revenue)` / `addCustomer(revenue, referredBy)` (referral adds
> revenue up the chain by one level) / `getKCustomersWithRevenueGreaterThan(k, v)`.
> Follow-up: better than O(N log K) per query — data is large and streaming.

What's being tested: you can't rebuild a heap per query when queries are
frequent. The expected direction: keep customers in a **sorted structure by
revenue** (balanced BST / `sortedcontainers.SortedList` in Python — SAY "in
Java this is a TreeMap") so a query is "walk from the top until k found or
revenue ≤ v" = O(k + log n). Updates (referral revenue change) = remove +
re-insert = O(log n). The top-voted community answer was exactly
HashMap + TreeMap — that pairing (point lookup + ordered iteration) is a
recurring Uber expectation.

## The phone-screen version (asked twice)

> Million purchase events/min stream in. Show the top-K items, refreshed
> every ~10 minutes. Live-code it; don't hold everything in memory.

Expected shape (this is coding, not boxes):
- Bucket counts per minute: `dict[minute][item] -> count` (or fixed ring of
  10 minute-buckets).
- On refresh: merge the last 10 buckets' counts, run the size-K min-heap.
- Expire old buckets — memory stays bounded by window size.
This is literally the Hit Counter pattern + top_k glued together.

## The HLD version (so you see the throughline)

Same problem at planet scale = the heatmap/trending playbook
(`../hld/01_realtime_heatmap_topk.md`): minute buckets become stream-processor
windows, the dict becomes Redis/state store, exact counts become
**count-min sketch** when keys are unbounded. In the design round, SAY the
DSA version first ("per window, counts + size-K heap") then scale it — that
narrative arc reads as seniority.

## When it's NOT a heap

- "k-th smallest with index/order conditions" → often binary search or BIT
  (see k-th next greater in `../solutions/arrays_windows.py`).
- "median of stream" → TWO heaps (low max-heap, high min-heap), balance sizes.
- "top K with updates/deletions" → ordered structure (SortedList/TreeMap),
  not a heap — heaps can't update arbitrary members efficiently. This
  distinction is exactly what the Feb-2025 follow-up was probing.

## Mistakes that cost offers

- Max-heap of ALL n items for top-K (O(n) memory — the follow-up will kill it).
- Rebuilding the heap per query (the explicitly banned approach in the real
  question).
- Forgetting Python heapq is min-only and fumbling the negation mid-interview.
- Heap of (value, dict)-style unorderable tuples → runtime crash; push
  (key, id, payload) with a tiebreaker id.

## Practice ladder

1. LC 215 Kth Largest in Array
2. LC 703 Kth Largest in a Stream (the class-based shape Uber likes)
3. LC 347 Top K Frequent Elements
4. LC 295 Find Median from Data Stream (two-heap drill)
5. Re-implement the phone-screen version (minute buckets + refresh) from
   memory in <20 min
