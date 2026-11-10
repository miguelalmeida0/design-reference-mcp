"""Audited seed URLs from the user's saved inspiration library.

All URLs below are explicit reference sources, not a general-purpose web crawler.
Individual project discovery is restricted to the allowed public hosts.
"""
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    url: str
    category: str


SOURCES = [
    Source("design-everywhere", "Design Everywhere", "https://designeverywhere.co/", "gallery"),
    Source("design-everywhere-library", "Design Everywhere library", "https://designeverywhere.co/library/1", "gallery"),
    Source("recent", "Recent Design", "https://recent.design/", "gallery"),
    Source("cosmos", "Cosmos", "https://www.cosmos.so/", "gallery"),
    Source("mindsparkle", "Mindsparkle", "https://mindsparklemag.com/", "gallery"),
    Source("motionin", "Motion in Design", "https://motionin.design/", "gallery"),
    Source("motionsites", "MotionSites", "https://motionsites.ai/", "gallery"),
    Source("landdding", "Landdding", "https://landdding.com/", "gallery"),
    Source("archives", "Archives.design", "https://archives.design/", "archive"),
    Source("designreviewed", "Design Reviewed", "https://designreviewed.com/archive/", "archive"),
    Source("cari", "CARI Aesthetics", "https://cari.institute/aesthetics", "archive"),
    Source("unsection", "Unsection", "https://www.unsection.com/", "gallery"),
    Source("navbar", "Navbar Gallery", "https://www.navbar.gallery/browse", "gallery"),
    Source("raivcoo", "Raivcoo", "https://raivcoo.com/", "gallery"),
    Source("cta", "CTA Gallery", "https://cta.gallery/", "gallery"),
    Source("designspells", "Design Spells", "https://designspells.com/", "gallery"),
    Source("emmiwu", "Emmi Wu", "https://emmiwu.com/", "project"),
    Source("alejandro", "Alejandro HA", "https://alejandroha.com/", "project"),
    Source("robot", "The Robot and Me", "https://therobotand.me/", "project"),
    Source("huy", "Huy ML", "https://huyml.co/", "project"),
    Source("madeinevolve", "Made in Evolve", "https://madeinevolve.com/", "project"),
    Source("brethren", "Brethren Design Co.", "https://www.brethrendesignco.com/", "project"),
    Source("lando", "Lando Norris", "https://landonorris.com/", "project"),
    Source("air", "Air", "https://air.inc/", "project"),
    Source("inkwell", "Inkwell", "https://inkwell.tech/", "project"),
    Source("vshslv", "VSHSLV", "https://vshslv.com/", "project"),
    Source("thunderstone", "Thunderstone Specimen", "https://recent.design/i/uilo6kx-thunderstone-specimen", "specific"),
    Source("dirt", "Dirt", "https://recent.design/i/1of4fz4-dirt", "specific"),
    Source("planet-motion", "Planet Select Motion", "https://recent.design/i/d0q7bmx-planet-select-motion", "specific"),
    Source("cosmos-mobile", "Cosmos mobile UX", "https://www.cosmos.so/search/elements/mobile%20ux%20design", "specific"),
    Source("cap-dept", "CAP Dept", "https://designeverywhere.co/work/cap-dept", "specific"),
    Source("tezza", "Tezza", "https://designeverywhere.co/work/tezza", "specific"),
    Source("design-spells-interactions", "Design Spells interactions", "https://designspells.com/?tag=interaction", "gallery"),
]

# A fixed public-website allowlist. No arbitrary hosts, private IPs, or user-supplied URLs.
HOSTS = frozenset(urlparse(s.url).hostname for s in SOURCES if urlparse(s.url).hostname)


def is_allowed_reference_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return (p.scheme == "https" and p.hostname in HOSTS
                and p.username is None and p.password is None
                and (p.port is None or p.port == 443)
                and len(url) <= 2048)
    except (ValueError, AttributeError):
        return False

