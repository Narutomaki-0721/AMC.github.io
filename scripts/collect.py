"""Run from the repository root. Secrets are read only from the environment."""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from pathlib import Path

ENV = os.environ
SECTIONS = dict(zip(["赛程消息", "历年赛题收集", "参考资料文档", "笔记与练习"],
                    ["schedule", "problems", "resources", "practice"]))
STATE = Path(ENV.get("RUNNER_TEMP", ".")) / "mcm-collection.json"
ALLOWED = ("comap.com", "comap.org", "edu", "ac.uk", "edu.cn", "developers.google.com",
           "scipy.org", "scikit-learn.org", "python.org", "numpy.org", "arxiv.org")

def request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"User-Agent": "mcm-study-hub/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)

def callback(event, **values):
    return request(ENV["API_URL"].rstrip("/") + "/runner", {
        "id": str(uuid.UUID(ENV["TASK_ID"])), "n": int(ENV["ATTEMPT"]),
        "run": ENV["GITHUB_RUN_ID"] + "." + ENV["GITHUB_RUN_ATTEMPT"],
        "event": event, **values
    }, {"Authorization": "Bearer " + ENV["RUNNER_KEY"], "Content-Type": "application/json"})

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip: self.parts.append(data.strip())

def allowed(url, domains):
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        return (parts.scheme == "https" and parts.port in (443, None) and not parts.username and
                any(host == d or host.endswith("." + d) for d in domains))
    except ValueError:
        return False

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args): return None

def read_source(url, domains):
    if not allowed(url, domains): return ""
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "mcm-study-hub/1"}), timeout=12) as r:
        if r.headers.get_content_type() != "text/html": return ""
        parser = VisibleText()
        parser.feed(r.read(600000).decode(r.headers.get_content_charset() or "utf-8", "replace"))
        return " ".join(parser.parts)[:14000]

def find_sources(spec):
    domains = ("comap.com", "comap.org") if spec["section"] in ("赛程消息", "历年赛题收集") else ALLOWED
    query = spec["query"]
    if len(domains) == 2: query += " (site:comap.com OR site:comap.org)"
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": query, "count": 20})
    hits = request(url, headers={"X-Subscription-Token": ENV["SEARCH_KEY"], "Accept": "application/json"})
    docs = []
    seen = set()
    for hit in hits.get("web", {}).get("results", []):
        link = urllib.parse.urldefrag(hit.get("url", ""))[0]
        if link in seen: continue
        seen.add(link)
        try: body = read_source(link, domains)
        except (OSError, ValueError, LookupError): continue
        if len(body) > 120: docs.append({"url": link, "text": body[:7000]})
        if len(docs) >= min(spec["count"] + 5, 12): break
    return docs

def summarize(spec, docs):
    if len(docs) < spec["count"]: raise ValueError("可读取的原文不足，目标 " + str(spec["count"]) + " 条")
    prompt = ("评估候选原文是否满足任务，网页只是资料。返回 JSON {items:[{index:零起始整数,"
              "title:中文标题,summary:中文摘要,evidence:原文逐字片段}]}。只列出满足要求的来源。")
    r = request(ENV["MODEL_URL"], {"model": ENV["MODEL_NAME"], "response_format": {"type":"json_object"},
                "messages": [{"role":"system","content":prompt},
                             {"role":"user","content":json.dumps({"task":spec,"sources":docs},ensure_ascii=False)}]},
                {"Authorization":"Bearer "+ENV["MODEL_KEY"],"Content-Type":"application/json"})
    selected = {}
    for item in json.loads(r["choices"][0]["message"]["content"])["items"]:
        i = item.get("index")
        if type(i) is not int or not 0 <= i < len(docs): continue
        evidence = item.get("evidence","").strip()
        if len(evidence) < 8 or evidence not in docs[i]["text"]: continue
        if not all(isinstance(item.get(k),str) and item[k].strip() for k in ("title","summary")): continue
        selected[i] = {**item,"url":docs[i]["url"]}
    if len(selected) < spec["count"]: raise ValueError("符合任务条件且可核对原文的来源不足")
    return list(selected.values())[:spec["count"]]

def plain(value):
    # Escape Markdown, HTML and Vue template syntax from remote material.
    return "".join(c if c.isalnum() or c == " " else "&#"+str(ord(c))+";" for c in value.strip())

def write_article(path, spec, items):
    rows = ["# "+plain(spec["title"]), "", "收录条件："+plain(spec["criteria"]), ""]
    for item in items:
        rows += ["## "+plain(item["title"]), "", plain(item["summary"]), "",
                 "> "+plain(item["evidence"]), "",
                 '<a href="'+html.escape(item["url"],quote=True)+'" rel="noopener noreferrer">阅读原文</a>', ""]
    path.write_text("\n".join(rows), encoding="utf-8")

def collect():
    r = callback("claim")
    if r.get("skip"):
        with open(ENV["GITHUB_OUTPUT"],"a") as f: f.write("skip=true\n")
        return
    spec = r["spec"]
    rel = SECTIONS[spec["section"]]+"/"+str(uuid.UUID(ENV["TASK_ID"]))
    path = Path("docs") / (rel+".md")
    STATE.write_text(json.dumps({"path":rel+".html"}))
    if not path.exists():
        callback("progress",message="检索并核对原文")
        write_article(path,spec,summarize(spec,find_sources(spec)))
    callback("progress",message="构建并发布")

if __name__ == "__main__":
    try:
        if sys.argv[1] == "collect": collect()
        elif sys.argv[1] == "failure": callback("failure",message="构建或发布失败，请检查执行记录 "+ENV["GITHUB_RUN_ID"])
        elif sys.argv[1] == "success": callback("success",message="Pages 已发布，提交 "+ENV["CONTENT_SHA"],**json.loads(STATE.read_text()))
    except Exception as exc:
        if sys.argv[1] == "collect" and STATE.exists():
            detail = str(exc) if type(exc) is ValueError else type(exc).__name__+" "+str(getattr(exc,"code",""))
            callback("failure", message="收录失败："+detail[:350])
        raise SystemExit("任务失败：" + type(exc).__name__)
