"""Fetch Uber-tagged posts from LeetCode Discuss (interview-question +
interview-experience categories) into raw_leetcode/{topicId}.json.

Each saved file: {"category": ..., "node": <list metadata>, "topic": <full post>,
"comments": [top comments by votes]}.
Re-runnable: skips topics already on disk.
"""
import json
import os
import time
import urllib.request

BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
RAW = os.path.join(BASE, "raw_leetcode")
os.makedirs(RAW, exist_ok=True)

GQL = "https://leetcode.com/graphql/"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://leetcode.com/discuss/",
}
PAGE_SIZE = 50
SLEEP = 0.35
MAX_COMMENTS = 15

LIST_QUERY = """
query categoryTopicList($categories: [String!]!, $first: Int!, $orderBy: TopicSortingOption, $skip: Int, $query: String, $tags: [String!]) {
  categoryTopicList(categories: $categories, orderBy: $orderBy, skip: $skip, query: $query, first: $first, tags: $tags) {
    totalNum
    edges {
      node {
        id
        title
        commentCount
        viewCount
        post { id creationDate voteCount author { username } }
      }
    }
  }
}
"""

TOPIC_QUERY = """
query DiscussTopic($topicId: Int!) {
  topic(id: $topicId) {
    id
    title
    viewCount
    post { id creationDate voteCount content author { username } }
  }
}
"""

COMMENTS_QUERY = """
query discussComments($topicId: Int!, $orderBy: String, $pageNo: Int, $numPerPage: Int) {
  topicComments(topicId: $topicId, orderBy: $orderBy, pageNo: $pageNo, numPerPage: $numPerPage) {
    data {
      id
      post { id content voteCount creationDate author { username } }
    }
  }
}
"""


def gql(query: str, variables: dict, retries: int = 3) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(GQL, data=payload, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.loads(r.read())
            if out.get("errors"):
                raise RuntimeError(str(out["errors"])[:200])
            return out["data"]
        except Exception as e:  # noqa: BLE001 - retry then surface
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"gql failed after {retries} tries: {last_err}")


def list_topics(category: str) -> list[dict]:
    nodes, skip, total = [], 0, None
    while total is None or skip < total:
        data = gql(LIST_QUERY, {
            "categories": [category], "first": PAGE_SIZE, "skip": skip,
            "orderBy": "newest_to_oldest", "query": "", "tags": ["uber"],
        })
        block = data["categoryTopicList"]
        total = block["totalNum"]
        page = [e["node"] for e in block["edges"]]
        if not page:
            break
        nodes.extend(page)
        skip += PAGE_SIZE
        print(f"  [{category}] listed {len(nodes)}/{total}")
        time.sleep(SLEEP)
    return nodes


def fetch_topic(node: dict, category: str) -> None:
    tid = int(node["id"])
    dest = os.path.join(RAW, f"{tid}.json")
    if os.path.exists(dest) and os.path.getsize(dest) > 100:
        return
    topic = gql(TOPIC_QUERY, {"topicId": tid})["topic"]
    time.sleep(SLEEP)
    comments = []
    if node.get("commentCount"):
        data = gql(COMMENTS_QUERY, {
            "topicId": tid, "orderBy": "most_votes",
            "pageNo": 1, "numPerPage": MAX_COMMENTS,
        })
        comments = data["topicComments"]["data"]
        time.sleep(SLEEP)
    record = {"category": category, "node": node, "topic": topic, "comments": comments}
    with open(dest, "w") as f:
        json.dump(record, f, ensure_ascii=False)


def main() -> None:
    all_nodes: dict[int, tuple[dict, str]] = {}
    for category in ("interview-question", "interview-experience"):
        print(f"listing {category} …")
        for node in list_topics(category):
            all_nodes.setdefault(int(node["id"]), (node, category))

    with open(os.path.join(BASE, "leetcode_topics.json"), "w") as f:
        json.dump([{**n, "category": c} for n, c in all_nodes.values()], f, ensure_ascii=False)
    print("total unique topics:", len(all_nodes))

    ok = failed = 0
    for i, (tid, (node, category)) in enumerate(sorted(all_nodes.items(), reverse=True)):
        try:
            fetch_topic(node, category)
            ok += 1
        except Exception as e:  # noqa: BLE001 - log and continue
            failed += 1
            print(f"[{i + 1}/{len(all_nodes)}] {tid} FAILED: {e}")
        if (i + 1) % 25 == 0:
            print(f"[{i + 1}/{len(all_nodes)}] ok={ok} failed={failed}")

    print(f"done. ok={ok} failed={failed} / {len(all_nodes)}")


if __name__ == "__main__":
    main()
