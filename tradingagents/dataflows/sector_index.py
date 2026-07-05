"""KIS sector index code mapping for stock-vs-sector relative performance.

Source: KIS official master file `idxcode.mst`
(https://new.real.download.dws.co.kr/common/master/idxcode.mst.zip), parsed
on 2026-04-10. The codes below are the 4-digit `FID_INPUT_ISCD` values that
the `inquire-daily-indexchartprice` endpoint accepts when
`FID_COND_MRKT_DIV_CODE="U"`.

Two index families are exposed for analyst use:

1. **K200 sectors (div 2)** — broad KOSPI 200 sub-groups. KIS only publishes
   ~11 of these, and they are coarse: 금융 includes banks/securities/
   insurance, 정보기술 includes 반도체 + general IT, etc.

2. **KRX industry indices (div 4)** — finer granularity. KRX 은행 / KRX
   반도체 / KRX 자동차 etc. give the actual peer-comparison context that
   matters for ROE-vs-industry questions. We prefer these whenever possible.

The hardcoded `STOCK_TO_SECTOR` mapping covers the major KOSPI/KOSDAQ
constituents. A stock that is not in the mapping returns `None` from
`get_sector_for_stock()` and the MarketPacket simply omits the
`sector_context` field — there is no fallback to a "general market" baseline,
per the design decision to avoid misleading anchoring.
"""

from __future__ import annotations

from typing import Optional


# ----------------------------------------------------------------------
# KIS sector index 4-digit codes (verified against idxcode.mst, 2026-04-10)
# ----------------------------------------------------------------------

KIS_SECTOR_INDEX_CODES: dict[str, str] = {
    # --- Market headline (div 0/1/2) ---
    "KOSPI 종합": "0001",
    "KOSDAQ 종합": "1001",
    "KOSPI 200": "2001",
    # --- KOSPI 200 sector family (div 2) ---
    "K200 건설": "2009",
    "K200 중공업": "2010",
    "K200 철강소재": "2011",
    "K200 에너지화학": "2012",
    "K200 정보기술": "2013",
    "K200 금융": "2014",
    "K200 생활소비재": "2015",
    "K200 경기소비재": "2016",
    "K200 산업재": "2017",
    "K200 헬스케어": "2018",
    "K200 커뮤니케이션서비스": "2039",
    # --- KRX industry indices (div 4) — preferred for granularity ---
    "KRX 자동차": "4002",
    "KRX 반도체": "4003",
    "KRX 헬스케어": "4004",
    "KRX 은행": "4005",
    "KRX 에너지화학": "4007",
    "KRX 철강": "4008",
    "KRX 방송통신": "4010",
    "KRX 건설": "4011",
    "KRX 증권": "4013",
    "KRX 보험": "4015",
    "KRX 운송": "4016",
    "KRX 경기소비재": "4061",
    "KRX 필수소비재": "4062",
    "KRX 미디어&엔터테인먼트": "4063",
}


# ----------------------------------------------------------------------
# Stock → sector mapping for KOSPI/KOSDAQ majors
# ----------------------------------------------------------------------
#
# The value is the sector key from KIS_SECTOR_INDEX_CODES. We prefer
# KRX industry indices over K200 sector indices when both apply, because
# the KRX series is more granular.
#
# This mapping covers the top ~50 KOSPI stocks plus the most-traded
# KOSDAQ names. Adding new entries is a one-line change. Tickers that
# are NOT in this mapping fall through and the MarketPacket simply does
# not include a sector_context block.

STOCK_TO_SECTOR: dict[str, str] = {
    # ── 반도체 ──
    "005930": "KRX 반도체",  # 삼성전자
    "000660": "KRX 반도체",  # SK하이닉스
    "042700": "KRX 반도체",  # 한미반도체
    "240810": "KRX 반도체",  # 원익IPS
    # ── 자동차 ──
    "005380": "KRX 자동차",  # 현대차
    "000270": "KRX 자동차",  # 기아
    "012330": "KRX 자동차",  # 현대모비스
    "204320": "KRX 자동차",  # HL만도
    # ── 은행 / 금융지주 ──
    "055550": "KRX 은행",  # 신한지주
    "105560": "KRX 은행",  # KB금융
    "086790": "KRX 은행",  # 하나금융지주
    "316140": "KRX 은행",  # 우리금융지주
    "138930": "KRX 은행",  # BNK금융지주
    "175330": "KRX 은행",  # JB금융지주
    # ── 보험 ──
    "032830": "KRX 보험",  # 삼성생명
    "000810": "KRX 보험",  # 삼성화재
    "088350": "KRX 보험",  # 한화생명
    # ── 증권 ──
    "005940": "KRX 증권",  # NH투자증권
    "006800": "KRX 증권",  # 미래에셋증권
    "016360": "KRX 증권",  # 삼성증권
    "071050": "KRX 증권",  # 한국금융지주
    # ── 에너지/화학 ──
    "051910": "KRX 에너지화학",  # LG화학
    "096770": "KRX 에너지화학",  # SK이노베이션
    "010950": "KRX 에너지화학",  # S-Oil
    "011170": "KRX 에너지화학",  # 롯데케미칼
    "009830": "KRX 에너지화학",  # 한화솔루션
    # ── 철강 ──
    "005490": "KRX 철강",  # POSCO홀딩스
    "004020": "KRX 철강",  # 현대제철
    # ── 건설 ──
    "000720": "KRX 건설",  # 현대건설
    "047040": "KRX 건설",  # 대우건설
    "375500": "KRX 건설",  # DL이앤씨
    # ── 운송 ──
    "180640": "KRX 운송",  # 한진칼
    "003490": "KRX 운송",  # 대한항공
    "011200": "KRX 운송",  # HMM
    "028670": "KRX 운송",  # 팬오션
    # ── 통신/방송 ──
    "017670": "KRX 방송통신",  # SK텔레콤
    "030200": "KRX 방송통신",  # KT
    "032640": "KRX 방송통신",  # LG유플러스
    # ── 미디어/엔터 ──
    "035900": "KRX 미디어&엔터테인먼트",  # JYP Ent.
    "041510": "KRX 미디어&엔터테인먼트",  # SM
    "352820": "KRX 미디어&엔터테인먼트",  # 하이브
    "122870": "KRX 미디어&엔터테인먼트",  # YG엔터
    # ── 헬스케어/바이오 ──
    "207940": "KRX 헬스케어",  # 삼성바이오로직스
    "068270": "KRX 헬스케어",  # 셀트리온
    "326030": "KRX 헬스케어",  # SK바이오팜
    "196170": "KRX 헬스케어",  # 알테오젠
    "091990": "KRX 헬스케어",  # 셀트리온헬스케어
    # ── 인터넷/IT (K200 정보기술 — KRX는 인터넷 별도 없음) ──
    "035420": "K200 정보기술",  # NAVER
    "035720": "K200 정보기술",  # 카카오
    "018260": "K200 정보기술",  # 삼성에스디에스
    "036570": "K200 정보기술",  # 엔씨소프트
    "251270": "K200 정보기술",  # 넷마블
    "259960": "K200 정보기술",  # 크래프톤
    # ── 2차전지/배터리 (K200 정보기술 또는 KRX 에너지화학에 가깝지만 별도 sector 없음) ──
    "373220": "K200 정보기술",  # LG에너지솔루션
    "006400": "K200 정보기술",  # 삼성SDI
    "003670": "KRX 에너지화학",  # 포스코퓨처엠
    # ── 산업재 (조선/기계) ──
    "009540": "K200 산업재",  # HD한국조선해양
    "010140": "K200 산업재",  # 삼성중공업
    "267250": "K200 산업재",  # HD현대중공업
    "042660": "K200 산업재",  # 한화오션
    # ── 경기소비재 (유통/생활) ──
    "023530": "KRX 경기소비재",  # 롯데쇼핑
    "069960": "KRX 경기소비재",  # 현대백화점
    "139480": "KRX 필수소비재",  # 이마트
    "097950": "KRX 필수소비재",  # CJ제일제당
    "271560": "KRX 필수소비재",  # 오리온
    "004990": "KRX 필수소비재",  # 롯데지주
    # ── 지주사 (주력 사업 sector로 분류) ──
    "003550": "K200 정보기술",  # LG (LG전자/LG화학 지주)
    "034730": "K200 정보기술",  # SK (SK하이닉스/SK이노 지주)
    "066570": "K200 정보기술",  # LG전자
    "009150": "K200 정보기술",  # 삼성전기
    "028260": "K200 산업재",  # 삼성물산
    "047050": "KRX 에너지화학",  # 포스코인터내셔널
}


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def get_sector_for_stock(stock_code: str) -> Optional[str]:
    """Return the KIS sector index name for the given stock, or None.

    Returns None for any stock not in the curated mapping. The caller is
    expected to omit the `sector_context` block in that case rather than
    fall back to a misleading "general market" baseline.
    """
    if not stock_code:
        return None
    return STOCK_TO_SECTOR.get(stock_code.strip())


def get_sector_index_code(sector_name: str) -> Optional[str]:
    """Resolve a sector name to its 4-digit KIS index code, or None."""
    if not sector_name:
        return None
    return KIS_SECTOR_INDEX_CODES.get(sector_name.strip())


def get_sector_index_code_for_stock(stock_code: str) -> Optional[tuple[str, str]]:
    """Return `(sector_name, sector_code)` for a stock, or None.

    Convenience helper that combines the two lookups above. Returns None
    if the stock is unmapped or the sector lookup fails.
    """
    sector_name = get_sector_for_stock(stock_code)
    if not sector_name:
        return None
    code = get_sector_index_code(sector_name)
    if not code:
        return None
    return (sector_name, code)


def get_peer_stocks_in_sector(
    sector_name: str,
    *,
    exclude: Optional[str] = None,
) -> list[str]:
    """Return all stock codes in the given sector.

    Used by the FundamentalsPacket peer_context builder to assemble a peer
    list for `fnlttMultiAcnt` calls. Pass `exclude=stock_code` to drop the
    target itself from the peer set so the comparison is target-vs-others.
    """
    if not sector_name:
        return []
    return [
        code
        for code, name in STOCK_TO_SECTOR.items()
        if name == sector_name and code != exclude
    ]
