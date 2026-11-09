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


def search_pages(spec):
    if spec.get("urls"):
        yield spec["urls"]
        return
    if not ENV.get("SEARCH_KEY"):
        raise ValueError("自动搜索缺少 GitHub Actions Secret SEARCH_KEY，可改用指定链接")
    query = spec["query"]
    if spec["section"] in ("赛程消息","历年赛题收集"):
        query += " (site:comap.com OR site:comap.org)"
    for offset in range(10):
        params = urllib.parse.urlencode({"q":query,"count":20,"offset":offset})
        hits = request("https://api.search.brave.com/res/v1/web/search?"+params,
                       headers={"X-Subscription-Token":ENV["SEARCH_KEY"],"Accept":"application/json"})
        urls = [hit["url"] for hit in hits.get("web",{}).get("results",[]) if hit.get("url")]
        if not urls:
            return
        yield urls
        if not hits.get("query",{}).get("more_results_available",len(urls)==20):
            return


def source_candidates(spec, seen):
    domains = ("comap.com", "comap.org") if spec["section"] in ("赛程消息","历年赛题收集") else ALLOWED
    permissions = set(json.loads(Path("content-policy.json").read_text(encoding="utf8"))["full_text_urls"])
    if spec.get("letters") and not spec.get("urls"):
        year = spec["year"]
        base = f"https://www.contest.comap.com/undergraduate/contests/mcm/contests/{year}/problems/"
        links = [base+f"{year}_{'MCM' if letter in 'ABC' else 'ICM'}_Problem_{letter}.pdf" for letter in spec["letters"]]
        from itertools import chain
        pages = chain([links], search_pages(spec)) if ENV.get("SEARCH_KEY") else [links]
    else:
        pages = search_pages(spec)
    for urls in pages:
        for url in urls:
            link = urllib.parse.urldefrag(url)[0]
            if link in seen:
                continue
            seen.add(link)
            approved = link in permissions
            hosts = domains
            if approved and spec["section"] not in ("赛程消息","历年赛题收集"):
                hosts = (*domains,urllib.parse.urlsplit(link).hostname or "")
            if not allowed(link,hosts):
                continue
            if spec.get("letters") and not urllib.parse.urlsplit(link).path.lower().endswith(".pdf"):
                continue
            try:
                blocks = read_source(link, hosts)
            except (OSError, ValueError, LookupError):
                continue
            text = "\n".join(value for _,value in blocks)
            if len(text.strip()) <= 30:
                continue
            doc = {"url":link,"text":text[:10000],"body":markdown(blocks) if approved else ""}
            if spec.get("letters"):
                header = text[:1800]
                identity = re.search(r"\bProblem\s+([A-F])\b",header,re.I)
                if not identity or str(spec["year"]) not in header or identity[1].upper() not in spec["letters"]:
                    continue
                doc["letter"] = identity[1].upper()
            yield doc


def find_sources(spec):
    from itertools import islice
    return list(islice(source_candidates(spec,set()),spec["count"]+5))

def summarize(spec, docs, *, require_count=True):
    if require_count and len(docs) < spec["count"]: raise ValueError("可读取的原文不足，目标 " + str(spec["count"]) + " 条")
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
        selected[i] = {**item,"letter":docs[i].get("letter"),"url":docs[i]["url"],"body":docs[i].get("body",""),
                       "notes":[p for p in notes if isinstance(p,str) and p.strip()] if isinstance(notes,list) else []}
    if require_count and len(selected) < spec["count"]: raise ValueError("符合任务条件且可核对原文的来源不足")
    matches = list(selected.values())
    return matches[:spec["count"]] if require_count else matches



def write_article(path, spec, items):
    rows = ["# "+plain(spec["title"]), "", "收录条件："+plain(spec["criteria"]), ""]
    previous = None
    grouped = len(spec.get("batches",[])) > 1
    for item in items:
        if grouped and item.get("batch_label") != previous:
            previous = item["batch_label"]
            rows += ["## "+plain(previous),""]
        rows += [("### " if grouped else "## ")+plain(item["title"]), "", plain(item["summary"]), ""]
        for note in item.get("notes",[]):
            rows += [plain(note), ""]
        if item.get("body"):
            rows += ["### 收录正文", "", item["body"], ""]
        rows += ["> "+plain(item["evidence"][:160]), "",
                 '<a href="'+html.escape(item["url"],quote=True)+'" rel="noopener noreferrer">阅读原文</a>', ""]
    path.write_text("\n".join(rows), encoding="utf-8")

def collect_batches(spec, notify=callback):
    from itertools import islice
    plan = spec.get("batches") or [{"label":"收录","count":spec["count"],"query":spec["query"]}]
    if sum(b["count"] for b in plan) != spec["count"] or any(not 1 <= b["count"] <= 8 for b in plan):
        raise ValueError("分批数量与已审批目标不一致")
    used = set()
    archived = set()
    if not spec.get("update"):
        if __package__:
            from .knowledge import passages
        else:
            from knowledge import passages
        for passage in passages():
            archived.update(urllib.parse.urldefrag(url)[0] for url in re.findall(
                r'https?://[^\s<>"\)]+', passage["body"]))

    all_items = []
    for i, batch in enumerate(plan):
        prefix = f"第 {i+1}/{len(plan)} 批 · {batch['label']}"
        batch_spec = {**spec,**batch}
        batch_spec.pop("batches",None)
        items = notify("load_batch",batch=i)["items"]
        if items is None:
            notify("progress",message=prefix+" · 正在收录")
            candidates = source_candidates(batch_spec,used | archived)
            items = []
            letters = set()
            try:
                while len(items) < batch["count"]:
                    limit = batch["count"]-len(items) if batch.get("letters") else 8
                    window = list(islice(candidates,limit))
                    if not window:
                        break
                    for item in summarize(batch_spec,window,require_count=False):
                        letter = item.get("letter")
                        if batch.get("letters") and (not letter or letter in letters):
                            continue
                        letters.add(letter)
                        items.append(item)
                        if len(items)==batch["count"]:
                            break
            except (ValueError, urllib.error.HTTPError) as error:
                raise ValueError(f"{prefix}：{error}") from error
            if len(items)!=batch["count"]:
                missing = "".join(letter for letter in batch.get("letters","") if letter not in letters)
                raise ValueError(f"{prefix}：排除知识库已有来源后匹配 {len(items)}/{batch['count']} 条"+(f"，缺 {missing} 题" if missing else ""))
            if batch.get("letters"):
                items.sort(key=lambda item: item["letter"])
            saved = notify("save_batch",batch=i,items=items)["saved"]
            stage = "已完成" if saved else "已完成（正文过大，重试需重新采集）"
        else:
            stage = "沿用已完成批次"
        urls = {item["url"] for item in items}
        if urls & archived:
            raise ValueError(f"{prefix}：已完成批次的来源现已入库，请重新检查收录范围")
        if len(urls)!=batch["count"] or used.intersection(urls):
            raise ValueError(f"{prefix}：来源重复或数量不符")
        used.update(urls)
        for item in items:
            all_items.append({**item,"batch_label":batch["label"]})
        notify("progress",message=f"{prefix} · {stage} · 共 {len(used)}/{spec['count']} 条")
    return all_items


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
        write_article(path,spec,collect_batches(spec))
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
