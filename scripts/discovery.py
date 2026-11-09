"""Discover actual links from public documentation directories when Brave is unavailable."""
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

ROOT = "https://www.contest.comap.com/undergraduate/contests/mcm/"
GUIDES = (
    "https://scikit-learn.org/stable/user_guide.html",
    "https://docs.scipy.org/doc/scipy/reference/optimize.html",
    "https://developers.google.com/optimization",
)
ALIASES = {"线性规划":"linear programming linprog", "整数规划":"integer programming milp",
           "聚类":"clustering cluster", "回归":"regression", "最短路径":"shortest path",
           "优化":"optimization optimize", "交叉验证":"cross validation", "随机森林":"forest",
           "时间序列":"time series", "支持向量":"svm support vector", "预测":"prediction forecasting",
           "赛程":"calendar dates", "报名":"registration", "规则":"rules instructions"}


def discover(spec):
    contest = spec["section"] in ("赛程消息", "历年赛题收集")
    query = " ".join(str(spec.get(key, "")) for key in ("query","criteria","title"))
    query += " " + " ".join(words for term,words in ALIASES.items() if term in query)
    terms = set(re.findall(r"[a-z0-9]+", query.lower())) - {"the","and","for","official","with","model"}
    catalogs = [ROOT, ROOT+"previous-contests.php"] if contest else list(GUIDES)
    if contest:
        for year in sorted(set(re.findall(r"\b20\d\d\b",query)))[-8:]:
            catalogs.insert(0,ROOT+"contests/"+year+"/problems/")
    scored = {}
    for page in catalogs:
        try:
            with urllib.request.urlopen(urllib.request.Request(page,headers={"User-Agent":"mcm-study-hub/1"}),timeout=10) as resp:
                soup = BeautifulSoup(resp.read(1500000),"html.parser")
        except (OSError,ValueError):
            continue
        for anchor in soup.select("a[href]"):
            link = urllib.parse.urldefrag(urllib.parse.urljoin(page,anchor["href"]))[0]
            host = urllib.parse.urlsplit(link).hostname
            if host != urllib.parse.urlsplit(page).hostname and not (contest and host=="www.comap.org"):
                continue
            if not link.startswith("https://") or "?" in link or link.endswith((".png",".jpg",".zip")):
                continue
            words=set(re.findall(r"[a-z0-9]+",(anchor.get_text(" ",strip=True)+" "+urllib.parse.urlsplit(link).path).lower()))
            score=len(terms & words)
            if score:scored[link]=max(scored.get(link,0),score)
    if not scored:
        raise ValueError("官方目录未找到匹配来源，请给出原文链接或配置 Brave SEARCH_KEY 扩大检索范围")
    return sorted(scored,key=scored.get,reverse=True)[:24]
