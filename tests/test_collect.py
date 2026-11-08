import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import collect

class CollectionTests(unittest.TestCase):
    def test_verified_source_and_safe_rendering(self):
        spec = {"count":1,"criteria":"入门","title":"测试"}
        docs = [{"url":"https://example.edu/intro","text":"verified evidence from source"}]
        result = '{"items":[{"index":0,"evidence":"verified evidence","title":"{{boom}}","summary":"<script>alert(1)</script>"}]}'
        with patch.object(collect,"request",return_value={"choices":[{"message":{"content":result}}]}), patch.dict(collect.ENV,MODEL_URL="unused",MODEL_KEY="unused",MODEL_NAME="test"):
            items = collect.summarize(spec,docs)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory)/"test.md"
            collect.write_article(path,spec,items)
            self.assertNotIn("<script>",path.read_text(encoding="utf8"))
            self.assertNotIn("{{",path.read_text(encoding="utf8"))
        self.assertFalse(collect.allowed("https://evil.com/?host=mit.edu",collect.ALLOWED))
        with self.assertRaises(ValueError): collect.summarize(spec,[])

if __name__ == "__main__": unittest.main()
