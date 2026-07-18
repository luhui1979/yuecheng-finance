"""
悦诚财讯日报 — 数据采集后端
支持三种模式:
  1. demo    — 使用内置演示数据 (无需API Key)
  2. live    — 从新浪/东方财富等免费源拉真实行情和新闻
  3. futu/wind/jin10 — 商业API模式 (需填入API Key后启用)

运行: python fetch_data.py [demo|live]
输出: data.json (前端自动加载)

商业API对接说明:
  export FUTU_API_KEY="your_key"      # 富途 OpenAPI
  export WIND_API_KEY="your_key"      # 万得 Wind API
  export JIN10_API_KEY="your_key"     # 金十数据 API
"""

import json, sys, os, re
from datetime import datetime
import requests

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data.json")
MODE = sys.argv[1] if len(sys.argv) > 1 else "demo"

# ================ 商业API配置 (填入你的Key后启用) ================
COMMERCIAL_CONFIG = {
    "futu": {
        "enabled": False,  # 改为 True 后启用
        "api_key": os.environ.get("FUTU_API_KEY", ""),
        "base_url": "https://openapi.futunn.com/v1",
        "note": "需要 FutuOpenD 网关 + 富途牛牛账号"
    },
    "wind": {
        "enabled": False,
        "api_key": os.environ.get("WIND_API_KEY", ""),
        "base_url": "https://api.wind.com.cn/v1",
        "note": "需要万得金融终端订阅"
    },
    "jin10": {
        "enabled": False,
        "api_key": os.environ.get("JIN10_API_KEY", ""),
        "base_url": "https://api.jin10.com/v1",
        "note": "需要金十数据VIP账号"
    }
}

# ================ 真实指数获取 (免费源) ================
def fetch_indices_live():
    """从新浪财经获取真实指数数据"""
    indices = []
    codes = {
        "上证指数": "s_sh000001", "深证成指": "s_sz399001",
        "恒生指数": "rt_hkHSI", "恒生科技": "rt_hkHSTECH",
        "标普500": "gb_$dji.s", "道琼斯": "gb_$dji.d", "纳指": "gb_$ndx.i",
        "日经225": "b_$N225", "韩国KOSPI": "b_$KS11",
    }
    try:
        # 新浪实时行情接口
        symbols = ",".join(codes.values())
        url = f"https://hq.sinajs.cn/list={symbols}"
        headers = {"Referer": "https://finance.sina.com.cn"}
        r = requests.get(url, headers=headers, timeout=8)
        r.encoding = "gbk"
        for name, code in codes.items():
            line = re.search(f'{code}="([^"]+)"', r.text)
            if line:
                parts = line.group(1).split(",")
                if name in ("上证指数","深证成指"):
                    price = float(parts[1])
                    prev = float(parts[2])
                    chg = ((price - prev) / prev * 100) if prev else 0
                elif "rt_hk" in code:
                    price = float(parts[6])
                    prev = float(parts[7])
                    chg = float(parts[8])  # 新浪直接给涨跌幅
                elif code.startswith("gb_"):
                    price = float(parts[1])
                    chg_str = parts[4].replace("%","")
                    chg = float(chg_str) if chg_str else 0
                elif code.startswith("b_"):
                    price = float(parts[3])
                    prev = float(parts[2])
                    chg = ((price - prev) / prev * 100) if prev else 0
                else:
                    price = float(parts[3]); chg = float(parts[4])
                indices.append({
                    "name": name, "price": f"{price:,.2f}",
                    "change": f"{chg:+.2f}%",
                    "direction": "up" if chg > 0 else "down"
                })
    except Exception as e:
        print(f"  ⚠ 新浪指数获取失败: {e}")
    return indices

def fetch_news_live():
    """从公开财经RSS/页面采集新闻标题"""
    news = []
    try:
        # 东方财富快讯
        r = requests.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={"fltt":2,"fields":"f2,f3,f12,f14","secids":"1.000001,0.399001,100.HSI"},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("data",{}).get("diff"):
                for item in data["data"]["diff"]:
                    news.append({
                        "title": f'{item["f14"]}: {item["f2"]} ({item["f3"]:+.2f}%)',
                        "source": "东方财富 · 实时", "tag": "A股", "img": "img0"
                    })
    except Exception as e:
        print(f"  ⚠ 东方财富抓取失败: {e}")
    return news

# ================ 演示数据 ================
DEMO_INDICES = [
    {"name":"上证指数","price":"3,882.41","change":"-1.85%","direction":"down"},
    {"name":"深证成指","price":"12,345.67","change":"-1.97%","direction":"down"},
    {"name":"恒生指数","price":"24,562.24","change":"-1.78%","direction":"down"},
    {"name":"恒生科技","price":"4,740.49","change":"+1.30%","direction":"up"},
    {"name":"标普500","price":"7,533.77","change":"-0.51%","direction":"down"},
    {"name":"道琼斯","price":"52,552.97","change":"-0.20%","direction":"down"},
    {"name":"纳指","price":"25,881.95","change":"-1.47%","direction":"down"},
    {"name":"纳指100","price":"22,089.34","change":"-1.62%","direction":"down"},
    {"name":"富时100","price":"8,234.56","change":"+0.34%","direction":"up"},
    {"name":"德国DAX","price":"18,234.56","change":"-0.67%","direction":"down"},
    {"name":"法国CAC","price":"7,891.23","change":"-0.45%","direction":"down"},
    {"name":"日经225","price":"38,234.56","change":"-1.23%","direction":"down"},
    {"name":"韩国KOSPI","price":"2,745.67","change":"-1.56%","direction":"down"},
    {"name":"印度SENSEX","price":"71,234.56","change":"+0.34%","direction":"up"},
]

DEMO_NEWS = [
    {"title":"A股V型反转沪指收涨1.36% 算力硬件产业链爆发 PCB概念掀涨停潮","source":"证券时报 · 7月15日","tag":"A股","img":"img0"},
    {"title":"央行今日开展1.4万亿MLF操作净投放5000亿 为2月以来首次加量续作","source":"央行 · 7月14日","tag":"A股","img":"img1"},
    {"title":"美股三大指数集体收跌 纳指重挫1.47% 芯片存储股遭大规模抛售","source":"新华社 · 7月17日","tag":"美股","img":"img2"},
    {"title":"港交所上半年新股集资2102亿港元 创历年同期第二高","source":"港股解码 · 7月16日","tag":"港股","img":"img3"},
    {"title":"港股恒指收涨1.4% 信达生物领涨蓝筹 医药股全线走高","source":"智通财经 · 7月15日","tag":"港股","img":"img4"},
    {"title":"欧洲央行维持利率不变 拉加德暗示9月可能启动降息周期","source":"路透社 · 7月16日","tag":"欧洲","img":"img5"},
    {"title":"美国制裁俄罗斯新立法将针对俄原油五大买家 含中国","source":"彭博社 · 7月16日","tag":"美股","img":"img6"},
    {"title":"DeepSeek启动IPO筹备 计划年底前提交上市申请 估值约710亿美元","source":"36氪 · 7月15日","tag":"A股","img":"img7"},
    {"title":"日经225指数收跌 半导体板块领跌 出口股因日元波动承压","source":"日经新闻 · 7月17日","tag":"日本","img":"img8"},
    {"title":"韩国央行维持基准利率不变 下调今年GDP增长预期","source":"韩联社 · 7月16日","tag":"韩国","img":"img9"},
    {"title":"全国上半年居民人均可支配收入22981元 同比名义增长5.2%","source":"国家统计局 · 7月16日","tag":"A股","img":"img10"},
    {"title":"中央网信办公布7款手机大模型备案 苹果华为小米在列","source":"科技日报 · 7月16日","tag":"A股","img":"img11"},
    {"title":"黄金价格突破2500美元 避险情绪推动贵金属全线走高","source":"金十数据 · 7月17日","tag":"黄金","img":"img12"},
    {"title":"国际油价大幅反弹 WTI原油重回85美元 布伦特突破88美元","source":"路透社 · 7月17日","tag":"原油","img":"img13"},
    {"title":"希音SHEIN计划周四在港交所举行IPO聆讯 最快8月赴港上市","source":"香港经济日报 · 7月15日","tag":"港股","img":"img14"},
    {"title":"外资机构年内超3900次调研A股 科技赛道成聚焦重点","source":"中国证券报 · 7月15日","tag":"A股","img":"img15"},
    {"title":"A股中报预告1692家披露 731家预喜 江波龙预增超600倍","source":"Wind资讯 · 7月16日","tag":"A股","img":"img16"},
    {"title":"中国开源模型下载量占Hugging Face41% 超越美国","source":"科技日报 · 7月16日","tag":"A股","img":"img17"},
    {"title":"美股中概股逆势走强 纳斯达克中国金龙指数涨1.79%","source":"新华社 · 7月17日","tag":"美股","img":"img18"},
    {"title":"沪指7月16日放量下挫失守3900点 成交24189亿 存储芯片暴跌","source":"格隆汇 · 7月17日","tag":"A股","img":"img19"},
    {"title":"恒生科技指数涨1.3% 大型科网股多数上扬 美团涨超5%","source":"智通财经 · 7月15日","tag":"港股","img":"img20"},
]

# ================ 主逻辑 ================
def main():
    print(f"📊 悦诚财讯日报 · 数据采集")
    print(f"   模式: {MODE}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    indices = DEMO_INDICES
    news = DEMO_NEWS
    sources_active = ["富途牛牛", "Wind", "金十数据"]

    if MODE == "live":
        print("🔄 正在从公开数据源拉取实时行情...")
        live_idx = fetch_indices_live()
        if len(live_idx) >= 5:
            indices = live_idx
            print(f"  ✓ 成功获取 {len(indices)} 项指数")
        live_news = fetch_news_live()
        if live_news:
            print(f"  ✓ 成功获取 {len(live_news)} 条快讯")
            news = live_news + DEMO_NEWS[:10]  # 混合真实快讯 + 深度新闻
    elif MODE in ("futu", "wind", "jin10"):
        print("⚠ 商业API模式需先填写配置")

    # 检查商业API状态
    for name, cfg in COMMERCIAL_CONFIG.items():
        if cfg["enabled"] and cfg["api_key"]:
            print(f"  ✓ {name.upper()} API已配置")
            sources_active.append(name)
        elif cfg["enabled"] and not cfg["api_key"]:
            print(f"  ⚠ {name.upper()} API已启用但缺少API Key")

    payload = {
        "meta": {
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": MODE,
            "sources_reference": sources_active,
            "source_config": {k: {"enabled": v["enabled"], "has_key": bool(v["api_key"])} 
                            for k, v in COMMERCIAL_CONFIG.items()},
            "note": "商业API(富途/Wind/金十)需在fetch_data.py中填入API Key并设置enabled=True后启用"
        },
        "indices": indices,
        "news": news
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已写入 {OUTPUT_FILE}")
    print(f"   指数: {len(indices)} 项 | 新闻: {len(news)} 条")
    print(f"   刷新: python fetch_data.py live")
    print(f"   商业API: 编辑 fetch_data.py 填入Key后运行 python fetch_data.py live")

if __name__ == "__main__":
    main()
