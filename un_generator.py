import random
import re
import string
from typing import List, Set, Optional, Tuple
from wordfreq import top_n_list
from mailer import check_avail_un

BANNED_SUBSTR = {
    "admin", "support", "security", "billing", "abuse", "postmaster",
    "noreply", "microsoft", "outlook", "hotmail",
}

ALLOWED = set(string.ascii_lowercase + string.digits + "._")

def sanitize_localpart(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch in ALLOWED)
    s = re.sub(r"[._]{2,}", ".", s)   # схлопнуть разделители
    s = s.strip("._")
    return s

def is_valid_localpart(s: str, min_len: int, max_len: int) -> bool:
    if not (min_len <= len(s) <= max_len):
        return False
    if s[0] in "._" or s[-1] in "._":
        return False
    if ".." in s or "__" in s or "._" in s or "_." in s:
        return False
    if s.isdigit():
        return False
    for b in BANNED_SUBSTR:
        if b in s:
            return False
    return True

def build_word_pool_from_wordfreq(
    *,
    lang: str = "en",
    n: int = 120_000,     # можно больше
    min_word_len: int = 3,
    max_word_len: int = 12,
) -> List[str]:
    words = top_n_list(lang, n)
    pool: List[str] = []
    seen = set()

    for w in words:
        w = w.lower().strip()
        # слово должно быть “простым”: только латиница/цифры
        if not re.fullmatch(r"[a-z0-9]+", w):
            continue
        if not (min_word_len <= len(w) <= max_word_len):
            continue
        if any(b in w for b in BANNED_SUBSTR):
            continue
        if w not in seen:
            seen.add(w)
            pool.append(w)

    if not pool:
        raise RuntimeError("wordfreq pool is empty (filters too strict?)")
    return pool

def generate_human_outlook_username(
    pool: List[str],
    rng: random.Random,
    *,
    min_len: int = 8,
    max_len: int = 28,
    digits_min: int = 2,
    digits_max: int = 4,
) -> str:
    sep = rng.choice([".", "_"])

    w1 = rng.choice(pool)
    w2 = rng.choice(pool)

    dlen = rng.randint(digits_min, digits_max)
    digits = "".join(rng.choice(string.digits) for _ in range(dlen))

    # “человечные” паттерны
    patterns = [
        lambda: f"{w1}{sep}{w2}{digits}",
        lambda: f"{w1[0]}{sep}{w2}{digits}",
        lambda: f"{w1}{w2}{digits}",
        lambda: f"{w1}{digits}",
        lambda: f"{w1}{sep}{w2[0]}{digits}",
    ]

    for _ in range(50):
        cand = sanitize_localpart(rng.choice(patterns)())

        # подгон длины
        if len(cand) < min_len:
            cand = sanitize_localpart(cand + "mail" + str(rng.randint(10, 99)))
        if len(cand) > max_len:
            cand = cand[:max_len].strip("._")

        if is_valid_localpart(cand, min_len, max_len):
            return cand

    # если совсем не повезло
    raise RuntimeError("Failed to generate valid username after many tries")

def generate_many(
    count: int,
    *,
    seed: Optional[int] = None,
    ensure_unique: bool = True,
) -> List[str]:
    rng = random.Random(seed)
    pool = build_word_pool_from_wordfreq(lang="en", n=120_000)

    used: Set[str] = set()
    result: List[str] = []

    while len(result) < count:
        u = generate_human_outlook_username(pool, rng)
        if ensure_unique and u in used:
            continue
        used.add(u)
        result.append(u)

    return result

# ===== SINGLE USERNAME API =====

_WORD_POOL = None
_RNG = random.Random()

def generate_one_username(
    *,
    seed: Optional[int] = None,
    min_len: int = 8,
    max_len: int = 28,
    digits_min: int = 2,
    digits_max: int = 4,
) -> str:
    """
    Генерирует ОДИН Outlook-safe username.
    Использует wordfreq и человеческие паттерны.
    """

    global _WORD_POOL, _RNG

    if seed is not None:
        _RNG.seed(seed)

    if _WORD_POOL is None:
        _WORD_POOL = build_word_pool_from_wordfreq(
            lang="en",
            n=120_000,
            min_word_len=3,
            max_word_len=12,
        )

    return generate_human_outlook_username(
        _WORD_POOL,
        _RNG,
        min_len=min_len,
        max_len=max_len,
        digits_min=digits_min,
        digits_max=digits_max,
    )

def generate_unique_outlook_un():
    while True:
        un = generate_one_username()
        res = check_avail_un(un)
        if res:
            return un


# ================================
#  FIRST NAME/LAST NAME GENERATOR
# ================================

_FIRST_NAMES: Optional[List[str]] = None
_LAST_NAMES: Optional[List[str]] = None

def _load_names(path: str, *, min_len=2, max_len=16) -> List[str]:
    names = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            n = line.strip().lower()
            n = re.sub(r"[^a-z]", "", n)  # только латиница
            if min_len <= len(n) <= max_len:
                names.append(n)
    if not names:
        raise ValueError(f"No valid names in {path}")
    return names

def get_random_name(
    first_names_file: str = "names_list/first-names.txt",
    last_names_file: str = "names_list/last-names.txt",
    *,
    seed: int | None = None,
) -> Tuple[str, str]:
    """
    Возвращает (first_name, last_name)
    """

    global _FIRST_NAMES, _LAST_NAMES

    if seed is not None:
        random.seed(seed)

    if _FIRST_NAMES is None:
        _FIRST_NAMES = _load_names(first_names_file)

    if _LAST_NAMES is None:
        _LAST_NAMES = _load_names(last_names_file)

    first = random.choice(_FIRST_NAMES)
    last = random.choice(_LAST_NAMES)

    return first, last

if __name__ == "__main__":
    for u in generate_many(50, seed=42):
        print(u)