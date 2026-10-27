import json
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import html5lib
from tools import site_seo

class SEO(unittest.TestCase):
    def test_generated_metadata_and_sitemap(self):
        root=Path(__file__).parent/'fixtures/site/expected'
        pages=sorted(root.rglob('*.html'))
        urls=[e.text for e in ET.parse(root/'sitemap.xml').findall('.//{*}loc')]
        self.assertEqual(urls,[site_seo.canonical(p.relative_to(root).as_posix()) for p in pages])
        self.assertLessEqual(len(site_seo.DESCRIPTION),160)
        for p in pages:
            t=html5lib.HTMLParser(strict=True,namespaceHTMLElements=False).parse(p.read_text())
            self.assertEqual(t.find('./head/title').text,site_seo.TITLE)
            self.assertEqual(json.loads(t.find('./head/script').text),site_seo.dataset())
            self.assertEqual(t.find('./head/link[@rel="canonical"]').get('href'),site_seo.canonical(p.relative_to(root).as_posix()))
            self.assertEqual(t.find('./head/meta[@name="description"]').get('content'),site_seo.DESCRIPTION)
            for _,url in site_seo.LINKS:
                self.assertIsNotNone(t.find('.//footer//a[@href="'+url+'"]'))
        self.assertIn('Sitemap: '+site_seo.BASE+'sitemap.xml',(root/'robots.txt').read_text())
        image=(root/'assets/social-card.png').read_bytes()
        self.assertEqual(image[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II',image[16:24]),(1200,630))
