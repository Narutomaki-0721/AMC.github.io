from unittest import TestCase
from unittest.mock import patch
from scripts.collect import collect_batches

class BatchTests(TestCase):
    def test_resume_and_require_all_years(self):
        plan = {"section":"历年赛题收集","count":4,"batches":[
            {"label":str(year),"year":year,"letters":"AB","count":2,"query":str(year)} for year in (2020,2021)]}
        cache, visits = {}, []
        def runner(event, **data):
            if event=="load_batch": return {"items":cache.get(data["batch"])}
            if event=="save_batch": cache[data["batch"]]=data["items"]; return {"saved":True}
        missing = True
        def docs(spec,seen):
            visits.append(spec["year"])
            for letter in spec["letters"]:
                if missing and spec["year"]==2021 and letter=="B": continue
                yield {"url":f"https://example.edu/{spec['year']}/{letter}","letter":letter}
        with patch("scripts.collect.source_candidates",docs), patch("scripts.collect.summarize",side_effect=lambda _,window,**opts: window):
            with self.assertRaisesRegex(ValueError,"缺 B 题"): collect_batches(plan,runner)
            self.assertEqual(list(cache),[0])
            missing = False
            items = collect_batches(plan,runner)
        self.assertEqual(visits,[2020,2021,2021])
        self.assertEqual(len({item["url"] for item in items}),4)
