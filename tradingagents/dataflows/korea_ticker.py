"""Korean ticker resolution module.

Provides unified lookup for Korean stocks:
- Company name → stock code (e.g. "삼성전자" → "005930")
- Stock code → DART corp_code (e.g. "005930" → "00126380")
- Flexible query resolution: accepts name, stock code, or corp_code

Data source: DART corpCode.xml (downloaded via DART API, cached locally)
Fallback: built-in mapping of major Korean stocks for offline use.
"""

import io
import logging
import os
import json
import zipfile
from typing import Optional
from xml.etree import ElementTree

import requests

from tradingagents.dataflows.config import get_config

logger = logging.getLogger(__name__)

# Built-in fallback mapping for major Korean stocks (no API key needed)
# Format: {stock_code: {"corp_code": ..., "name": ..., "name_eng": ...}}
BUILTIN_TICKERS = {
    "005930": {"corp_code": "00126380", "name": "삼성전자", "name_eng": "Samsung Electronics"},
    "000660": {"corp_code": "00164779", "name": "SK하이닉스", "name_eng": "SK Hynix"},
    "042700": {"corp_code": "00161383", "name": "한미반도체", "name_eng": "Hanmi Semiconductor"},
    "240810": {"corp_code": "01135941", "name": "원익IPS", "name_eng": "Wonik IPS"},
    "035420": {"corp_code": "00266961", "name": "NAVER", "name_eng": "NAVER"},
    "005380": {"corp_code": "00164742", "name": "현대자동차", "name_eng": "Hyundai Motor"},
    "000270": {"corp_code": "00106641", "name": "기아", "name_eng": "Kia"},
    "006400": {"corp_code": "00126362", "name": "삼성SDI", "name_eng": "Samsung SDI"},
    "051910": {"corp_code": "00356361", "name": "LG화학", "name_eng": "LG Chem"},
    "035720": {"corp_code": "00258801", "name": "카카오", "name_eng": "Kakao"},
    "005490": {"corp_code": "00155319", "name": "POSCO홀딩스", "name_eng": "POSCO Holdings"},
    "055550": {"corp_code": "00382199", "name": "신한지주", "name_eng": "Shinhan Financial Group"},
    "105560": {"corp_code": "00688996", "name": "KB금융", "name_eng": "KB Financial Group"},
    "003670": {"corp_code": "00155276", "name": "포스코퓨처엠", "name_eng": "POSCO Future M"},
    "012330": {"corp_code": "00164788", "name": "현대모비스", "name_eng": "Hyundai Mobis"},
    "066570": {"corp_code": "00401731", "name": "LG전자", "name_eng": "LG Electronics"},
    "003550": {"corp_code": "00120021", "name": "LG", "name_eng": "LG Corp"},
    "034730": {"corp_code": "00181712", "name": "SK", "name_eng": "SK Inc"},
    "028260": {"corp_code": "00149655", "name": "삼성물산", "name_eng": "Samsung C&T"},
    "207940": {"corp_code": "00877059", "name": "삼성바이오로직스", "name_eng": "Samsung Biologics"},
    "068270": {"corp_code": "00413046", "name": "셀트리온", "name_eng": "Celltrion"},
    "373220": {"corp_code": "01515323", "name": "LG에너지솔루션", "name_eng": "LG Energy Solution"},
    "096770": {"corp_code": "00631518", "name": "SK이노베이션", "name_eng": "SK Innovation"},
    "017670": {"corp_code": "00159023", "name": "SK텔레콤", "name_eng": "SK Telecom"},
    "030200": {"corp_code": "00190321", "name": "케이티", "name_eng": "KT Corp"},
    "032830": {"corp_code": "00126256", "name": "삼성생명", "name_eng": "Samsung Life Insurance"},
    "009150": {"corp_code": "00126371", "name": "삼성전기", "name_eng": "Samsung Electro-Mechanics"},
    "018260": {"corp_code": "00126186", "name": "삼성에스디에스", "name_eng": "Samsung SDS"},
    "086790": {"corp_code": "00547583", "name": "하나금융지주", "name_eng": "Hana Financial Group"},
    "316140": {"corp_code": "01350869", "name": "우리금융지주", "name_eng": "Woori Financial Group"},
    "047050": {"corp_code": "00124504", "name": "포스코인터내셔널", "name_eng": "POSCO International"},
    "259960": {"corp_code": "00760971", "name": "크래프톤", "name_eng": "KRAFTON"},
}

# In-memory cache for the full DART mapping (loaded from file or API)
_ticker_cache: Optional[dict] = None


def _get_cache_path() -> str:
    """Get the local cache file path for DART ticker data."""
    config = get_config()
    cache_dir = config.get("data_cache_dir", "/tmp")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "dart_corp_codes.json")


def _load_cache() -> dict:
    """Load ticker mapping from local cache file."""
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache

    cache_path = _get_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                _ticker_cache = json.load(f)
                logger.info("Loaded %d ticker mappings from cache", len(_ticker_cache))
                return _ticker_cache
        except (json.JSONDecodeError, OSError):
            pass

    # Fall back to built-in mapping
    _ticker_cache = BUILTIN_TICKERS.copy()
    return _ticker_cache


def _save_cache(data: dict) -> None:
    """Save ticker mapping to local cache file."""
    global _ticker_cache
    _ticker_cache = data
    cache_path = _get_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Saved %d ticker mappings to cache", len(data))
    except OSError as e:
        logger.warning("Failed to save ticker cache: %s", e)


def update_from_dart() -> int:
    """Download and parse DART corpCode.xml to update the full ticker mapping.

    Requires DART_API_KEY environment variable.
    Returns the number of stock-listed companies found.
    """
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        raise RuntimeError("DART_API_KEY required to download corpCode.xml")

    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download corpCode.xml: {e}")

    # Response is a zip file containing CORPCODE.xml
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            xml_name = zf.namelist()[0]  # Usually "CORPCODE.xml"
            xml_data = zf.read(xml_name)
    except (zipfile.BadZipFile, IndexError) as e:
        raise RuntimeError(f"Failed to extract corpCode.xml from zip: {e}")

    # Parse XML
    root = ElementTree.fromstring(xml_data)
    mapping = {}

    for item in root.findall(".//list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()

        # Only include companies with a stock code (listed companies)
        if stock_code and corp_code and corp_name:
            mapping[stock_code] = {
                "corp_code": corp_code,
                "name": corp_name,
                "name_eng": "",
            }

    # Merge with built-in data (keep English names from built-in)
    for code, info in BUILTIN_TICKERS.items():
        if code in mapping:
            mapping[code]["name_eng"] = info.get("name_eng", "")

    _save_cache(mapping)
    return len(mapping)


def resolve_ticker(query: str) -> Optional[dict]:
    """Resolve a query to a Korean stock ticker.

    Accepts:
    - Stock code: "005930"
    - Company name (Korean): "삼성전자"
    - Company name (partial): "삼성"
    - DART corp_code: "00126380"

    Returns:
        {"stock_code": "005930", "corp_code": "00126380", "name": "삼성전자"}
        or None if not found.
    """
    data = _load_cache()
    query = query.strip()

    # 1. Exact stock code match
    if query in data:
        info = data[query]
        return {
            "stock_code": query,
            "corp_code": info["corp_code"],
            "name": info["name"],
            "name_eng": info.get("name_eng", ""),
        }

    # 2. Exact corp_code match
    for stock_code, info in data.items():
        if info["corp_code"] == query:
            return {
                "stock_code": stock_code,
                "corp_code": info["corp_code"],
                "name": info["name"],
                "name_eng": info.get("name_eng", ""),
            }

    # 3. Exact company name match
    for stock_code, info in data.items():
        if info["name"] == query or info.get("name_eng", "").upper() == query.upper():
            return {
                "stock_code": stock_code,
                "corp_code": info["corp_code"],
                "name": info["name"],
                "name_eng": info.get("name_eng", ""),
            }

    # 4. Partial name match (prefix)
    matches = []
    for stock_code, info in data.items():
        if query in info["name"] or query.upper() in info.get("name_eng", "").upper():
            matches.append({
                "stock_code": stock_code,
                "corp_code": info["corp_code"],
                "name": info["name"],
                "name_eng": info.get("name_eng", ""),
            })

    if len(matches) == 1:
        return matches[0]
    if matches:
        # Return first match but log ambiguity
        logger.info("Ambiguous ticker query '%s': %d matches, returning first", query, len(matches))
        return matches[0]

    return None


def get_instrument_profile(query: str) -> dict:
    """Build a canonical instrument profile for routing Korean-market data calls.

    This keeps a single resolved view of the instrument while allowing each
    downstream vendor to use the identifier format it expects.
    """
    raw_input = "" if query is None else str(query)
    stripped = raw_input.strip()
    normalized = stripped.upper()
    has_exchange_suffix = "." in stripped

    lookup_query = stripped
    if has_exchange_suffix:
        lookup_query = stripped.rsplit(".", 1)[0]

    resolved = resolve_ticker(lookup_query) if lookup_query else None
    stock_code = resolved["stock_code"] if resolved else None
    company_name = resolved["name"] if resolved else stripped
    name_eng = resolved.get("name_eng", "") if resolved else ""

    if stock_code:
        yfinance_symbol = normalized if has_exchange_suffix else stock_code
        display_name = f"{company_name} ({stock_code})"
        structured_symbol = stock_code
        news_query = company_name
        corp_code = resolved["corp_code"]
    else:
        yfinance_symbol = normalized
        display_name = stripped
        structured_symbol = normalized
        news_query = stripped
        corp_code = None

    return {
        "raw_input": raw_input,
        "query": stripped,
        "resolved": bool(resolved),
        "is_korean_equity": bool(stock_code),
        "has_exchange_suffix": has_exchange_suffix,
        "stock_code": stock_code,
        "corp_code": corp_code,
        "name": company_name,
        "name_eng": name_eng,
        "display_name": display_name,
        "structured_symbol": structured_symbol,
        "news_query": news_query,
        "yfinance_symbol": yfinance_symbol,
    }


def get_corp_code(stock_code: str) -> Optional[str]:
    """Get DART corp_code for a stock code. Convenience function."""
    result = get_instrument_profile(stock_code)
    return result["corp_code"]


def get_stock_code(query: str) -> Optional[str]:
    """Get stock code for any query (name, code, etc). Convenience function."""
    result = get_instrument_profile(query)
    return result["stock_code"]


def get_yfinance_candidates(
    query: str,
    *,
    prefer_qualified: bool = False,
) -> list[str]:
    """Return ordered yfinance symbol candidates for the given instrument query."""
    profile = get_instrument_profile(query)

    if profile["has_exchange_suffix"]:
        return [profile["yfinance_symbol"]]

    stock_code = profile["stock_code"]
    if stock_code:
        if prefer_qualified:
            candidates = [f"{stock_code}.KS", f"{stock_code}.KQ", stock_code]
        else:
            candidates = [stock_code, f"{stock_code}.KS", f"{stock_code}.KQ"]
        deduped = []
        for candidate in candidates:
            if candidate not in deduped:
                deduped.append(candidate)
        return deduped

    return [profile["yfinance_symbol"]]
