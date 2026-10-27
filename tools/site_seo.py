"""Deterministic metadata for the public benchmark site; no measured values."""
import html
import json
from pathlib import Path
from urllib.parse import quote

BASE = 'https://yasha1971-coder.github.io/hw-apex-bench/'
TITLE = 'hw-apex-bench — random access into compressed data: bgzip, zstd-seekable, ACEAPEX, measured'
# Google Search Console ownership file: exact name and content Google expects; a plain-text file, not a page.
GOOGLE_VERIFICATION = 'googlecb044b428b198ccc.html'
GOOGLE_VERIFICATION_TEXT = 'google-site-verification: googlecb044b428b198ccc.html\n'
DESCRIPTION = 'Compressed-data benchmarks: window law, cohort access and corruption; hardware recorded per evidence. Evidence, not estimates.'
LINKS = [('hw-apex-bench', 'https://github.com/yasha1971-coder/hw-apex-bench'),
         ('aceapex', 'https://github.com/yasha1971-coder/aceapex'),
         ('panvram', 'https://github.com/yasha1971-coder/panvram'),
         ('Methodology', 'https://arxiv.org/abs/2609.16731'),
         ('Dataset DOI', 'https://doi.org/10.5281/zenodo.22713364')]

def canonical(page):
    return BASE + quote(page.removesuffix('index.html'), safe='/')

def dataset():
    return {'@context': 'https://schema.org', '@type': 'Dataset',
            'name': 'hw-apex-bench', 'description': DESCRIPTION, 'url': BASE,
            'identifier': 'https://doi.org/10.5281/zenodo.22713364',
            'creator': {'@type': 'Person', 'name': 'Yakiv Shavidze',
                        '@id': 'https://orcid.org/0009-0008-3622-3448'},
            'license': 'https://creativecommons.org/licenses/by/4.0/'}

def head(page):
    esc = html.escape
    tags = '<title>'+esc(TITLE)+'</title>'
    for attr, key, value in [('name','description',DESCRIPTION),
        ('property','og:title',TITLE), ('property','og:description',DESCRIPTION),
        ('property','og:type','website'), ('property','og:url',canonical(page)),
        ('property','og:image',BASE+'assets/social-card.png'),
        ('property','og:image:width','1200'), ('property','og:image:height','630'),
        ('property','og:image:alt','hw-apex-bench: window law, cohort access, corruption'),
        ('name','twitter:card','summary_large_image')]:
        tags += f'<meta {attr}="{key}" content="{esc(value, quote=True)}">'
    tags += '<link rel="canonical" href="'+canonical(page)+'">'
    return tags+'<script type="application/ld+json">'+json.dumps(dataset(),sort_keys=True).replace('<','\\u003c')+'</script>'

def footer():
    return '<nav aria-label="Project references">'+' · '.join(
        '<a href="'+url+'">'+html.escape(label)+'</a>' for label,url in LINKS)+'</nav>'

def write(root, pages):
    root = Path(root)
    entries = ''.join('<url><loc>'+html.escape(canonical(p))+'</loc></url>' for p in sorted(pages))
    (root/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+entries+'</urlset>\n',encoding='utf-8')
    (root/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+BASE+'sitemap.xml\n',encoding='utf-8')
    (root/'assets/social-card.png').write_bytes((Path(__file__).parent/'assets/social-card.png').read_bytes())
    (root/GOOGLE_VERIFICATION).write_text(GOOGLE_VERIFICATION_TEXT, encoding='utf-8')
