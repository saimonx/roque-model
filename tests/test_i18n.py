"""The web page's two languages must say the same things.

site/assets/i18n.js holds every text of the page in Spanish (es) and English (en). A key missing
in one language would show up empty, and a {placeholder} missing would drop a number. Node reads
the file (it is JavaScript); the test is skipped where Node is not installed.
"""

import json
import re
import shutil
import subprocess

import pytest

from roque_forecast import config

I18N = config.PROJECT_DIR / "site" / "assets" / "i18n.js"

# Prints every text as {"es": {"a.b": "..."}, "en": {...}}, nested keys joined with dots.
DUMP = """
global.window = {};
require(process.argv[1]);
const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) =>
  v && typeof v === "object" ? flat(v, p + k + ".") : [[p + k, String(v)]]);
const out = {};
for (const lang of Object.keys(window.I18N)) out[lang] = Object.fromEntries(flat(window.I18N[lang]));
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def texts() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", DUMP, str(I18N)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_both_languages_have_the_same_keys(texts):
    assert set(texts) == {"es", "en"}
    assert set(texts["es"]) == set(texts["en"]), set(texts["es"]) ^ set(texts["en"])


def test_both_languages_have_the_same_placeholders_and_links(texts):
    def marks(text: str) -> tuple:
        return sorted(re.findall(r"\{\w+\}", text)), len(re.findall(r"href=", text))

    for key, es in texts["es"].items():
        assert marks(es) == marks(texts["en"][key]), key


def test_no_text_is_empty(texts):
    for lang, entries in texts.items():
        empty = [k for k, v in entries.items() if not v.strip()]
        assert not empty, (lang, empty)
