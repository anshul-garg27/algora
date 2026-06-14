"""Fetch Uber-tagged posts from LeetCode's NEW discuss system (ugcArticle*),
which holds everything after the ~Feb 2025 migration. Saves into
raw_leetcode_v2/{topicId}.json as {"node":..., "article":..., "comments":[...]}.

Only fetches articles created on/after CUTOFF. Re-runnable: skips existing files.
"""
import datetime
import json
import os
import time
import urllib.request

BASE = "/Users/anshullkgarg/Desktop/projects/claude-gpt/uber-interviews"
RAW = os.path.join(BASE, "raw_leetcode_v2")
os.makedirs(RAW, exist_ok=True)

CUTOFF = datetime.datetime(2025, 2, 1, tzinfo=datetime.timezone.utc)
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
query discussPostItems($orderBy: ArticleOrderByEnum, $keywords: [String]!, $tagSlugs: [String!], $skip: Int, $first: Int) {
  ugcArticleDiscussionArticles(orderBy: $orderBy, keywords: $keywords, tagSlugs: $tagSlugs, skip: $skip, first: $first) {
    totalNum
    edges {
      node {
        uuid
        title
        slug
        createdAt
        topicId
        hitCount
        author { userSlug }
        tags { name slug }
        topic { id commentCount }
        reactions { count reactionType }
      }
    }
  }
}
"""

ARTICLE_QUERY = """
query articleDetail($topicId: ID) {
  ugcArticleDiscussionArticle(topicId: $topicId) {
    uuid
    title
    content
    createdAt
    hitCount
    author { userSlug }
    reactions { count reactionType }
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


def list_recent() -> list[dict]:
    nodes, skip = [], 0
    while True:
        data = gql(LIST_QUERY, {
            "orderBy": "MOST_RECENT", "keywords": [], "tagSlugs": ["uber"],
            "skip": skip, "first": PAGE_SIZE,
        })
        block = data["ugcArticleDiscussionArticles"]
        page = [e["node"] for e in block["edges"]]
        if not page:
            break
        stop = False
        for n in page:
            created = datetime.datetime.fromisoformat(n["createdAt"])
            if created < CUTOFF:
                stop = True
                break
            nodes.append(n)
        print(f"  listed {len(nodes)} (skip={skip}, total={block['totalNum']})")
        if stop or skip + PAGE_SIZE >= block["totalNum"]:
            break
        skip += PAGE_SIZE
        time.sleep(SLEEP)
    return nodes


def fetch_article(node: dict) -> None:
    tid = int(node["topicId"])
    dest = os.path.join(RAW, f"{tid}.json")
    if os.path.exists(dest) and os.path.getsize(dest) > 100:
        return
    article = gql(ARTICLE_QUERY, {"topicId": tid})["ugcArticleDiscussionArticle"]
    time.sleep(SLEEP)
    comments = []
    if (node.get("topic") or {}).get("commentCount"):
        data = gql(COMMENTS_QUERY, {
            "topicId": tid, "orderBy": "most_votes",
            "pageNo": 1, "numPerPage": MAX_COMMENTS,
        })
        comments = data["topicComments"]["data"]
        time.sleep(SLEEP)
    record = {"node": node, "article": article, "comments": comments}
    with open(dest, "w") as f:
        json.dump(record, f, ensure_ascii=False)


def main() -> None:
    print(f"listing uber-tagged articles since {CUTOFF.date()} …")
    nodes = list_recent()
    print("articles in window:", len(nodes))

    ok = failed = 0
    for i, node in enumerate(nodes):
        try:
            fetch_article(node)
            ok += 1
        except Exception as e:  # noqa: BLE001 - log and continue
            failed += 1
            print(f"[{i + 1}/{len(nodes)}] {node['topicId']} FAILED: {e}")
        if (i + 1) % 25 == 0:
            print(f"[{i + 1}/{len(nodes)}] ok={ok} failed={failed}")
    print(f"done. ok={ok} failed={failed} / {len(nodes)}")


if __name__ == "__main__":
    main()
