"""
五维评分引擎 V1.0
100分制：趋势强度25 + 量能健康度20 + 衰竭信号25 + 均线支撑15 + 形态匹配15
"""

from typing import List, Dict, Optional, Tuple
from utils import sma, bar_chart
def _bar(score: int, max_score: int, width: int = 10) -> str:
    """绘制进度条"""
    return bar_chart(score, max_score, width)


def score_trend_strength(kline: List[dict], params: dict = None, detect_result: dict = None) -> dict:
    """趋势强度 25分 + 底部反转额外加分"""
    p = params or {}
    max_score = 25
    score = 0
    details = []
    
    if len(kline) < 60:
        return {'score': 0, 'max': max_score, 'label': '趋势强度', 'details': ['K线不足60日']}
    
    closes = [k['close'] for k in kline]
    lows = [k['low'] for k in kline]
    opens = [k['open'] for k in kline]
    vols = [k['volume'] for k in kline]
    n = len(kline)
    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    
    # MA多头排列 +15
    if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
        score += 15
        details.append('四线多头排列(+15)')
    elif ma10[-1] > ma20[-1] > ma60[-1]:
        score += 10
        details.append('MA10>20>60多头(+10)')
    elif ma20[-1] > ma60[-1]:
        score += 5
        details.append('MA20>MA60(+5)')
    
    # 站上MA20 +5
    if closes[-1] > ma20[-1]:
        score += 5
        details.append(f'站上MA20({ma20[-1]:.2f})(+5)')
    else:
        score -= 10
        details.append(f'跌破MA20({ma20[-1]:.2f})(-10)')
    
    # 站上MA60 +5（M1康复中跌破MA60仅轻罚）
    if closes[-1] > ma60[-1]:
        score += 5
        details.append(f'站上MA60({ma60[-1]:.2f})(+5)')
    else:
        # 检测M1康复场景
        m1_hold = False
        if detect_result:
            hold = detect_result.get('hold_patterns', [])
            m1_hold = any('M1' in h.get('name', '') or '底部启动' in h.get('name', '') for h in hold)
        
        if m1_hold and closes[-1] > ma20[-1]:
            score -= 5
            details.append(f'M1康复中跌破MA60({ma60[-1]:.2f})轻罚(-5)')
        else:
            score -= 15
            details.append(f'跌破MA60({ma60[-1]:.2f})(-15)')
    
    # === 底部反转加分：距60日低点<15%出现放量阳线 +10 ===
    low_60 = min(lows[-min(60, n):])
    dist_from_low = (closes[-1] - low_60) / low_60 * 100 if low_60 > 0 else 100
    is_bullish = closes[-1] > opens[-1]
    avg_vol_5 = sum(vols[-6:-1]) / 5 if n >= 6 else vols[-1]
    is_volume_break = vols[-1] > avg_vol_5 * 1.3
    
    if dist_from_low < 15 and is_bullish and is_volume_break:
        score += 10
        details.append(f'底部反转：距60日低{low_60:.2f}仅{dist_from_low:.1f}%放量阳线(+10)')
    
    score = max(0, min(max_score, score))
    return {'score': score, 'max': max_score, 'label': '趋势强度', 'details': details}


def score_volume_health(kline: List[dict], params: dict = None) -> dict:
    """量能健康度 20分"""
    max_score = 20
    score = 0
    details = []
    
    if len(kline) < 10:
        return {'score': 0, 'max': max_score, 'label': '量能健康度', 'details': ['K线不足']}
    
    closes = [k['close'] for k in kline]
    opens = [k['open'] for k in kline]
    vols = [k['volume'] for k in kline]
    n = len(kline)
    
    # 温和放量 +10（近5日均量 > 前20日均量，但不爆量<3x）
    vol_5 = sum(vols[-5:]) / 5
    vol_20 = sum(vols[-25:-5]) / 20 if n >= 25 else vol_5
    if vol_5 > vol_20 and vol_5 < vol_20 * 3:
        score += 10
        details.append('温和放量(+10)')
    elif vol_5 > vol_20 * 3:
        score += 5
        details.append(f'爆量({vol_5/vol_20:.1f}x)(+5)')
    else:
        details.append(f'量能萎缩({vol_5/vol_20:.1f}x)')
    
    # 上涨放量下跌缩量 +10
    up_vol = 0
    down_vol = 0
    up_count = 0
    down_count = 0
    for i in range(n-5, n):
        if closes[i] > opens[i]:
            up_vol += vols[i]
            up_count += 1
        else:
            down_vol += vols[i]
            down_count += 1
    
    if up_count > 0 and down_count > 0:
        avg_up = up_vol / up_count
        avg_down = down_vol / down_count
        if avg_up > avg_down:
            score += 10
            details.append('涨放量跌缩量(+10)')
        else:
            score -= 5
            details.append('量价背离(-5)')
    elif up_count > 0:
        score += 5
        details.append('近5日全阳(+5)')
    
    # 放量滞涨检查 -8
    for i in range(n-3, n):
        chg = abs(closes[i] - opens[i]) / opens[i] * 100
        avg_vol_5 = sum(vols[max(0,i-5):i]) / min(5, i)
        if vols[i] > avg_vol_5 * 2 and chg < 1:
            score -= 8
            details.append(f'{kline[i]["date"]}放量滞涨(-8)')
            break
    
    score = max(0, min(max_score, score))
    return {'score': score, 'max': max_score, 'label': '量能健康度', 'details': details}


def score_exhaustion(kline: List[dict], params: dict = None, detect_result: dict = None) -> dict:
    """衰竭信号 25分"""
    max_score = 25
    score = 25  # 满分开始，逐个扣
    details = []
    
    if len(kline) < 20:
        return {'score': 0, 'max': max_score, 'label': '衰竭信号', 'details': ['K线不足']}
    
    closes = [k['close'] for k in kline]
    opens = [k['open'] for k in kline]
    highs = [k['high'] for k in kline]
    n = len(kline)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60) if n >= 60 else [0]
    
    # M1早期康复豁免：M1活跃且价格<MA60时，初期拉升是康复而非过热
    m1_active = False
    below_ma60 = ma60[-1] > 0 and closes[-1] < ma60[-1]
    if detect_result:
        hold = detect_result.get('hold_patterns', [])
        m1_hits = [h for h in hold if 'M1' in h.get('name', '') or '底部启动' in h.get('name', '')]
        m1_active = len(m1_hits) > 0
    
    m1_recovery = m1_active and below_ma60
    
    
    # 涨幅过热 -10（区分趋势加速 vs 超跌修复 vs M1早期康复）
    gain_20 = (closes[-1] - closes[-20]) / closes[-20] * 100
    gain_10 = (closes[-1] - closes[-10]) / closes[-10] * 100
    
    # 距60日高点回撤>40% -> 超跌修复场景，阈值放宽
    peak_60 = max(highs[-min(60, n):])
    dd_from_peak = (closes[-1] - peak_60) / peak_60 * 100 if peak_60 > 0 else 0
    is_bounce = dd_from_peak < -40
    
    # M1早期康复：底部启动的初期拉升是康复表现，豁免过热/加速惩罚
    if m1_recovery:
        score += 3
        details.append(f'M1底部康复(+3，涨幅{gain_10:.1f}%为正常修复)')
    else:
        gain20_threshold = 35 if is_bounce else 20
        gain10_threshold = 25 if is_bounce else 15
        
        if gain_20 > gain20_threshold:
            score -= 10
            scenario = "(超跌修复放宽)" if is_bounce else ""
            details.append(f'20日涨{gain_20:.1f}%过热{scenario}(-10)')
        elif gain_10 > gain10_threshold:
            score -= 5
            scenario = "(超跌修复放宽)" if is_bounce else ""
            details.append(f'10日涨{gain_10:.1f}%加速{scenario}(-5)')
        elif gain_20 < 5 and gain_10 < 3:
            score += 5
            details.append(f'涨幅适中(+5)')
    
    # 上影频繁 -8
    upper_count = 0
    for i in range(n-5, n):
        upper = (highs[i] - max(closes[i], opens[i])) / highs[i] * 100 if highs[i] > 0 else 0
        if upper > 3:
            upper_count += 1
    if upper_count >= 3:
        score -= 8
        details.append(f'上影频繁({upper_count}/5日)(-8)')
    elif upper_count == 0:
        score += 3
        details.append('无上影线(+3)')
    
    # 乖离过大 -7（M1早期康复免罚：底部拉升高乖离为正常表现）
    deviation = (closes[-1] - ma20[-1]) / ma20[-1] * 100
    if deviation > 15:
        if m1_recovery:
            score += 2
            details.append(f'M1康复乖离{deviation:.1f}%无需惩罚(+2)')
        else:
            score -= 7
            details.append(f'乖离{deviation:.1f}%(-7)')
    elif deviation < -10:
        score -= 5
        details.append(f'负乖离{deviation:.1f}%(-5)')
    
    # 回撤
    peak_10 = max(closes[-10:])
    dd = (closes[-1] - peak_10) / peak_10 * 100
    if dd > -3:
        score += 3
        details.append('回撤小(+3)')
    elif dd < -10:
        score -= 5
        details.append(f'回撤{abs(dd):.1f}%(-5)')
    
    score = max(0, min(max_score, score))
    return {'score': score, 'max': max_score, 'label': '衰竭信号', 'details': details}


def score_ma_support(kline: List[dict], params: dict = None, detect_result: dict = None) -> dict:
    """均线支撑 15分"""
    max_score = 15
    score = 0
    details = []
    
    if len(kline) < 60:
        return {'score': 0, 'max': max_score, 'label': '均线支撑', 'details': ['K线不足']}
    
    closes = [k['close'] for k in kline]
    n = len(kline)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    
    supports = [
        ('MA10', ma10[-1], closes[-1] > ma10[-1]),
        ('MA20', ma20[-1], closes[-1] > ma20[-1]),
        ('MA60', ma60[-1], closes[-1] > ma60[-1]),
    ]
    
    for name, ma_val, above in supports:
        if above:
            score += 5
            details.append(f'{name}({ma_val:.2f})支撑(+5)')
    
    if score == 0:
        details.append('无近端均线支撑(0)')
    
    return {'score': score, 'max': max_score, 'label': '均线支撑', 'details': details}


def score_pattern_match(detect_result: dict, params: dict = None) -> dict:
    """形态匹配 15分"""
    max_score = 15
    score = 0
    details = []
    
    hold = detect_result.get('hold_patterns', [])
    sell = detect_result.get('sell_signals', [])
    
    if sell:
        score = 0
        details.append(f'卖出信号触发 → 0分')
        return {'score': score, 'max': max_score, 'label': '形态匹配', 'details': details}
    
    if not hold:
        score = 0
        details.append('无持有形态命中 → 0分')
        return {'score': score, 'max': max_score, 'label': '形态匹配', 'details': details}
    
    # 取最强的持有形态
    best = max(hold, key=lambda h: h.get('score_base', 0))
    base = best.get('score_base', 8)
    # 映射到15分制：基础分8~17 → 8~15
    score = min(max_score, max(8, base - 2))
    details.append(f'{best["name"]}({best["tag"]}) 基础分{base} → 匹配{score}/{max_score}')
    
    return {'score': score, 'max': max_score, 'label': '形态匹配', 'details': details}


def score_buy_signals(detect_result: dict, vp_result: dict = None, params: dict = None) -> dict:
    """加仓信号评分 0-10分"""
    max_score = 10
    score = 0
    details = []
    
    buy = detect_result.get('buy_signals', [])
    sell = detect_result.get('sell_signals', [])
    
    # 卖出区间不加仓
    if sell:
        return {'score': 0, 'max': max_score, 'label': '加仓信号', 
                'details': ['卖出信号触发，不加仓'], 'buy_advice': None}
    
    if not buy:
        return {'score': 0, 'max': max_score, 'label': '加仓信号',
                'details': ['无加仓信号'], 'buy_advice': None}
    
    # VP背离 → 否决加仓
    if vp_result and vp_result.get('warning'):
        return {'score': 0, 'max': max_score, 'label': '加仓信号',
                'details': [f'VP背离预警({vp_result["warning"]})，否决加仓'], 'buy_advice': None}
    
    buy_count = len(buy)
    buy_names = [b['name'] for b in buy]
    
    has_b3 = any(b['name'] == 'B3整理突破' for b in buy)
    has_b2 = any(b['name'] == 'B2回踩确认' for b in buy)
    has_b1 = any(b['name'] == 'B1反包阳线' for b in buy)
    has_b4 = any(b['name'] == 'B4缩尽首阳' for b in buy)
    
    if has_b3 or buy_count >= 2:
        grade = 3
        score = 8
        grade_label = '强烈建议加仓'
    elif has_b2 or (has_b1 and vp_result and vp_result.get('score', 0) >= 60):
        grade = 2
        score = 5
        grade_label = '建议加仓'
    elif has_b1 or has_b4:
        grade = 1
        score = 3
        grade_label = '可轻仓试探'
    else:
        grade = 0
        grade_label = ''
        score = 0
    
    # VP共振加成
    if vp_result and vp_result.get('score', 0) >= 80:
        if grade < 3:
            grade += 1
        score += 2
        details.append(f'VP{vp_result["variant"]}{vp_result["label"]}>=80分 → 信号升级')
    elif vp_result and vp_result.get('score', 0) >= 60 and score > 0:
        score += 2
        details.append(f'VP{vp_result["variant"]}{vp_result["label"]}共振(+2)')
    
    stars = '⭐' * grade if grade > 0 else ''
    detail_line = f'{"+".join(buy_names)} {stars} {grade_label}'
    details.insert(0, detail_line)
    
    score = min(max_score, score)
    
    return {
        'score': score, 'max': max_score, 'label': '加仓信号',
        'details': details,
        'buy_advice': grade_label if grade_label else None,
        'buy_grade': grade,
    }


def compute_cost_factor(price: float, cost: float) -> dict:
    """持仓成本因子：根据盈亏幅度调整决策紧迫度（-8 ~ +8分）
    
    逻辑：
    - 大盈(≥30%) → +8：利润厚，可以等，不急着卖
    - 中盈(≥15%) → +5
    - 小盈(0-15%) → 0
    - 小亏(0~-10%) → -3：开始浮亏，要注意
    - 大亏(≤-10%) → -8：止损优先，果断卖出
    """
    if cost is None or cost <= 0 or price <= 0:
        return {'score': 0, 'max': 8, 'label': '持仓成本', 
                'details': ['无成本数据'], 'pnl_pct': None}
    
    pnl_pct = (price - cost) / cost * 100
    
    if pnl_pct >= 30:
        score = 8
        reason = f'大幅盈利{pnl_pct:+.1f}%，利润缓冲充裕(+8)'
    elif pnl_pct >= 15:
        score = 5
        reason = f'稳健盈利{pnl_pct:+.1f}%，可从容决策(+5)'
    elif pnl_pct >= 5:
        score = 2
        reason = f'小幅盈利{pnl_pct:+.1f}%，略有缓冲(+2)'
    elif pnl_pct >= -3:
        score = 0
        reason = f'盈亏平衡{pnl_pct:+.1f}%(0)'
    elif pnl_pct >= -10:
        score = -3
        reason = f'小幅浮亏{pnl_pct:+.1f}%，关注风险(-3)'
    else:
        score = -8
        reason = f'大幅亏损{pnl_pct:+.1f}%，止损优先级高(-8)'
    
    return {
        'score': score, 
        'max': 8, 
        'label': '持仓成本',
        'details': [reason],
        'pnl_pct': round(pnl_pct, 1),
    }


def calculate_score(kline: List[dict], detect_result: dict, 
                    vp_bonus: int = 0, vp_reason: str = '',
                    vp_result: dict = None,
                    cost: float = None, latest_price: float = None,
                    params: dict = None) -> dict:
    """
    计算完整的五维评分 + 量价共振加成 + 持仓成本因子
    
    参数:
        vp_bonus: 量价收敛共振加成 (-10 ~ +10)
        vp_reason: 加成理由
        cost: 持仓成本价
        latest_price: 最新价格（用于成本计算）
    
    返回:
    {
        'total': 82,
        'base_total': 80,     # 五维基础分
        'max_total': 100,
        'decision': 'hold' | 'reduce' | 'sell',
        'dimensions': [...],
        'vp_dim': {...},       # 量价共振维度
        'cost_dim': {...},     # 持仓成本维度
        'vp_reason': '...',
    }
    """
    p = params or {}
    
    dims = [
        score_trend_strength(kline, p, detect_result),
        score_volume_health(kline, p),
        score_exhaustion(kline, p, detect_result),
        score_ma_support(kline, p, detect_result),
        score_pattern_match(detect_result, p),
    ]
    
    base_total = sum(d['score'] for d in dims)
    
    # 加仓信号评分
    buy_dim = score_buy_signals(detect_result, vp_result, p)
    dims.append(buy_dim)
    
    # 持仓成本因子
    cost_dim = compute_cost_factor(latest_price or 0, cost or 0)
    
    total = base_total + vp_bonus + buy_dim['score'] + cost_dim['score']
    total = max(0, min(100, total))
    
    # 决策映射（基于总分）
    # M1康复场景放宽：M1活跃+衰竭信号满分 → 允许更低分持有
    hold_threshold = 75
    if detect_result:
        hold = detect_result.get('hold_patterns', [])
        has_m1 = any('M1' in h.get('name', '') or '底部启动' in h.get('name', '') for h in hold)
        exhaust_dim = [d for d in dims if d['label'] == '衰竭信号']
        exhaust_healthy = exhaust_dim and exhaust_dim[0]['score'] >= 23
        if has_m1 and exhaust_healthy:
            hold_threshold = 65  # M1底部康复场景放宽持有阈值
    
    if total >= hold_threshold:
        decision = 'hold'
    elif total >= 50:
        decision = 'reduce'
        # 加仓信号升级：动量≥60 + 加仓≥⭐⭐ → 升级为持有
        buy_grade = buy_dim.get('buy_grade', 0)
        if base_total >= 60 and buy_grade >= 2:
            decision = 'hold_buy'  # 持有（加仓信号驱动）
    else:
        decision = 'sell'
    
    # 量价共振维度
    vp_dim = {
        'score': max(0, vp_bonus + 5),  # 展示用，偏移到0-10
        'max': 10,
        'label': '量价共振',
        'details': [vp_reason] if vp_reason else ['无共振信号'],
        'raw_bonus': vp_bonus,
    }
    
    return {
        'total': total,
        'base_total': base_total,
        'max_total': 100,
        'decision': decision,
        'dimensions': dims,
        'vp_dim': vp_dim,
        'cost_dim': cost_dim,
        'vp_reason': vp_reason,
        'buy_advice': buy_dim.get('buy_advice'),
        'buy_grade': buy_dim.get('buy_grade', 0),
    }


def compute_trend_duration(kline: List[dict]) -> str:
    """计算趋势持续时间统计"""
    if not kline or len(kline) < 20:
        return ''
    
    closes = [k['close'] for k in kline]
    opens = [k['open'] for k in kline]
    highs = [k['high'] for k in kline]
    n = len(kline)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60) if n >= 60 else [0]
    
    # 连续站上MA20天数
    above_ma20_days = 0
    for i in range(n-1, -1, -1):
        if closes[i] > ma20[i]:
            above_ma20_days += 1
        else:
            break
    
    # 连续阳线天数
    bull_days = 0
    for i in range(n-1, -1, -1):
        if closes[i] > opens[i]:
            bull_days += 1
        else:
            break
    
    # 距20日高点天数
    peak_20 = max(highs[-20:])
    peak_20_idx = n - 1
    for i in range(n-1, n-21, -1):
        if highs[i] == peak_20:
            peak_20_idx = i
            break
    days_from_peak = n - 1 - peak_20_idx
    
    # 距60日高点天数
    peak_60_idx = n - 1
    if n >= 60:
        peak_60 = max(highs[-60:])
        for i in range(n-1, n-61, -1):
            if highs[i] == peak_60:
                peak_60_idx = i
                break
    
    parts = []
    if above_ma20_days >= 3:
        parts.append(f'MA20+{above_ma20_days}d')
    else:
        parts.append(f'BELOW MA20')
    
    if bull_days >= 2:
        parts.append(f'{bull_days}bull')
    
    if days_from_peak <= 3 and closes[-1] >= peak_20 * 0.98:
        parts.append(f'near peak')
    elif days_from_peak > 0:
        dd_pct = (closes[-1] - peak_20) / peak_20 * 100
        parts.append(f'peak{days_from_peak}d ago {dd_pct:+.1f}%')
    
    return ' | '.join(parts)


def format_score_output(score_result: dict, detect_result: dict, 
                         name: str = '', code: str = '',
                         cost: float = None, latest_price: float = None,
                         kline: List[dict] = None) -> str:
    """格式化评分为可打印文本"""
    lines = []
    
    # 头部
    lines.append("=== Momentum Position Advisor -- " + name + "(" + code + ") ===")
    
    # 价格行 + 趋势统计
    price_line = f"Price: {latest_price:.2f}" if latest_price else ""
    if cost and latest_price:
        pnl = (latest_price - cost) / cost * 100
        price_line += f" | Cost: {cost:.2f} | PnL: {pnl:+.1f}%"
    lines.append(price_line)
    
    # 趋势持续时间
    trend_stats = compute_trend_duration(kline)
    if trend_stats:
        lines.append(f"Trend: {trend_stats}")
    lines.append("")
    
    # 形态命中
    decision_tag = {'hold': 'HOLD', 'hold_buy': 'HOLD +BUY', 'reduce': 'REDUCE', 'sell': 'SELL'}
    primary = detect_result.get('primary', {})
    
    base = score_result.get('base_total', score_result['total'])
    vp_bonus_raw = score_result.get('vp_dim', {}).get('raw_bonus', 0)
    cost_bonus = score_result.get('cost_dim', {}).get('score', 0)
    
    bonus_parts = []
    if vp_bonus_raw != 0:
        bonus_parts.append(f"VP{'+' if vp_bonus_raw > 0 else ''}{vp_bonus_raw}")
    if cost_bonus != 0:
        bonus_parts.append(f"成本{'+' if cost_bonus > 0 else ''}{cost_bonus}")
    
    bonus_str = f"({' '.join(bonus_parts)})" if bonus_parts else ""
    if bonus_str:
        lines.append(f"Decision: {decision_tag.get(score_result['decision'], '?')}  {score_result['total']}/{score_result['max_total']}pts ({base}{bonus_str})")
    else:
        lines.append(f"Decision: {decision_tag.get(score_result['decision'], '?')}  {score_result['total']}/{score_result['max_total']}pts")
    lines.append("Primary: " + primary.get('name', 'None') + " " + primary.get('tag', ''))
    
    warnings = detect_result.get('warnings', [])
    if warnings:
        warn_names = ' | '.join(f"{w['tag']} {w['name']}" for w in warnings if w.get('hit'))
        lines.append("  WARN: " + warn_names)
    
    lines.append("")
    
    # 五维评分
    for dim in score_result['dimensions']:
        bar = _bar(dim['score'], dim['max'])
        lines.append(f"{dim['label']:<8} {bar} {dim['score']}/{dim['max']}")
        for d in dim.get('details', []):
            lines.append(f"  {d}")
    
    # 量价共振维度
    vp_dim = score_result.get('vp_dim')
    if vp_dim:
        bar = _bar(vp_dim['score'], vp_dim['max'])
        bonus_str = f"(+{vp_dim['raw_bonus']})" if vp_dim['raw_bonus'] > 0 else f"({vp_dim['raw_bonus']})" if vp_dim['raw_bonus'] < 0 else ""
        lines.append(f"{vp_dim['label']:<8} {bar} {vp_dim['score']}/{vp_dim['max']} {bonus_str}")
        for d in vp_dim.get('details', []):
            lines.append(f"  {d}")
    
    # 持仓成本维度
    cost_dim = score_result.get('cost_dim')
    if cost_dim and cost_dim.get('score', 0) != 0:
        bar = _bar(max(0, cost_dim['score'] + 8), 16)  # 偏移展示
        lines.append(f"{cost_dim['label']:<8} {bar} {cost_dim['score']:+.0f}/±8")
        for d in cost_dim.get('details', []):
            lines.append(f"  {d}")
    
    lines.append("")
    
    # 反弹博弈信号 🎲
    rebound = detect_result.get('rebound_signals', [])
    if rebound:
        risk_level = {'R1恐慌抛售反弹': '高确定性', 'R2缩量衰竭反弹': '中等概率', 'R3超跌均值回归': '纯统计'}
        lines.append("─── 🎲 反弹博弈信号 (高风险投机) ───")
        for r in rebound:
            quality = r.get('quality', 0)
            stars = '★★★' if quality >= 60 else '★★' if quality >= 40 else '★'
            risk = risk_level.get(r['name'], '未知')
            lines.append(f"  {r['tag']} {r['name']} {stars} 质量{quality}分 [{risk}]")
            lines.append(f"     {r['detail']}")
        lines.append("  ⚠️ 反弹博弈 ≠ 趋势反转，建议严格止损(入场价-5%)")
        lines.append("")
    
    # 决策建议
    if score_result['decision'] == 'sell':
        lines.append("Advice: SELL -- momentum exhaustion confirmed")
    elif score_result['decision'] == 'reduce':
        warn_names = ' | '.join(w.get('name', '') for w in warnings)
        lines.append("Advice: REDUCE -- " + warn_names)
    elif score_result['decision'] == 'hold_buy':
        buy_advice = score_result.get('buy_advice', '')
        stars = '⭐' * score_result.get('buy_grade', 0)
        lines.append(f"Advice: HOLD -- {stars} {buy_advice} (加仓信号驱动升级)")
    else:
        buy_advice = score_result.get('buy_advice')
        if buy_advice:
            stars = '⭐' * score_result.get('buy_grade', 0)
            lines.append(f"Advice: HOLD -- {stars} {buy_advice}")
        else:
            lines.append("Advice: HOLD -- " + primary.get('detail', 'momentum healthy'))
    
    lines.append("")
    
    return '\n'.join(lines)


def format_score_compact(score_result: dict, detect_result: dict,
                          name: str, code: str) -> str:
    """简洁单行输出"""
    decision_icons = {'hold': '[HOLD]', 'hold_buy': '[HOLD+BUY]', 'reduce': '[REDUCE]', 'sell': '[SELL]'}
    icon = decision_icons.get(score_result['decision'], '[?]')
    primary = detect_result.get('primary', {})
    warnings = detect_result.get('warnings', [])
    warn_str = ''
    if warnings:
        warn_names = [w['name'] for w in warnings if w.get('hit')]
        if warn_names:
            warn_str = f"  ⚠{'|'.join(warn_names)}"
    
    return f"  {icon} {name}({code})  {score_result['decision']}  {score_result['total']}分  {primary.get('name', '无形态')}{warn_str}"
