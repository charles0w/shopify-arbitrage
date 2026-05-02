"""
Fetch Google Trends interest score for a keyword.
Returns 0.0–1.0: ratio of current week vs. 12-month peak.
pytrends needs no API key but rate-limits aggressively — add sleep between calls.
"""
import time
import random
from pytrends.request import TrendReq


_pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 30))


def trend_score(keyword: str) -> float:
    """Return 0.0–1.0 trend velocity for keyword over the past 12 months."""
    try:
        _pytrends.build_payload([keyword], timeframe="today 12-m", geo="US")
        df = _pytrends.interest_over_time()
        if df.empty or keyword not in df.columns:
            return 0.0
        series = df[keyword]
        peak = series.max()
        if peak == 0:
            return 0.0
        # Use last 4 weeks average as "current" interest
        recent = series.iloc[-4:].mean()
        score = recent / peak
        # Smooth: penalise declining trends
        overall_mean = series.mean()
        if recent < overall_mean:
            score *= 0.75
        return round(float(score), 4)
    except Exception:
        return 0.0
    finally:
        # Avoid rate-limit: sleep 1–3s between calls
        time.sleep(random.uniform(1.0, 3.0))


def batch_trend_scores(keywords: list[str]) -> dict[str, float]:
    return {kw: trend_score(kw) for kw in keywords}
