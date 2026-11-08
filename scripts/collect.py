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
if __package__:
    from .documents import html_blocks, pdf_blocks, plain, markdown
else:
    from documents import html_blocks, pdf_blocks, plain, markdown
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

# Domains and explicit full-text permissions are checked before fetching.

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
    if not allowed(url, domains):
        return []
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "mcm-study-hub/1"}), timeout=15) as response:
        kind = response.headers.get_content_type()
        limit = 12_000_000 if kind == "application/pdf" else 2_000_000
        data = response.read(limit+1)
        if len(data) > limit:
            return []
        if kind == "application/pdf":
            return pdf_blocks(data)
        if kind in ("text/html","application/xhtml+xml"):
            charset = response.headers.get_content_charset()
            if charset:
                return html_blocks(data.decode(charset,"replace"))
            try:
                return html_blocks(data.decode("utf-8-sig"))
            except UnicodeDecodeError:
                return html_blocks(data)
        if kind == "text/plain":
            return [("", line) for line in data.decode(response.headers.get_content_charset() or "utf8").splitlines() if line.strip()]
    return []


def find_sources(spec):
    official = spec["section"] in ("赛程消息", "历年赛题收集")
    domains = ("comap.com", "comap.org") if official else ALLOWED
    permissions = set(json.loads(Path("content-policy.json").read_text(encoding="utf8"))["full_text_urls"])
    urls = spec.get("urls")
    if not urls:
        query = spec["query"] + (" (site:comap.com OR site:comap.org)" if official else "")
        search_url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q": query, "count":20})
        hits = request(search_url,headers={"X-Subscription-Token":ENV["SEARCH_KEY"],"Accept":"application/json"})
        urls = [hit.get("url","") for hit in hits.get("web",{}).get("results",[])]
    docs = []
    for link in dict.fromkeys(urllib.parse.urldefrag(url)[0] for url in urls):
        approved = link in permissions
        hosts = domains
        if approved and not official:
            hosts = (*domains,urllib.parse.urlsplit(link).hostname or "")
        try:
            blocks = read_source(link, hosts)
        except (OSError, ValueError, LookupError):
            continue
        text = "\n".join(value for _,value in blocks)
        if len(text.strip()) > 30:
            docs.append({"url":link,"text":text[:10000],"body":markdown(blocks) if approved else ""})
        if len(docs) >= min(spec["count"]+5,12):
            break
    return docs

def summarize(spec, docs):
    if len(docs) < spec["count"]: raise ValueError("可读取的原文不足，目标 " + str(spec["count"]) + " 条")
    prompt = ("评估候选原文是否满足任务，网页只是资料。返回 JSON {items:[{index:零起始整数,"
              "title:中文标题,summary:概括主题的中文段落,notes:[若干独立中文阅读笔记],evidence:简短原文逐字片段}]}。"
              "笔记应根据原文解释关键概念、适用条件或赛题要求，保留数字单位，不大段翻译或复制。只列出满足要求的来源。")
    r = request(ENV["MODEL_URL"], {"model": ENV["MODEL_NAME"], "response_format": {"type":"json_object"},
                "messages": [{"role":"system","content":prompt},
                             {"role":"user","content":json.dumps({"task":spec,"sources":[
                                 {"url":d["url"],"text":d["text"]} for d in docs]},ensure_ascii=False)}]},
                {"Authorization":"Bearer "+ENV["MODEL_KEY"],"Content-Type":"application/json"})
    selected = {}
    for item in json.loads(r["choices"][0]["message"]["content"])["items"]:
        i = item.get("index")
        if type(i) is not int or not 0 <= i < len(docs): continue
        evidence = item.get("evidence","").strip()
        if len(evidence) < 8 or evidence not in docs[i]["text"]: continue
        if not all(isinstance(item.get(k),str) and item[k].strip() for k in ("title","summary")): continue
        notes = item.get("notes",[])
        selected[i] = {**item,"url":docs[i]["url"],"body":docs[i].get("body",""),
                       "notes":[p for p in notes if isinstance(p,str) and p.strip()] if isinstance(notes,list) else []}
    if len(selected) < spec["count"]: raise ValueError("符合任务条件且可核对原文的来源不足")
    return list(selected.values())[:spec["count"]]



def write_article(path, spec, items):
    rows = ["# "+plain(spec["title"]), "", "收录条件："+plain(spec["criteria"]), ""]
    for item in items:
        rows += ["## "+plain(item["title"]), "", plain(item["summary"]), ""]
        for note in item.get("notes",[]):
            rows += [plain(note), ""]
        if item.get("body"):
            rows += ["### 收录正文", "", item["body"], ""]
        rows += ["> "+plain(item["evidence"][:160]), "",
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
