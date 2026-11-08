from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from scripts.documents import import_uploads, html_blocks, markdown, pdf_blocks
from scripts.collect import find_sources, write_article

class DocumentImportTests(unittest.TestCase):
    def test_word_text_update_and_removal(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            root = Path(tmp)
            folder = root / "docs/practice"
            folder.mkdir(parents=True)
            source = folder / "训练.docx"
            with ZipFile(source,"w") as zipped:
                zipped.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>练习正文 {{ 2+2 }}</w:t></w:r></w:p></w:body></w:document>')
            import_uploads(root)
            converted = folder / "训练.docx.imported.md"
            text = converted.read_text(encoding="utf8")
            self.assertIn("练习正文",text)
            self.assertNotIn("{{",text)
            self.assertIn("blob/main/docs/practice/",text)
            (folder/"复盘.txt").write_text("新的复盘",encoding="utf8")
            source.unlink()
            import_uploads(root)
            self.assertFalse(converted.exists())
            self.assertIn("新的复盘",(folder/"复盘.txt.imported.md").read_text(encoding="utf8"))

    def test_pdf_text_is_readable(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=200,height=200)
        font = DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"):writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 10 100 Td (MCM training) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)
        output = BytesIO()
        writer.write(output)
        self.assertIn("MCM training", markdown(pdf_blocks(output.getvalue())))

    def test_only_approved_urls_publish_source_body(self):
        url = "https://example.edu/intro"
        blocks = html_blocks(b"<nav>advert</nav><article><h1>Integer models</h1><p>Useful material for mathematical modeling practice.</p></article>")
        spec = {"section":"参考资料文档","urls":[url],"count":1,"title":"外部资料","criteria":"入门"}
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            for approved in (False,True):
                permissions = '{"full_text_urls":["'+url+'"]}' if approved else '{"full_text_urls":[]}'
                with patch("scripts.collect.Path.read_text",return_value=permissions), patch("scripts.collect.read_source",return_value=blocks):
                    doc = find_sources(spec)[0]
                output = Path(tmp)/"task.md"
                write_article(output,spec,[{**doc,"notes":["应用条件"],"summary":"导读","title":"资料","evidence":"mathematical"}])
                text = output.read_text(encoding="utf8")
                self.assertIn("应用条件",text)
                self.assertEqual("Useful material" in text,approved)
                self.assertNotIn("advert",text)
