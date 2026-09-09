"""Normalization helpers used to compare website records against CRM records.

The CRM writes addresses the way whoever typed them felt like that day
("4930 W Lake Rd" vs "4930 West Lake Road"), so nothing can be compared raw.
Everything here is deliberately conservative: it collapses formatting noise
without ever collapsing two genuinely different values together.
"""

import re
from difflib import SequenceMatcher

_SUFFIX = {
    "street": "st", "st": "st",
    "road": "rd", "rd": "rd",
    "drive": "dr", "dr": "dr",
    "avenue": "ave", "ave": "ave", "av": "ave",
    "boulevard": "blvd", "blvd": "blvd", "blvd,": "blvd",
    "lane": "ln", "ln": "ln",
    "pike": "pk", "pk": "pk",
    "court": "ct", "ct": "ct",
    "circle": "cir", "cir": "cir",
    "place": "pl", "pl": "pl",
    "parkway": "pkwy", "pkwy": "pkwy",
    "highway": "hwy", "hwy": "hwy",
    "terrace": "ter", "ter": "ter",
    "trail": "trl", "trl": "trl",
    "square": "sq", "sq": "sq",
    "route": "rt", "rt": "rt",
    "way": "way",
}

_DIRECTION = {
    "north": "n", "n": "n",
    "south": "s", "s": "s",
    "east": "e", "e": "e",
    "west": "w", "w": "w",
    "northeast": "ne", "ne": "ne",
    "northwest": "nw", "nw": "nw",
    "southeast": "se", "se": "se",
    "southwest": "sw", "sw": "sw",
}

_STREET_TOKENS = {**_SUFFIX, **_DIRECTION}

_PO_BOX_RE = re.compile(r"\b(p\.?\s*o\.?\s*box|post\s+office\s+box)\b", re.I)

# Words that carry no identifying weight in a facility name.
_NAME_STOPWORDS = {"the", "of", "at", "and", "a", "an"}


def norm_street(value):
    """Canonical form of a street line: lowercase, suffixes and directionals
    reduced to a single spelling."""
    if not value:
        return ""
    text = value.lower().replace(".", " ").replace(",", " ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(_STREET_TOKENS.get(tok, tok) for tok in text.split())


def is_po_box(value):
    """True when a street line is a mailing box rather than a physical address.

    These cannot be address-matched and must fall through to a name match.
    """
    return bool(value and _PO_BOX_RE.search(value))


def norm_city(value):
    return " ".join((value or "").lower().split())


def norm_zip(value):
    digits = re.sub(r"\D", "", value or "")
    return digits[:5]


def norm_state(value):
    return (value or "").strip().upper()[:2]


def norm_phone(value):
    """Last 10 digits, so (216) 659-9837 and 216-659-9837 compare equal."""
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def norm_name(value):
    """Canonical facility name for similarity scoring.

    Folds the spelling variants that actually occur in this data set
    (Centre/Center, Health Care/Healthcare, Rehabilitation/Rehab) and drops
    filler words, so "Bellhaven Healthcare Centre of Ashland" and "Bellhaven
    Health Care Center of Ashland" reduce to the same string.
    """
    if not value:
        return ""
    text = value.lower().replace("&", " and ")
    text = re.sub(r"\(.*?\)", " ", text)          # strip "(Parent Account)"
    text = re.sub(r"\bcentre\b", "center", text)
    text = re.sub(r"\bhealth\s+care\b", "healthcare", text)
    text = re.sub(r"\brehabilitation\b", "rehab", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    tokens = [t for t in text.split() if t and t not in _NAME_STOPWORDS]
    return " ".join(tokens)


def name_sim(left, right):
    """0..1 similarity that tolerates word reordering and extra qualifiers."""
    a = set(norm_name(left).split())
    b = set(norm_name(right).split())
    if not a or not b:
        return 0.0
    jaccard = len(a & b) / len(a | b)
    sequence = SequenceMatcher(
        None, " ".join(sorted(a)), " ".join(sorted(b))
    ).ratio()
    return round(max(jaccard, sequence), 4)


# The website and the CRM use different care vocabularies. Without this map a
# naive field diff proposes a care_type change on nearly every facility.
CARE_TYPE_FROM_SITE = {
    "short-term rehabilitation & nursing": "Skilled Nursing",
    "short term rehabilitation & nursing": "Skilled Nursing",
    "skilled nursing": "Skilled Nursing",
    "assisted living": "Assisted Living",
    "memory support": "Memory Care",
    "memory care": "Memory Care",
    "independent living": "Independent Living",
}


def map_care_types(labels):
    """Website care badges -> CRM care_type values, order preserved."""
    out = []
    for label in labels or []:
        mapped = CARE_TYPE_FROM_SITE.get(" ".join(label.strip().lower().split()))
        if mapped and mapped not in out:
            out.append(mapped)
    return out


def address_key(street, zip_code):
    """Join key for confident address matching, or None if unusable."""
    if is_po_box(street):
        return None
    street_key = norm_street(street)
    zip_key = norm_zip(zip_code)
    if not street_key or not zip_key:
        return None
    return (street_key, zip_key)
