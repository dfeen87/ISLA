"""Ensure README listening links resolve to committed FLAC audio, not GitHub blob pages.

This check is deliberately offline: it verifies the URLs and actual repo files
without making CI depend on GitHub's CDN or a browser's audio codec support.
"""

from pathlib import Path
import re
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
AUDIO_URL = re.compile(r"\]\(([^)\s]+\.flac(?:\?[^)\s]*)?)\)")
PREFIX = "/dfeen87/ISLA/main/docs/audio/"


def test_readme_audio_links_resolve_to_real_flac_assets():
    readme = README.read_text(encoding="utf-8")
    links = AUDIO_URL.findall(readme)

    # Four listening collections: two classical, two electronic, and a
    # four-sample historical piano baseline. Prevent accidental omission.
    assert len(links) >= 34, "README lost one or more listening links"
    assert len(set(links)) == len(links), "Duplicate README audio link"

    for link in links:
        url = urlsplit(link)
        assert url.scheme == "https", link
        assert url.netloc == "raw.githubusercontent.com", link
        assert url.path.startswith(PREFIX), link
        assert not url.query and not url.fragment, link

        local_path = ROOT / "docs" / "audio" / url.path[len(PREFIX):]
        assert local_path.is_file(), f"Untracked or missing audio target: {link}"
        with local_path.open("rb") as audio:
            assert audio.read(4) == b"fLaC", f"Not a FLAC recording: {link}"
