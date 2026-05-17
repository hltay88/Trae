"""
Bursa Malaysia breakout analyzer core utilities.

This module is used by:
  - Streamlit app (bursa_web_app.py)
  - Desktop/Tkinter apps

It provides:
  - data fetch (yfinance)
  - breakout models (v1/v2/v3)
  - universe helpers (KLCI / FBM indices / custom file)
  - RSS news + simple keyword-based trend inference
"""

from __future__ import annotations

import csv
import datetime as _dt
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator


# ----------------------------
# yfinance caching (safe default)
# ----------------------------
_DEFAULT_CACHE_DIR = Path(os.getcwd()) / ".yfinance_cache"
try:
    # Streamlit deployments or locked cwd often can't write; fall back to /tmp when needed.
    if os.environ.get("STREAMLIT_SERVER_PORT") or not os.access(os.getcwd(), os.W_OK):
        _DEFAULT_CACHE_DIR = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp") / ".yfinance_cache"
except Exception:
    _DEFAULT_CACHE_DIR = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp") / ".yfinance_cache"

try:
    _DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

os.environ["YFINANCE_CACHE_DIR"] = str(_DEFAULT_CACHE_DIR)
try:
    yf.set_tz_cache_location(str(_DEFAULT_CACHE_DIR))
except Exception:
    pass


# ----------------------------
# Basic curated insights (used for labels / sector focus)
# ----------------------------
# NOTE: This is intentionally a small curated set; you can extend it freely.
MARKET_INSIGHTS: dict[str, dict] = {
    "1155.KL": {"code": "1155", "name": "MAYBANK", "sector": "Banking", "analysis": "Strong defensive play with attractive dividends.", "catalyst": "High interest rate environment."},
    "1295.KL": {"code": "1295", "name": "PBBANK", "sector": "Banking", "analysis": "Strong asset quality and consistent dividends.", "catalyst": "Economic recovery proxy."},
    "1023.KL": {"code": "1023", "name": "CIMB", "sector": "Banking", "analysis": "Leading ASEAN focused bank. Strong earnings growth.", "catalyst": "Regional growth momentum."},
    "5347.KL": {"code": "5347", "name": "TNB", "sector": "Utilities", "analysis": "Top pick for FY26. Grid investments and renewable energy.", "catalyst": "National Energy Transition Roadmap (NETR)."},
    "5183.KL": {"code": "5183", "name": "PCHEM", "sector": "Chemicals", "analysis": "Proxy for global economic recovery and oil prices.", "catalyst": "Product price stabilization."},
    "5225.KL": {"code": "5225", "name": "IHH", "sector": "Healthcare", "analysis": "Global healthcare leader with strong expansion plans.", "catalyst": "Medical tourism and aging population."},
    "6947.KL": {"code": "6947", "name": "DIGI", "sector": "Telecommunications", "analysis": "Post-merger synergies and 5G leadership.", "catalyst": "Digital economy growth."},
    "6888.KL": {"code": "6888", "name": "AXIATA", "sector": "Telecommunications", "analysis": "Regional footprint and digital assets expansion.", "catalyst": "TowerCo monetization."},
    "6012.KL": {"code": "6012", "name": "MAXIS", "sector": "Telecommunications", "analysis": "Strong mobile market share and 5G rollout.", "catalyst": "Enterprise digital transformation."},
    "5819.KL": {"code": "5819", "name": "HLBANK", "sector": "Banking", "analysis": "Excellent asset quality and cost management.", "catalyst": "Mortgage and SME loan growth."},
    "6033.KL": {"code": "6033", "name": "PETGAS", "sector": "Utilities", "analysis": "Defensive play with high yields.", "catalyst": "Regulated asset base growth."},
    "3816.KL": {"code": "3816", "name": "MISC", "sector": "Transportation", "analysis": "Long-term charter contracts provide stability.", "catalyst": "Global energy demand."},
    "1066.KL": {"code": "1066", "name": "RHBBANK", "sector": "Banking", "analysis": "Attractive dividend yields and digital banking.", "catalyst": "Transformation program success."},
    "4707.KL": {"code": "4707", "name": "NESTLE", "sector": "Consumer", "analysis": "Resilient demand for essential products.", "catalyst": "Input cost normalization."},
    "1961.KL": {"code": "1961", "name": "IOICORP", "sector": "Plantation", "analysis": "Efficient producer with strong integrated operations.", "catalyst": "CPO price support."},
    "2445.KL": {"code": "2445", "name": "KLK", "sector": "Plantation", "analysis": "Leading plantation group with strong downstream.", "catalyst": "Upstream production growth."},
    "3182.KL": {"code": "3182", "name": "GENTING", "sector": "Tourism", "analysis": "Proxy for global travel recovery.", "catalyst": "Resorts World Las Vegas performance."},
    "4715.KL": {"code": "4715", "name": "GENM", "sector": "Tourism", "analysis": "Direct beneficiary of Visit Malaysia Year 2026.", "catalyst": "Increased tourist arrivals."},
    "7277.KL": {"code": "7277", "name": "DIALOG", "sector": "Oil & Gas", "analysis": "Strong recurring income from storage assets.", "catalyst": "Pengerang Phase 3 development."},
    "4197.KL": {"code": "4197", "name": "SIME", "sector": "Conglomerate", "analysis": "Strong automotive and heavy equipment division.", "catalyst": "EV market expansion."},
    "5285.KL": {"code": "5285", "name": "SIMEPLT", "sector": "Plantation", "analysis": "World's largest producer of certified sustainable CPO.", "catalyst": "ESG leadership and yield recovery."},
    "5681.KL": {"code": "5681", "name": "PETDAG", "sector": "Retail", "analysis": "Dominant market share in retail fuel.", "catalyst": "Domestic travel volume."},
    "0166.KL": {"code": "0166", "name": "INARI", "sector": "Technology", "analysis": "Proxy for global 5G and AI smartphone cycle.", "catalyst": "New product launches by key customers."},
    "5296.KL": {"code": "5296", "name": "MRDIY", "sector": "Consumer", "analysis": "Aggressive store expansion and resilient demand.", "catalyst": "Inflationary environment beneficiary."},
    "5246.KL": {"code": "5246", "name": "WESTPORTS", "sector": "Transportation", "analysis": "Proxy for global trade recovery.", "catalyst": "Port expansion plans."},
    "4677.KL": {"code": "4677", "name": "YTL", "sector": "Conglomerate", "analysis": "Strong performance from utility and data center divisions.", "catalyst": "AI data center development."},
    "6742.KL": {"code": "6742", "name": "YTLPOWR", "sector": "Utilities", "analysis": "Power & utilities leader with data center-related growth exposure.", "catalyst": "Electricity demand growth and digital infrastructure theme."},
    "5099.KL": {"code": "5099", "name": "CAPITALA", "sector": "Aviation", "analysis": "Proxy for regional travel surge.", "catalyst": "AirAsia recovery and digital assets."},
    "FKLI=F": {"code": "FKLI", "name": "KLCI FUTURES", "sector": "Futures", "analysis": "Proxy for the underlying FBM KLCI index.", "catalyst": "Market sentiment and index component performance."},
    "FCPO=F": {"code": "FCPO", "name": "CPO FUTURES", "sector": "Futures", "analysis": "Global benchmark for Crude Palm Oil.", "catalyst": "Indonesian export policies and weather patterns."},
    "FM70=F": {"code": "FM70", "name": "MID 70 FUTURES", "sector": "Futures", "analysis": "Proxy for the FBM Mid 70 Index.", "catalyst": "Domestic liquidity and mid-cap earnings momentum."},
}


# ----------------------------
# Universe files / caches
# ----------------------------
APP_DIR = Path(__file__).resolve().parent
BURSA_UNIVERSE_FILE = str(APP_DIR / "bursa_universe.csv")
BURSA_UNIVERSE_AUTO_FILE = str(APP_DIR / "bursa_universe_auto.csv")
INDEX_COMPONENTS_CACHE_DIR = APP_DIR / "index_components_cache"
KLCI_COMPONENTS_FILE = APP_DIR / "klci_components_auto.txt"

# A small "curated" scanning universe (fast).
STOCK_DISCOVERY_UNIVERSE = [t for t in MARKET_INSIGHTS.keys() if t.endswith(".KL")]
KLCI_COMPONENTS = set()  # filled lazily by get_stock_universe()

# Auto-universe name map (code -> company name). Loaded on demand.
_AUTO_NAME_MAP: dict[str, str] | None = None
_SEARCH_CACHE: dict[str, tuple[float, str | None]] = {}
_SEARCH_CACHE_SECONDS = 12 * 3600


def _short_company_name(name: str) -> str:
    """
    Makes long Bursa company names more readable in tables.
    Example: "ABC BERHAD" -> "ABC"
    """
    try:
        s = str(name or "").strip()
        if not s:
            return s
        s = re.sub(r"\s+", " ", s).strip()
        # common suffixes
        s = re.sub(r"\bBERHAD\b", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\bBHD\b", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\bSDN\.?\s*BHD\b", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\bHOLDINGS?\b", "HLDG", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"\s+", " ", s).strip()
        return s
    except Exception:
        return str(name or "").strip()


def _load_auto_universe_name_map() -> dict[str, str]:
    global _AUTO_NAME_MAP
    if isinstance(_AUTO_NAME_MAP, dict) and _AUTO_NAME_MAP:
        return _AUTO_NAME_MAP

    def _merge_code_name_csv(path: Path, code_key: str = "code", name_key: str = "name") -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            if not path.exists():
                return out
            with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    return out
                fields = {str(x).strip().lower() for x in (reader.fieldnames or [])}
                if code_key.lower() not in fields or name_key.lower() not in fields:
                    return out
                for row in reader:
                    if not row:
                        continue
                    code = str(row.get(code_key) or row.get(code_key.title()) or "").strip()
                    name = str(row.get(name_key) or row.get(name_key.title()) or "").strip()
                    if not (code.isdigit() and len(code) == 4):
                        continue
                    if not name:
                        continue
                    out[f"{code}.KL".upper()] = _short_company_name(name)
            return out
        except Exception:
            return out

    m: dict[str, str] = {}

    # Prefer richer name sources when available (index cache usually has code,name)
    try:
        for p in [
            INDEX_COMPONENTS_CACHE_DIR / "fbm100.txt",
            INDEX_COMPONENTS_CACHE_DIR / "fbm70.txt",
            INDEX_COMPONENTS_CACHE_DIR / "smallcap.txt",
        ]:
            m.update(_merge_code_name_csv(p, code_key="code", name_key="name"))
    except Exception:
        pass

    # If user has an auto-universe file with names, merge it too.
    try:
        m.update(_merge_code_name_csv(Path(BURSA_UNIVERSE_AUTO_FILE), code_key="code", name_key="name"))
    except Exception:
        pass

    _AUTO_NAME_MAP = m
    return m


def _auto_universe_name(ticker: str) -> str | None:
    """
    Best-effort: resolve a nicer company name from bursa_universe_auto.csv.
    Returns None if not found.
    """
    try:
        t = str(ticker or "").upper().strip()
        if not t:
            return None
        code = t.split(".")[0].replace("^", "").strip()
        mp = _load_auto_universe_name_map()
        if t in mp:
            return mp.get(t)
        if code.isdigit() and len(code) == 4:
            return mp.get(f"{code}.KL")
        return None
    except Exception:
        return None


def _is_today_kl(ts) -> bool:
    try:
        t = pd.Timestamp(ts)
        if t.tz is None:
            t = t.tz_localize("Asia/Kuala_Lumpur")
        else:
            t = t.tz_convert("Asia/Kuala_Lumpur")
        return t.normalize() == pd.Timestamp.now(tz="Asia/Kuala_Lumpur").normalize()
    except Exception:
        return False


def _load_list_file(path: Path) -> list[str]:
    try:
        if not path.exists():
            return []
        txt = path.read_text(encoding="utf-8", errors="ignore")
        out = []
        for line in txt.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                continue
            s = s.replace(",", " ").replace("\t", " ")
            s = s.split()[0]
            s = s.upper()
            if s.isdigit() and len(s) == 4:
                s = f"{s}.KL"
            if s.endswith(".KL") or s.endswith("=F") or s.startswith("^"):
                out.append(s)
        # de-dupe, preserve order
        seen = set()
        uniq = []
        for x in out:
            if x in seen:
                continue
            seen.add(x)
            uniq.append(x)
        return uniq
    except Exception:
        return []


def _load_universe_from_csv(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[str] = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                s = str(row[0]).strip().upper()
                if not s or s.startswith("#"):
                    continue
                if s.isdigit() and len(s) == 4:
                    s = f"{s}.KL"
                if s.endswith(".KL"):
                    out.append(s)
    except Exception:
        return []
    seen = set()
    uniq = []
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    return uniq


def _find_company_list_xlsx_files() -> list[Path]:
    try:
        patterns = [
            "List_of_Companies*.xlsx",
            "list_of_companies*.xlsx",
            "companies*.xlsx",
        ]
        out: list[Path] = []
        for pat in patterns:
            out.extend(sorted(APP_DIR.glob(pat)))
        seen = set()
        uniq: list[Path] = []
        for p in out:
            rp = str(p.resolve())
            if rp in seen:
                continue
            seen.add(rp)
            uniq.append(p)
        return uniq
    except Exception:
        return []


def _load_universe_from_xlsx(path: Path) -> list[str]:
    try:
        if not path.exists():
            return []
        with zipfile.ZipFile(path, "r") as z:
            shared: list[str] = []
            try:
                ss = z.read("xl/sharedStrings.xml")
                root = ET.fromstring(ss)
                ns = ""
                if root.tag.startswith("{"):
                    ns = root.tag.split("}")[0] + "}"
                for si in root.findall(f".//{ns}si"):
                    texts = []
                    for t in si.findall(f".//{ns}t"):
                        if t.text:
                            texts.append(t.text)
                    shared.append("".join(texts))
            except Exception:
                shared = []

            sheet_xml = None
            for name in ["xl/worksheets/sheet1.xml", "xl/worksheets/sheet0.xml"]:
                try:
                    sheet_xml = z.read(name)
                    break
                except Exception:
                    sheet_xml = None
            if sheet_xml is None:
                try:
                    names = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
                    names.sort()
                    if names:
                        sheet_xml = z.read(names[0])
                except Exception:
                    sheet_xml = None
            if sheet_xml is None:
                return []

            root = ET.fromstring(sheet_xml)
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"

            out: list[str] = []
            for c in root.findall(f".//{ns}c"):
                r = c.attrib.get("r") or ""
                if not r.startswith("D"):
                    continue
                v = c.find(f"{ns}v")
                if v is None or v.text is None:
                    continue
                raw = v.text.strip()
                if not raw:
                    continue
                if (c.attrib.get("t") or "").strip().lower() == "s":
                    try:
                        idx = int(raw)
                        raw = shared[idx] if 0 <= idx < len(shared) else ""
                    except Exception:
                        raw = ""
                raw = str(raw).strip()
                if not raw:
                    continue
                code = raw.replace(".KL", "").strip()
                if code.isdigit() and 1 <= len(code) <= 4:
                    out.append(f"{code.zfill(4)}.KL")

            seen = set()
            uniq = []
            for x in out:
                if x in seen:
                    continue
                seen.add(x)
                uniq.append(x)
            return uniq
    except Exception:
        return []


def _write_universe_csv(path: str, tickers: list[str]) -> bool:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="\n") as f:
            f.write("ticker\n")
            for t in tickers:
                s = str(t or "").strip().upper()
                if not s:
                    continue
                if s.isdigit() and len(s) == 4:
                    s = f"{s}.KL"
                if s.endswith(".KL"):
                    f.write(f"{s}\n")
        return True
    except Exception:
        return False


def get_stock_universe(mode: str = "curated") -> tuple[list[str], str]:
    """
    Returns (tickers, source_label).
    Supported modes match the Streamlit UI.
    """
    m = str(mode or "curated").strip().lower()

    # cached constituent lists
    if m in {"klci", "kcli"}:
        u = _load_list_file(KLCI_COMPONENTS_FILE)
        if u:
            global KLCI_COMPONENTS
            KLCI_COMPONENTS = set(u)
            return u, "klci-file"
        return list(STOCK_DISCOVERY_UNIVERSE), "klci-fallback"

    if m in {"fbm70", "mid70"}:
        u = _load_list_file(INDEX_COMPONENTS_CACHE_DIR / "fbm70.txt")
        return (u, "fbm70-cache") if u else (list(STOCK_DISCOVERY_UNIVERSE), "fbm70-fallback")

    if m in {"fbm100", "top100"}:
        u = _load_list_file(INDEX_COMPONENTS_CACHE_DIR / "fbm100.txt")
        return (u, "fbm100-cache") if u else (list(STOCK_DISCOVERY_UNIVERSE), "fbm100-fallback")

    if m in {"smallcap", "small", "sc"}:
        u = _load_list_file(INDEX_COMPONENTS_CACHE_DIR / "smallcap.txt")
        return (u, "smallcap-cache") if u else (list(STOCK_DISCOVERY_UNIVERSE), "smallcap-fallback")

    if m in {"file", "full", "all"}:
        u = _load_universe_from_csv(BURSA_UNIVERSE_FILE)
        try:
            xls = []
            for p in _find_company_list_xlsx_files():
                xls.extend(_load_universe_from_xlsx(p))
            if xls:
                seen = set(u)
                merged = list(u)
                for t in xls:
                    if t in seen:
                        continue
                    seen.add(t)
                    merged.append(t)
                if len(merged) != len(u):
                    _write_universe_csv(BURSA_UNIVERSE_FILE, merged)
                u = merged
        except Exception:
            pass
        return (u, "file") if u else (list(STOCK_DISCOVERY_UNIVERSE), "file-fallback")

    if m in {"auto", "malaysia", "my"}:
        u = _load_universe_from_csv(BURSA_UNIVERSE_AUTO_FILE)
        if u:
            return u, "auto-file"
        u = _load_universe_from_csv(BURSA_UNIVERSE_FILE)
        return (u, "auto-fallback-file") if u else (list(STOCK_DISCOVERY_UNIVERSE), "auto-fallback-curated")

    # simple sector filters from curated insights (fast)
    if m.startswith("sector-"):
        sector_key = m.replace("sector-", "").strip().lower()
        sector_map = {
            "tech": {"technology"},
            "utilities": {"utilities"},
            "infra": {"infrastructure"},
            "property": {"property"},
            "consumer": {"consumer"},
            "banks": {"banking", "financial"},
            "healthcare": {"healthcare"},
            "energy": {"energy", "oil & gas"},
            "plantation": {"plantation"},
            "telco": {"telecommunications", "telco"},
            "industrial": {"industrials"},
        }
        allow = sector_map.get(sector_key, set())
        u = []
        for t, v in MARKET_INSIGHTS.items():
            if not str(t).endswith(".KL"):
                continue
            sec = str(v.get("sector") or "").strip().lower()
            if allow and sec in allow:
                u.append(str(t).upper())
        return (u, f"{m}-curated") if u else (list(STOCK_DISCOVERY_UNIVERSE), f"{m}-fallback")

    # "focus" is a slightly larger curated list; currently same as curated.
    if m in {"focus", "curated"}:
        return list(STOCK_DISCOVERY_UNIVERSE), "curated"

    return list(STOCK_DISCOVERY_UNIVERSE), "curated"


# ----------------------------
# Insight resolution
# ----------------------------
def _resolve_insight(ticker: str, resolved_name: str | None) -> tuple[str, str, str, str]:
    t = str(ticker).upper().strip()
    code = t.split(".")[0]
    analysis = "Technical breakout analysis based on live data."
    catalyst = "Market momentum / Trend following."

    insight = MARKET_INSIGHTS.get(t)
    if not insight:
        for _, v in MARKET_INSIGHTS.items():
            if str(v.get("code") or "").strip() == code:
                insight = v
                break

    if insight:
        name = str(insight.get("name") or code)
        analysis = str(insight.get("analysis") or analysis)
        catalyst = str(insight.get("catalyst") or catalyst)
        code = str(insight.get("code") or code)
    else:
        name = (resolved_name or code) if resolved_name else code
    # Fallback for when yfinance doesn't provide a name:
    try:
        if (not resolved_name) or (str(resolved_name).strip().upper() in {t, code, f"{code}.KL"}):
            nm = _auto_universe_name(t) or _auto_universe_name(f"{code}.KL")
            if nm:
                name = nm
    except Exception:
        pass
    name = str(name).replace(".KL", "").strip()
    return code, name, analysis, catalyst


def _resolve_insight_v3(ticker: str, resolved_name: str | None) -> tuple[str, str, str, str, str]:
    t = str(ticker).upper().strip()
    code = t.split(".")[0]
    name = resolved_name or code
    analysis = "Technical breakout analysis based on live data."
    catalyst = "Market momentum / Trend following."
    sector = "Unknown"

    insight = MARKET_INSIGHTS.get(t)
    if not insight:
        for _, v in MARKET_INSIGHTS.items():
            if str(v.get("code") or "").strip() == code:
                insight = v
                break

    if insight:
        name = str(insight.get("name") or name)
        analysis = str(insight.get("analysis") or analysis)
        catalyst = str(insight.get("catalyst") or catalyst)
        sector = str(insight.get("sector") or sector).strip() or sector
        code = str(insight.get("code") or code)
    else:
        # Fallback for when yfinance doesn't provide a name:
        try:
            if (not resolved_name) or (str(resolved_name).strip().upper() in {t, code, f"{code}.KL"}):
                nm = _auto_universe_name(t) or _auto_universe_name(f"{code}.KL")
                if nm:
                    name = nm
        except Exception:
            pass

    name = str(name).replace(".KL", "").strip()
    if name.strip() == code:
        name = code
    return code, name, sector, analysis, catalyst


# ----------------------------
# Extra indicators (MACD/ATR/Volume ratio)
# ----------------------------
def _calc_extra_indicators(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {"macd": None, "macd_signal": None, "macd_hist": None, "atr14": None, "atr_pct": None, "vol_ratio20": None}

    try:
        close = pd.to_numeric(df.get("Close"), errors="coerce")
        high = pd.to_numeric(df.get("High"), errors="coerce")
        low = pd.to_numeric(df.get("Low"), errors="coerce")
        vol = pd.to_numeric(df.get("Volume"), errors="coerce")
    except Exception:
        return {"macd": None, "macd_signal": None, "macd_hist": None, "atr14": None, "atr_pct": None, "vol_ratio20": None}

    out = {"macd": None, "macd_signal": None, "macd_hist": None, "atr14": None, "atr_pct": None, "vol_ratio20": None}

    try:
        if close.notna().sum() >= 30:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            sig = macd.ewm(span=9, adjust=False).mean()
            hist = macd - sig
            out["macd"] = float(macd.iloc[-1]) if pd.notna(macd.iloc[-1]) else None
            out["macd_signal"] = float(sig.iloc[-1]) if pd.notna(sig.iloc[-1]) else None
            out["macd_hist"] = float(hist.iloc[-1]) if pd.notna(hist.iloc[-1]) else None
    except Exception:
        pass

    try:
        if close.notna().sum() >= 30 and high.notna().sum() >= 30 and low.notna().sum() >= 30:
            prev_close = close.shift(1)
            tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
            atr14 = tr.rolling(window=14).mean()
            atr_pct = atr14 / close
            out["atr14"] = float(atr14.iloc[-1]) if pd.notna(atr14.iloc[-1]) else None
            out["atr_pct"] = float(atr_pct.iloc[-1]) if pd.notna(atr_pct.iloc[-1]) else None
    except Exception:
        pass

    try:
        if vol.notna().sum() >= 25:
            v_last = float(vol.iloc[-1]) if pd.notna(vol.iloc[-1]) else None
            v_avg20 = float(vol.rolling(window=20).mean().iloc[-1]) if pd.notna(vol.rolling(window=20).mean().iloc[-1]) else None
            if v_last is not None and v_avg20 and v_avg20 > 0:
                out["vol_ratio20"] = float(v_last / v_avg20)
    except Exception:
        pass

    return out


# ----------------------------
# Data fetch
# ----------------------------
def get_stock_data(ticker: str, period: str = "1y") -> tuple[pd.DataFrame | None, str | None]:
    """
    Returns (df, resolved_name).
    """
    t = str(ticker).upper().strip()
    if not t:
        return None, None

    try:
        tk = yf.Ticker(t)
        df = tk.history(period=str(period))
    except Exception:
        return None, None

    if df is None or df.empty:
        return None, None

    # Some environments return tz-aware index; keep it, but ensure clean numeric OHLCV.
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    try:
        df = df.dropna(subset=["Close"])
    except Exception:
        pass

    # Drop trailing "bad" bar if necessary.
    try:
        if len(df) >= 2:
            last_close = df["Close"].iloc[-1]
            last_open = df["Open"].iloc[-1] if "Open" in df.columns else None
            if pd.isna(last_close) or (last_open is not None and pd.isna(last_open)):
                df = df.iloc[:-1]
            elif "Volume" in df.columns and float(df["Volume"].iloc[-1] or 0) == 0.0 and float(df["Volume"].iloc[-2] or 0) > 0.0 and not _is_today_kl(df.index[-1]):
                df = df.iloc[:-1]
    except Exception:
        pass

    name = None
    try:
        info = getattr(tk, "info", None) or {}
        name = info.get("shortName") or info.get("longName") or info.get("displayName")
    except Exception:
        name = None

    return df, (str(name).strip() if name else None)


# ----------------------------
# Breakout models
# ----------------------------
def analyze_breakout(ticker, df, resolved_name=None, min_rows: int = 50):
    """
    Original (V1) breakout model. Score range: 0-5.
    """
    if df is None or len(df) < int(min_rows):
        return None

    ticker = str(ticker).upper().strip()
    current_price = float(df["Close"].iloc[-1])

    rsi = 50.0
    score = 1
    is_volume_surge = False
    breakout_level = None
    try:
        sma_20 = float(SMAIndicator(df["Close"], window=20).sma_indicator().iloc[-1])
        sma_50 = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-1])
        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
        if rsi_v == rsi_v:
            rsi = float(rsi_v)
        avg_volume_20 = float(df["Volume"].rolling(window=20).mean().iloc[-1]) if "Volume" in df.columns else 0.0
        current_volume = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else 0.0
        is_above_sma = current_price > sma_20 and current_price > sma_50
        is_volume_surge = (avg_volume_20 > 0 and current_volume > (avg_volume_20 * 1.5))
        breakout_level = float(df["Close"].iloc[-20:-1].max())
        is_price_break = current_price > breakout_level
        score = 0
        if is_above_sma:
            score += 1
        if is_volume_surge:
            score += 2
        if is_price_break:
            score += 2
    except Exception:
        pass

    code, name, analysis, catalyst = _resolve_insight(ticker, resolved_name)
    extra = _calc_extra_indicators(df)

    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "price": float(round(current_price, 3)),
        "rsi": float(round(rsi, 2)),
        "volume_surge": bool(is_volume_surge),
        "score": int(score),
        "score_max": 5,
        "analysis": analysis,
        "catalyst": catalyst,
        "breakout_level": breakout_level,
        **extra,
        "model": "v1",
    }


def analyze_breakout_v2(ticker, df, resolved_name=None, benchmark_df=None, min_rows: int = 120):
    """
    Stronger (V2) breakout model. Score range: 0-10.
    """
    if df is None or len(df) < int(min_rows):
        return None

    ticker = str(ticker).upper().strip()
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    try:
        current_close = float(df["Close"].iloc[-1])
        if not (current_close > 0.0):
            return None
    except Exception:
        return None

    rsi = 50.0
    try:
        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
        if rsi_v == rsi_v:
            rsi = float(rsi_v)
    except Exception:
        pass

    sma50 = sma200 = None
    try:
        sma50 = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-1])
        if len(df) >= 220:
            sma200 = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-1])
    except Exception:
        pass

    score = 0
    score_max = 10

    # Trend strength
    try:
        if sma50 is not None and current_close > sma50:
            sma50_prev = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-6])
            if sma50_prev == sma50_prev and sma50 > sma50_prev:
                score += 2
    except Exception:
        pass

    try:
        if sma200 is not None and current_close > sma200:
            sma200_prev = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-6])
            if sma200_prev == sma200_prev and sma200 > sma200_prev:
                score += 2
    except Exception:
        pass

    # 55d breakout
    breakout_lookback = 55
    breakout_55 = False
    breakout_level = None
    try:
        if len(df) >= breakout_lookback + 5:
            breakout_level = float(df["Close"].iloc[-breakout_lookback:-1].max())
            if current_close > breakout_level:
                breakout_55 = True
                score += 2
    except Exception:
        pass

    # Close strength
    try:
        o = float(df["Open"].iloc[-1])
        h = float(df["High"].iloc[-1])
        l = float(df["Low"].iloc[-1])
        if h > l:
            close_pos = (current_close - l) / (h - l)
            if close_pos >= 0.7:
                score += 1
    except Exception:
        pass

    # Volume + liquidity
    try:
        if "Volume" in df.columns and len(df) >= 30:
            current_vol = float(df["Volume"].iloc[-1])
            avg_vol20 = float(df["Volume"].rolling(window=20).mean().iloc[-1])
            if avg_vol20 > 0 and current_vol >= avg_vol20 * 1.8:
                score += 1
            traded_value20 = float((df["Close"] * df["Volume"]).rolling(window=20).mean().iloc[-1])
            if traded_value20 >= 1_000_000:
                score += 1
    except Exception:
        pass

    # Relative strength vs benchmark over ~3 months
    rs_3m = None
    try:
        if benchmark_df is not None and not benchmark_df.empty and "Close" in benchmark_df.columns:
            join = pd.concat([df["Close"], benchmark_df["Close"]], axis=1, join="inner").dropna()
            if len(join) >= 70:
                s_now, s_prev = float(join.iloc[-1, 0]), float(join.iloc[-64, 0])
                b_now, b_prev = float(join.iloc[-1, 1]), float(join.iloc[-64, 1])
                if s_prev > 0 and b_prev > 0:
                    rs_3m = (s_now / s_prev) - (b_now / b_prev)
                    if rs_3m > 0:
                        score += 1
    except Exception:
        pass

    # ATR contraction
    atr_contraction = False
    try:
        if len(df) >= 40:
            prev_close = df["Close"].shift(1)
            tr = pd.concat([(df["High"] - df["Low"]).abs(), (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
            atr14 = tr.rolling(window=14).mean()
            atr_pct = atr14 / df["Close"]
            recent = float(pd.to_numeric(atr_pct.tail(5), errors="coerce").dropna().mean())
            prior = float(pd.to_numeric(atr_pct.iloc[-25:-5], errors="coerce").dropna().mean())
            if prior > 0 and recent > 0 and recent <= prior * 0.8:
                atr_contraction = True
                score += 1
    except Exception:
        pass

    code, name, analysis, catalyst = _resolve_insight(ticker, resolved_name)
    extra = _calc_extra_indicators(df)

    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "price": float(round(current_close, 3)),
        "rsi": float(round(rsi, 2)),
        "score": int(score),
        "score_max": int(score_max),
        "analysis": analysis,
        "catalyst": catalyst,
        "breakout_55": bool(breakout_55),
        "breakout_level": breakout_level,
        "rs_3m": None if rs_3m is None else float(rs_3m),
        "atr_contraction": bool(atr_contraction),
        **extra,
        "model": "v2",
    }


def analyze_breakout_v3(
    ticker,
    df,
    resolved_name=None,
    benchmark_df=None,
    min_rows: int = 120,
    signal_lookback: int = 5,
    max_runup_pct=None,
    max_pullback_pct=None,
    retest_days: int = 0,
    breakout_buffer_pct: float | None = None,
    volume_spike_mult: float | None = None,
    power_close_pos_min: float | None = None,
    power_body_pct_min: float | None = None,
    min_traded_value20: float | None = None,
    require_rs_positive: bool = False,
    require_atr_contraction: bool = False,
    require_benchmark_trend: bool = False,
):
    """
    Breakout candle (V3) model. Score range: 0-11.
    Adds a "breakout candle" bonus when:
      - 55d breakout (with optional buffer)
      - bullish power candle
      - volume spike
    Also supports optional retest confirmation logic.
    """
    if df is None or len(df) < int(min_rows):
        return None

    ticker = str(ticker).upper().strip()
    df = df.copy()
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    try:
        current_close = float(df["Close"].iloc[-1])
        if not (current_close > 0.0):
            return None
    except Exception:
        return None

    rsi = 50.0
    try:
        rsi_v = RSIIndicator(df["Close"], window=14).rsi().iloc[-1]
        if rsi_v == rsi_v:
            rsi = float(rsi_v)
    except Exception:
        pass

    sma50 = sma200 = None
    try:
        sma50 = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-1])
        if len(df) >= 220:
            sma200 = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-1])
    except Exception:
        pass

    score = 0
    score_max = 11

    # Trend strength
    try:
        if sma50 is not None and current_close > sma50:
            sma50_prev = float(SMAIndicator(df["Close"], window=50).sma_indicator().iloc[-6])
            if sma50_prev == sma50_prev and sma50 > sma50_prev:
                score += 2
    except Exception:
        pass

    try:
        if sma200 is not None and current_close > sma200:
            sma200_prev = float(SMAIndicator(df["Close"], window=200).sma_indicator().iloc[-6])
            if sma200_prev == sma200_prev and sma200 > sma200_prev:
                score += 2
    except Exception:
        pass

    # Liquidity
    liquidity_ok = False
    try:
        min_tv = 1_000_000.0 if min_traded_value20 is None else float(min_traded_value20)
        traded_value20 = float((df["Close"] * df["Volume"]).rolling(window=20).mean().shift(1).iloc[-1])
        if traded_value20 >= float(min_tv):
            liquidity_ok = True
            score += 1
    except Exception:
        pass

    # Relative strength (optional gate)
    rs_3m = None
    try:
        if benchmark_df is not None and not benchmark_df.empty and "Close" in benchmark_df.columns:
            join = pd.concat([df["Close"], benchmark_df["Close"]], axis=1, join="inner").dropna()
            if len(join) >= 70:
                s_now, s_prev = float(join.iloc[-1, 0]), float(join.iloc[-64, 0])
                b_now, b_prev = float(join.iloc[-1, 1]), float(join.iloc[-64, 1])
                if s_prev > 0 and b_prev > 0:
                    rs_3m = (s_now / s_prev) - (b_now / b_prev)
                    if rs_3m > 0:
                        score += 1
    except Exception:
        pass
    if require_rs_positive and rs_3m is not None and rs_3m <= 0:
        return None

    # ATR contraction (optional gate)
    atr_contraction = False
    try:
        prev_close = df["Close"].shift(1)
        tr = pd.concat([(df["High"] - df["Low"]).abs(), (df["High"] - prev_close).abs(), (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
        atr14 = tr.rolling(window=14).mean()
        atr_pct = atr14 / df["Close"]
        recent = float(pd.to_numeric(atr_pct.tail(5), errors="coerce").dropna().mean())
        prior = float(pd.to_numeric(atr_pct.iloc[-25:-5], errors="coerce").dropna().mean())
        if prior > 0 and recent > 0 and recent <= prior * 0.8:
            atr_contraction = True
            score += 1
    except Exception:
        pass
    if require_atr_contraction and not atr_contraction:
        return None

    # Benchmark trend (optional gate) - simple: KLSE above SMA50 and rising
    bench_trend_ok = None
    try:
        if benchmark_df is not None and not benchmark_df.empty and "Close" in benchmark_df.columns and len(benchmark_df) >= 60:
            b = pd.to_numeric(benchmark_df["Close"], errors="coerce").dropna()
            sma_b = b.rolling(50).mean()
            bench_trend_ok = bool(b.iloc[-1] > sma_b.iloc[-1] and sma_b.iloc[-1] > sma_b.iloc[-6])
    except Exception:
        bench_trend_ok = None
    if require_benchmark_trend and bench_trend_ok is False:
        return None

    # Breakout candle logic
    try:
        lookback_days = int(signal_lookback)
    except Exception:
        lookback_days = 5
    lookback_days = max(1, min(20, lookback_days))

    buf_pct = 0.0 if breakout_buffer_pct is None else float(breakout_buffer_pct)
    buf_pct = max(0.0, buf_pct)
    vol_mult = 1.8 if volume_spike_mult is None else float(volume_spike_mult)
    vol_mult = max(1.0, vol_mult)
    close_pos_min = 0.7 if power_close_pos_min is None else float(power_close_pos_min)
    close_pos_min = max(0.0, min(1.0, close_pos_min))
    body_pct_min = 0.55 if power_body_pct_min is None else float(power_body_pct_min)
    body_pct_min = max(0.0, min(1.0, body_pct_min))

    breakout_lookback = 55
    breakout_55 = False
    breakout_candle = False
    breakout_candle_valid = False
    breakout_hold_ok = False
    power_candle = False
    volume_spike = False
    breakout_candle_ts = None
    breakout_candle_vol = None
    breakout_candle_close = None

    # find breakout candle within lookback window (most recent wins)
    try:
        if len(df) >= breakout_lookback + 5 and "Volume" in df.columns:
            prior_high_series = df["Close"].rolling(window=breakout_lookback).max().shift(1)
            avg_vol20 = df["Volume"].rolling(window=20).mean().shift(1)
            start_i = max(1, len(df) - lookback_days)
            for i in range(len(df) - 1, start_i - 1, -1):
                ph = float(prior_high_series.iloc[i])
                if not (ph > 0.0):
                    continue
                thr = ph * (1.0 + (buf_pct / 100.0))
                c = float(df["Close"].iloc[i])
                o = float(df["Open"].iloc[i])
                h = float(df["High"].iloc[i])
                l = float(df["Low"].iloc[i])
                v = float(df["Volume"].iloc[i])
                avg_v = float(avg_vol20.iloc[i]) if pd.notna(avg_vol20.iloc[i]) else 0.0
                if c > thr:
                    breakout_55 = True
                    # power candle
                    if h > l:
                        close_pos = (c - l) / (h - l)
                    else:
                        close_pos = 0.0
                    body = abs(c - o)
                    rng = max(1e-9, h - l)
                    body_pct = body / rng
                    power_candle = (c > o) and (close_pos >= close_pos_min) and (body_pct >= body_pct_min)
                    volume_spike = (avg_v > 0 and v >= avg_v * vol_mult)
                    breakout_candle = True
                    breakout_candle_ts = df.index[i]
                    breakout_candle_close = c
                    breakout_candle_vol = v
                    breakout_candle_valid = bool(power_candle and volume_spike)
                    # hold check: today's close above breakout candle low
                    try:
                        today_low = float(df["Low"].iloc[-1])
                        breakout_hold_ok = bool(float(df["Close"].iloc[-1]) >= today_low)
                    except Exception:
                        breakout_hold_ok = False
                    break
    except Exception:
        pass

    if breakout_candle_valid:
        score += 2  # breakout candle bonus

    # retest confirm (optional): within N days, touch breakout level and close above it
    retest_confirmed = False
    retest_touch_date = ""
    try:
        rd = int(retest_days) if retest_days is not None else 0
    except Exception:
        rd = 0
    rd = max(0, min(20, rd))
    if rd > 0 and breakout_candle_ts is not None:
        try:
            idx = df.index
            i0 = list(idx).index(breakout_candle_ts)
            end = min(len(df) - 1, i0 + rd)
            # breakout level approximate: prior 55d high at candle time
            prior_high = float(df["Close"].iloc[i0 - breakout_lookback:i0].max())
            ceiling = prior_high * 1.01
            hold = prior_high * 0.995
            for j in range(i0 + 1, end + 1):
                low_j = float(df["Low"].iloc[j])
                close_j = float(df["Close"].iloc[j])
                if low_j <= ceiling and close_j >= hold:
                    retest_confirmed = True
                    retest_touch_date = pd.Timestamp(idx[j]).date().isoformat()
                    break
        except Exception:
            retest_confirmed = False

    # run-up and pullback (used by UI filters)
    breakout_level = None
    runup_pct = None
    distance_to_breakout_pct = None
    near_breakout = False
    try:
        prior_high = float(df["Close"].iloc[-breakout_lookback:-1].max())
        breakout_level = prior_high * (1.0 + (buf_pct / 100.0))
        if breakout_level and breakout_level > 0:
            distance_to_breakout_pct = ((current_close / breakout_level) - 1.0) * 100.0
            if (not breakout_candle_valid) and (not retest_confirmed) and (distance_to_breakout_pct is not None):
                if float(distance_to_breakout_pct) < 0.0 and float(distance_to_breakout_pct) >= -1.0:
                    near_breakout = True
        if breakout_candle_close and breakout_level and breakout_level > 0:
            runup_pct = ((breakout_candle_close / breakout_level) - 1.0) * 100.0
    except Exception:
        pass

    max_runup_val = None
    max_pullback_val = None
    try:
        max_runup_val = None if max_runup_pct is None else float(max_runup_pct)
    except Exception:
        max_runup_val = None
    try:
        max_pullback_val = None if max_pullback_pct is None else float(max_pullback_pct)
    except Exception:
        max_pullback_val = None

    breakout_candle_date = ""
    breakout_candle_age = None
    if breakout_candle_ts is not None:
        try:
            d = pd.Timestamp(breakout_candle_ts).date()
            breakout_candle_date = d.isoformat()
            today = pd.Timestamp.now(tz="Asia/Kuala_Lumpur").date()
            breakout_candle_age = int((today - d).days)
        except Exception:
            breakout_candle_date = ""
            breakout_candle_age = None

    code, name, sector, analysis, catalyst = _resolve_insight_v3(ticker, resolved_name)
    extra = _calc_extra_indicators(df)

    return {
        "ticker": ticker,
        "code": code,
        "name": name,
        "sector": sector,
        "price": float(round(current_close, 3)),
        "rsi": float(round(rsi, 2)),
        "score": int(score),
        "score_max": int(score_max),
        "analysis": analysis,
        "catalyst": catalyst,
        "rs_3m": None if rs_3m is None else float(rs_3m),
        "atr_contraction": bool(atr_contraction),
        "bench_trend_ok": None if bench_trend_ok is None else bool(bench_trend_ok),
        "breakout_55": bool(breakout_55),
        "power_candle": bool(power_candle),
        "volume_spike": bool(volume_spike),
        "liquidity_ok": bool(liquidity_ok),
        "breakout_candle": bool(breakout_candle),
        "breakout_candle_valid": bool(breakout_candle_valid),
        "breakout_hold_ok": bool(breakout_hold_ok),
        "breakout_candle_date": breakout_candle_date,
        "breakout_candle_age": breakout_candle_age,
        "signal_lookback": int(lookback_days),
        "breakout_candle_close": None if breakout_candle_close is None else float(breakout_candle_close),
        "breakout_candle_vol": None if breakout_candle_vol is None else float(breakout_candle_vol),
        "runup_pct": None if runup_pct is None else float(runup_pct),
        "max_runup_pct": None if max_runup_val is None else float(max_runup_val),
        "max_pullback_pct": None if max_pullback_val is None else float(max_pullback_val),
        "retest_days": int(rd),
        "retest_confirmed": bool(retest_confirmed),
        "retest_touch_date": retest_touch_date,
        "breakout_level": None if breakout_level is None else float(breakout_level),
        "distance_to_breakout_pct": None if distance_to_breakout_pct is None else float(distance_to_breakout_pct),
        "near_breakout": bool(near_breakout),
        **extra,
        "model": "v3",
    }


# ----------------------------
# Scanners
# ----------------------------
FUTURES_COMPONENTS = ["FKLI=F", "FCPO=F", "FM70=F"]


def get_futures_breakouts() -> list[dict]:
    results: list[dict] = []
    for ticker in FUTURES_COMPONENTS:
        df, name = get_stock_data(ticker, period="2y")
        if df is None or df.empty:
            continue
        min_r = 30 if len(df) >= 30 else len(df)
        r = analyze_breakout(ticker, df, name, min_rows=min_r)
        if r:
            results.append(r)
    return results


def get_top_breakouts(
    limit: int = 10,
    model: str = "v2",
    universe_mode: str = "curated",
    universe: list[str] | None = None,
    sector_allowlist=None,
    signal_lookback: int = 5,
    max_runup_pct=None,
    max_pullback_pct=None,
    retest_days: int = 0,
    max_tickers=None,
    breakout_buffer_pct: float | None = None,
    volume_spike_mult: float | None = None,
    power_close_pos_min: float | None = None,
    power_body_pct_min: float | None = None,
    min_traded_value20: float | None = None,
    require_rs_positive: bool = False,
    require_atr_contraction: bool = False,
    require_benchmark_trend: bool = False,
) -> list[dict]:
    m = str(model or "v2").lower().strip()
    tickers = list(universe) if universe is not None else list(get_stock_universe(universe_mode)[0])
    try:
        if max_tickers is not None:
            n = int(max_tickers)
            if n > 0:
                tickers = tickers[:n]
    except Exception:
        pass

    allow = None
    if m == "v3" and sector_allowlist:
        allow = {str(x).strip().lower() for x in sector_allowlist if str(x).strip()}

    benchmark_df = None
    if m in {"v2", "v3"}:
        try:
            benchmark_df, _ = get_stock_data("^KLSE", period="1y")
        except Exception:
            benchmark_df = None

    all_results: list[dict] = []
    for ticker in tickers:
        t = str(ticker).upper().strip()
        if not t:
            continue
        if allow:
            try:
                _, _, sec, *_ = _resolve_insight_v3(t, None)
                if sec and str(sec).strip().lower() not in allow:
                    continue
            except Exception:
                pass

        df, resolved_name = get_stock_data(t, period="1y")
        if df is None or df.empty:
            continue

        if m == "v3":
            res = analyze_breakout_v3(
                t,
                df,
                resolved_name,
                benchmark_df=benchmark_df,
                min_rows=120,
                signal_lookback=signal_lookback,
                max_runup_pct=max_runup_pct,
                max_pullback_pct=max_pullback_pct,
                retest_days=retest_days,
                breakout_buffer_pct=breakout_buffer_pct,
                volume_spike_mult=volume_spike_mult,
                power_close_pos_min=power_close_pos_min,
                power_body_pct_min=power_body_pct_min,
                min_traded_value20=min_traded_value20,
                require_rs_positive=bool(require_rs_positive),
                require_atr_contraction=bool(require_atr_contraction),
                require_benchmark_trend=bool(require_benchmark_trend),
            )
        elif m == "v2":
            res = analyze_breakout_v2(t, df, resolved_name, benchmark_df=benchmark_df, min_rows=120)
        else:
            res = analyze_breakout(t, df, resolved_name)
        if res:
            all_results.append(res)

    if m == "v3":
        all_results.sort(
            key=lambda x: (
                bool(x.get("retest_confirmed")),
                bool(x.get("breakout_candle_valid")),
                int(x.get("score", 0)),
                -float(x.get("rsi", 0.0) or 0.0),
            ),
            reverse=True,
        )
    else:
        all_results.sort(key=lambda x: (int(x.get("score", 0)), -float(x.get("rsi", 0.0) or 0.0)), reverse=True)

    return all_results[: int(limit)]


def search_bursa(query):
    q = str(query or "").upper().strip()
    if not q:
        return None
    if q == "FKLI":
        return "FKLI=F"
    if q == "FCPO":
        return "FCPO=F"
    if q == "FM70":
        return "FM70=F"
    if q in {"^KLSE", "^KLCI", "^KLSI"}:
        return "^KLSE"
    if q.endswith(".KL") and len(q.split(".")[0]) == 4 and q.split(".")[0].isdigit():
        return q
    if q.isdigit() and len(q) == 4:
        return f"{q}.KL"
    if q in MARKET_INSIGHTS:
        return q
    # match by name or code (curated set)
    for k, v in MARKET_INSIGHTS.items():
        code = str(v.get("code") or "").upper().strip()
        name = str(v.get("name") or "").upper().strip()
        if q == code or q == name:
            return str(k).upper().strip()
    for k, v in MARKET_INSIGHTS.items():
        name = str(v.get("name") or "").upper().strip()
        if name and q in re.split(r"[^A-Z0-9]+", name):
            return str(k).upper().strip()

    # match against auto-universe name map (supports partial matches)
    try:
        mp = _load_auto_universe_name_map()
        if mp:
            # exact name match first
            for t, nm in mp.items():
                if q == str(nm).upper().strip():
                    return str(t).upper().strip()
            # then substring match (first hit)
            for t, nm in mp.items():
                if q and q in str(nm).upper():
                    return str(t).upper().strip()
    except Exception:
        pass

    # Yahoo search fallback (fixes cases like "genetec" -> 0104.KL)
    # This runs only when local maps can't resolve the query.
    try:
        now = time.time()
        cached = _SEARCH_CACHE.get(q)
        if cached and (now - float(cached[0])) <= float(_SEARCH_CACHE_SECONDS):
            return cached[1]
        out = None
        try:
            s = yf.Search(q)
            quotes = getattr(s, "quotes", None) or []
            # Prefer Bursa/KLS + .KL symbols
            for it in quotes:
                sym = str((it or {}).get("symbol") or "").upper().strip()
                exch = str((it or {}).get("exchange") or "").upper().strip()
                if sym.endswith(".KL") and (exch in {"KLS", "KLSE"} or "KUALA" in str((it or {}).get("exchDisp") or "").upper()):
                    out = sym
                    nm = (it or {}).get("shortname") or (it or {}).get("longname") or ""
                    if nm:
                        try:
                            mp2 = _load_auto_universe_name_map()
                            mp2[out] = _short_company_name(str(nm))
                        except Exception:
                            pass
                    break
            # Any .KL result as fallback
            if out is None:
                for it in quotes:
                    sym = str((it or {}).get("symbol") or "").upper().strip()
                    if sym.endswith(".KL"):
                        out = sym
                        break
        except Exception:
            out = None
        _SEARCH_CACHE[q] = (now, out)
        return out
    except Exception:
        return None
    return None


# ----------------------------
# RSS news + trend inference
# ----------------------------
_NEWS_CACHE: dict[str, tuple[float, list[dict]]] = {}


def _parse_rss_items(xml_text: str, source: str, limit: int = 30) -> list[dict]:
    out: list[dict] = []
    if not xml_text:
        return out
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    items = root.findall(".//item")
    for it in items:
        try:
            title = unescape(str(it.findtext("title") or "")).strip()
            link = str(it.findtext("link") or "").strip()
            pub = str(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "")
            dt = None
            if pub:
                try:
                    dt = parsedate_to_datetime(pub)
                except Exception:
                    dt = None
            out.append(
                {
                    "title": title,
                    "link": link,
                    "published": pub,
                    "published_ts": None if dt is None else float(dt.timestamp()),
                    "source": str(source),
                }
            )
        except Exception:
            continue
        if len(out) >= int(limit):
            break
    return out


def get_latest_market_news(limit: int = 40, cache_seconds: int = 600, feeds: dict | None = None) -> list[dict]:
    default_feeds = {
        "Google News: Bursa Malaysia": "https://news.google.com/rss/search?q=Bursa%20Malaysia&hl=en-MY&gl=MY&ceid=MY:en",
        "Google News: KLCI": "https://news.google.com/rss/search?q=KLCI&hl=en-MY&gl=MY&ceid=MY:en",
        "Google News: Malaysia OPR": "https://news.google.com/rss/search?q=Malaysia%20OPR&hl=en-MY&gl=MY&ceid=MY:en",
    }
    feed_map = feeds if isinstance(feeds, dict) and feeds else default_feeds
    merged: list[dict] = []
    now = time.time()
    for src, url in feed_map.items():
        if not url:
            continue
        cache_key = f"rss:{src}:{url}"
        cached = _NEWS_CACHE.get(cache_key)
        if cached and (now - float(cached[0])) <= float(cache_seconds):
            items = list(cached[1] or [])
        else:
            items = []
            try:
                r = requests.get(
                    str(url),
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
                    timeout=20,
                )
                txt = r.text if getattr(r, "text", None) is not None else ""
                if int(getattr(r, "status_code", 0) or 0) == 200 and txt:
                    items = _parse_rss_items(txt, source=str(src), limit=50)
            except Exception:
                items = []
            _NEWS_CACHE[cache_key] = (now, items)
        merged.extend(items)
    seen = set()
    uniq: list[dict] = []
    for it in merged:
        k = str(it.get("link") or "").strip() or str(it.get("title") or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    uniq.sort(key=lambda x: float(x.get("published_ts") or 0.0), reverse=True)
    return uniq[: int(limit)]


def google_news_rss_url(query: str, hl: str = "en-MY", gl: str = "MY", ceid: str = "MY:en") -> str:
    q = str(query or "").strip()
    if not q:
        return ""
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl={quote_plus(hl)}&gl={quote_plus(gl)}&ceid={quote_plus(ceid)}"


def infer_market_trends_from_news(news_items: list[dict], top_n: int = 6) -> dict:
    kw = {
        "Technology": ["ai", "data center", "datacentre", "semiconductor", "chip", "5g", "cloud"],
        "Energy": ["oil", "opec", "brent", "crude", "lng", "gas", "petroleum"],
        "Banking": ["opr", "rate", "inflation", "bnm", "ringgit", "bond", "yield"],
        "Utilities": ["tariff", "grid", "renewable", "solar", "power", "electricity", "netr"],
        "Infrastructure": ["infrastructure", "construction", "rail", "mrt", "lrt", "highway", "project"],
        "Telco": ["telco", "telecom", "maxis", "digi", "axiata", "tower", "broadband"],
        "Plantation": ["cpo", "palm oil", "plantation", "biodiesel"],
        "Property": ["property", "reits", "reit", "housing", "real estate"],
        "Healthcare": ["health", "hospital", "pharma", "medical"],
        "Consumer": ["consumer", "retail", "spending", "inflation", "gst"],
        "Defense": ["defense", "defence", "military", "missile", "drone"],
        "Shipping": ["shipping", "strait", "hormuz", "red sea", "freight", "logistics", "port"],
        "Metals": ["gold", "copper", "nickel", "tin", "metal", "commodit"],
    }
    macro = {
        "Rates / Central Banks": ["opr", "rate", "bnm", "inflation", "yield", "fed", "fomc", "powell", "ecb", "boj"],
        "US Macro": ["cpi", "ppi", "jobs", "payroll", "unemployment", "ism", "gdp", "recession", "soft landing"],
        "FX": ["ringgit", "fx", "usd", "dollar", "yen", "yuan", "euro"],
        "Commodities": ["oil", "brent", "crude", "cpo", "palm oil", "gas", "lng", "gold", "copper"],
        "Risk / Geopolitics": ["middle east", "iran", "israel", "geopolit", "war", "sanction", "strait", "hormuz", "red sea", "ukraine", "russia"],
        "Markets / Risk-on": ["s&p", "nasdaq", "dow", "vix", "risk", "sell-off", "rally"],
    }
    sector_scores: dict[str, int] = {k: 0 for k in kw.keys()}
    theme_scores: dict[str, int] = {k: 0 for k in macro.keys()}
    for it in (news_items or []):
        t = (str(it.get("title") or "") + " " + str(it.get("source") or "")).lower()
        if not t:
            continue
        for sec, words in kw.items():
            for w in words:
                if w and w in t:
                    sector_scores[sec] += 1
                    break
        for th, words in macro.items():
            for w in words:
                if w and w in t:
                    theme_scores[th] += 1
                    break
    sector_ranked = sorted(sector_scores.items(), key=lambda kv: kv[1], reverse=True)
    theme_ranked = sorted(theme_scores.items(), key=lambda kv: kv[1], reverse=True)
    sectors = [{"sector": k, "mentions": int(v)} for k, v in sector_ranked if int(v) > 0][: int(top_n)]
    themes = [{"theme": k, "mentions": int(v)} for k, v in theme_ranked if int(v) > 0][: int(top_n)]
    return {"themes": themes, "sectors": sectors, "sector_scores": sector_scores, "theme_scores": theme_scores}


def summarize_market_impacts(trends: dict) -> list[str]:
    try:
        theme_scores = dict((trends or {}).get("theme_scores") or {})
        sector_scores = dict((trends or {}).get("sector_scores") or {})
    except Exception:
        theme_scores = {}
        sector_scores = {}
    notes: list[str] = []
    if int(theme_scores.get("Risk / Geopolitics", 0) or 0) > 0:
        notes.append("Geopolitics headlines up: watch oil, freight, defense; risk-off can pressure growth and small caps.")
    if int(theme_scores.get("Rates / Central Banks", 0) or 0) > 0 or int(theme_scores.get("US Macro", 0) or 0) > 0:
        notes.append("Rates/macro in focus: banks, REITs, utilities and high-debt names are more sensitive to yields/OPR/Fed expectations.")
    if int(sector_scores.get("Energy", 0) or 0) > 0 or int(sector_scores.get("Shipping", 0) or 0) > 0:
        notes.append("Energy/shipping themes: oil & gas upstream, ports/logistics can move with crude and freight disruptions.")
    if int(sector_scores.get("Technology", 0) or 0) > 0:
        notes.append("Tech themes: semicon/AI/data-center related counters tend to follow global risk appetite and US tech leadership.")
    if int(sector_scores.get("Metals", 0) or 0) > 0:
        notes.append("Metals themes: gold/copper news often ties to risk sentiment and China/US growth expectations.")
    if int(theme_scores.get("FX", 0) or 0) > 0:
        notes.append("FX headlines: ringgit and USD moves can impact exporters/importers and commodity-linked earnings translation.")
    return notes[:6]
