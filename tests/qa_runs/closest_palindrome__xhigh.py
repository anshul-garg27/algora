
## 7. Code Walkthrough

Let me trace `n = "12921"` (L = 5, odd; `num = 12921`).

| Step | Action | State |
|---|---|---|
| Edge 1 | `10^(5-1) - 1` | add `9999` |
| Edge 2 | `10^5 + 1` | add `100001` |
| Prefix | first `(5+1)//2 = 3` digits | `prefix = 129` |
| p = 128 | odd mirror: `"128" + "21"` | add `12821` |
| p = 129 | odd mirror: `"129" + "21"` | add `12921` |
| p = 130 | odd mirror: `"130" + "31"` | add `13031` |
| Discard | remove `num = 12921` | candidates `{9999, 100001, 12821, 13031}` |

Now compare distances to `12921`:

