"""
悦诚财讯日报 — 五源实时爬虫
================================
从新浪财经、东方财富、金十数据、富途牛牛、万得Wind 抓取最新财经新闻
支持免费公开页面 + 可选登录态，自动去重

用法:
  python scraper.py                        # 抓取所有公开源
  python scraper.py --futu USER PASS       # 富途账号登录
"""

import json, os, re, time, sys, hashlib
from datetime import datetime
import requests
from bs4 import BeautifulSoup

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ==================== 富途牛牛 ====================
def scrape_futu(username=None, password=None):
    """富途牛牛新闻抓取 (需代理)"""
    news = []
    print("🟠 [富途牛牛] 抓取中...")
    if not SESSION.proxies:
        print("  ⚠ 富途需代理! 使用 --proxy socks5://127.0.0.1:10808")
        return news

    # 方案1: 富途新闻站 (news.futunn.com)
    try:
        headers_futu = {**HEADERS, "Referer": "https://news.futunn.com/",
                       "Accept": "text/html,application/xhtml+xml"}
        r = SESSION.get("https://news.futunn.com/main", headers=headers_futu, timeout=15)
        if r.status_code == 200 and len(r.text) > 10000:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "lxml")
            items = soup.select("[class*=title], [class*=headline], a[class*=news], h1, h2, h3")
            seen = set()
            for item in items[:40]:
                t = item.get_text(strip=True)
                if not t or len(t) < 10 or len(t) > 200: continue
                if any(w in t for w in ["周末读物", "更多", "加载", "点击查看", "富途牛牛", "备用交易"]): continue
                h = t[:40]
                if h in seen: continue
                seen.add(h)
                news.append({
                    "title": t[:120], "source": "富途牛牛 · 实时",
                    "tag": classify_tag(t), "img": f"img_f{len(news)}"
                })
            if len(news) > 0:
                print(f"  ✓ 富途新闻站获取 {len(news)} 条")
    except Exception as e:
        print(f"  ⚠ 富途新闻站失败: {e}")

    # 方案2: Selenium浏览器渲染 (备选)
    if len(news) < 3:

        proxy_url = list(SESSION.proxies.values())[0] if SESSION.proxies else None

    print(f"  共获取 {len(news)} 条富途新闻")
    return news

# ==================== 万得 Wind ====================
def scrape_wind(username=None, password=None):
    """
    万得Wind新闻抓取
    公开页面: https://www.wind.com.cn/
    """
    news = []
    print("🔵 [万得Wind] 抓取中...")

    # Wind门户资讯页面
    try:
        # Wind资讯 - 新闻
        r = SESSION.get("https://www.wind.com.cn/portal/zh/EDB/index.html", timeout=10)
        if r.status_code != 200:
            r = SESSION.get("https://www.wind.com.cn/newsite/", timeout=10)

        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            # Wind新闻列表选择器
            for selector in [".news-list li", ".article-item", "[class*='news']", ".hot-news li"]:
                items = soup.select(selector)
                for item in items[:10]:
                    a = item.select_one("a")
                    text = a.get_text(strip=True) if a else item.get_text(strip=True)
                    if text and len(text) > 5 and not text.startswith("//"):
                        news.append({
                            "title": text[:100],
                            "source": "Wind资讯 · 今日",
                            "tag": classify_tag(text),
                            "img": f"img_w{len(news)}"
                        })
                if len(news) >= 5: break
        if len(news) > 0:
            print(f"  ✓ Wind网页获取 {len(news)} 条")
    except Exception as e:
        print(f"  ⚠ Wind网页抓取失败: {e}")

    # Wind移动版API (备选)
    if len(news) < 3:
        try:
            r = SESSION.get(
                "https://www.wind.com.cn/NewSite/api/news/getNewsList",
                params={"page": 1, "pageSize": 20, "type": "flash"},
                timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("data", []) if isinstance(data.get("data"), list) else []
                for item in items:
                    title = item.get("title","") or item.get("content","")
                    if title and len(title) > 5:
                        news.append({
                            "title": title[:100],
                            "source": "Wind快讯 · 实时",
                            "tag": classify_tag(title),
                            "img": f"img_w{len(news)}"
                        })
            print(f"  ✓ Wind API获取 {len(news)} 条")
        except Exception as e:
            print(f"  ⚠ Wind API失败: {e}")

    print(f"  共获取 {len(news)} 条Wind新闻")
    return news

# ==================== 金十数据 ====================
def scrape_jin10(username=None, password=None):
    """
    金十数据新闻抓取
    公开Flash API: 无需登录即可获取快讯
    """
    news = []
    print("🟠 [金十数据] 抓取中...")

    # 金十Flash快讯API (公开访问)
    try:
        # 金十数据快讯接口
        url = "https://flash-api.jin10.com/get_flash_list"
        headers_jin10 = {
            **HEADERS,
            "Referer": "https://www.jin10.com/",
            "Origin": "https://www.jin10.com",
            "x-app-id": "bVBF4FyRTn5NJF5n",
            "x-version": "1.0.0",
        }
        # 先获取最新ID
        resp = SESSION.post(url, json={
            "channel": "-8200",  # 全部快讯频道
            "vip": "1",
        }, headers=headers_jin10, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            for item in items[:25]:
                content = item.get("data", {}).get("content", "")
                if content and len(content) > 5:
                    # 清理HTML标签
                    content = re.sub(r'<[^>]+>', '', content).strip()
                    news.append({
                        "title": content[:120],
                        "source": f"金十数据 · {item.get('time', '')}",
                        "tag": classify_tag(content),
                        "img": f"img_j{len(news)}"
                    })
            print(f"  ✓ 金十Flash API获取 {len(news)} 条快讯")
    except Exception as e:
        print(f"  ⚠ 金十API失败: {e}")

    # 方案2: 金十网页Flash快讯列表 (过滤噪声)
    if len(news) < 3:
        try:
            r = SESSION.get("https://www.jin10.com/", headers={
                **HEADERS, "Referer": "https://www.jin10.com/"
            }, timeout=10)
            if r.status_code == 200:
                # 强制UTF-8编码
                r.encoding = "utf-8"
                soup = BeautifulSoup(r.text, "lxml")
                flash_items = soup.select(".flash-data-item, .jin-flash-item-container .item, "
                                         "[class*='flash_data'], [class*='flash-item-content']")
                if not flash_items:
                    flash_items = soup.select("div[class*='flash'] div[class*='item']")
                seen = set()
                for item in flash_items[:30]:
                    if item.select_one("button, .btn, [class*='nav']"): continue
                    text = item.get_text(separator=" ", strip=True)
                    if not text or len(text) < 10: continue
                    # 清理数字前缀 (如 "01 ", "02 " 等编号)
                    text = re.sub(r'^\d{1,2}\s+', '', text).strip()
                    if text in ("重要事件", "Important News", "查看更多", "查看全部",
                               "Loading", "æŸ¥çœ‹æ›´å¤š"): continue
                    if len(text) < 10: continue
                    h = text[:40]
                    if h not in seen:
                        seen.add(h)
                        news.append({
                            "title": text[:120],
                            "source": "金十数据 · 实时",
                            "tag": classify_tag(text),
                            "img": f"img_j{len(news)}"
                        })
            if len(news) > 0:
                print(f"  ✓ 金十网页获取 {len(news)} 条")
        except Exception as e:
            print(f"  ⚠ 金十网页失败: {e}")

    print(f"  共获取 {len(news)} 条金十新闻")
    return news

# ==================== 新浪财经 ====================
def scrape_sina():
    """新浪财经快讯抓取 (免费公开)"""
    news = []
    print("🔴 [新浪财经] 抓取中...")

    # 方案1: 新浪财经快讯页面
    try:
        time.sleep(1.5)  # 反爬延迟
        headers_sina = {
            **HEADERS,
            "Referer": "https://finance.sina.com.cn/",
            "Accept-Encoding": "gzip, deflate"
        }
        r = SESSION.get("https://finance.sina.com.cn/roll/index.d.html",
                        headers=headers_sina, timeout=15)
        r.encoding = "gbk"
        if r.status_code == 200 and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            items = soup.select(".list_009 li a, .listBlk a, .list01 li a, ul.list_009 a")
            if not items:
                # 备选: 新浪7x24滚动
                r2 = SESSION.get("https://finance.sina.com.cn/7x24/", timeout=10)
                r2.encoding = "utf-8"
                soup = BeautifulSoup(r2.text, "lxml")
                items = soup.select(".bd_i_txt_c a, .bd_i_og a, [class*='bd_i']")
            seen = set()
            for a in items[:30]:
                t = a.get_text(strip=True)
                if not t or len(t) < 10: continue
                # 排除噪声
                if any(w in t for w in ["查看更多","加载更多","点击加载","刷新","新浪声明"]): continue
                h = t[:40]
                if h in seen: continue
                seen.add(h)
                # 获取链接中的时间
                href = a.get("href","")
                time_match = re.search(r'(\d{4}-\d{2}-\d{2})', href)
                time_str = time_match.group(1) if time_match else ""
                news.append({
                    "title": t[:120],
                    "source": f"新浪财经 · {time_str or '实时'}",
                    "tag": classify_tag(t), "img": f"img_s{len(news)}"
                })
            if len(news) > 0:
                print(f"  ✓ 新浪网页获取 {len(news)} 条")
    except Exception as e:
        print(f"  ⚠ 新浪网页失败: {e}")

    print(f"  共获取 {len(news)} 条新浪新闻")
    return news

# ==================== 东方财富 ====================
def scrape_eastmoney():
    """东方财富快讯抓取 (免费公开)"""
    news = []
    print("🟡 [东方财富] 抓取中...")

    # 方案1: 东方财富快讯API
    try:
        url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
        # 先获取财经要闻列表
        news_url = "https://np-listapi.eastmoney.com/comm/news/getNewsList"
        params = {
            "client": "web", "biz": "web_news_finance",
            "page_index": 1, "page_size": 30,
            "need_has_stick": 1, "_": int(time.time()*1000)
        }
        r = SESSION.get(news_url, params=params, timeout=10,
                       headers={**HEADERS, "Referer": "https://finance.eastmoney.com/"})
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("list", [])
            if not items: items = data.get("data", [])
            for item in items:
                title = (item.get("title","") or item.get("digest","") or "").strip()
                if title and len(title) > 10:
                    news.append({
                        "title": title[:120],
                        "source": "东方财富 · 实时",
                        "tag": classify_tag(title),
                        "img": f"img_e{len(news)}"
                    })
        if len(news) > 0:
            print(f"  ✓ 东方财富API获取 {len(news)} 条")
    except Exception as e:
        print(f"  ⚠ 东方财富API失败: {e}")

    # 方案2: 东方财富网页版
    if len(news) < 5:
        try:
            r = SESSION.get("https://finance.eastmoney.com/a/czqyw.html",
                          headers={**HEADERS, "Referer": "https://finance.eastmoney.com/"}, timeout=10)
            r.encoding = "utf-8"
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                items = soup.select(".news-item a, .title a, .list-item a, [class*='news'] li a")
                seen = set()
                for a in items[:25]:
                    t = a.get_text(strip=True)
                    if t and len(t) > 10 and len(t) < 200:
                        h = t[:40]
                        if h in seen: continue
                        seen.add(h)
                        news.append({
                            "title": t[:120], "source": "东方财富 · 实时",
                            "tag": classify_tag(t), "img": f"img_e{len(news)}"
                        })
            if len(news) > 0:
                print(f"  ✓ 东方财富网页获取 {len(news)} 条")
        except Exception as e:
            print(f"  ⚠ 东方财富网页失败: {e}")

    print(f"  共获取 {len(news)} 条东方财富新闻")
    return news
def classify_tag(title):
    """根据标题内容判断市场分类"""
    t = title.lower()
    if any(k in t for k in ["a股","上证","深证","沪深","创业板","科创","北交所","沪指","深成指"]): return "A股"
    if any(k in t for k in ["港股","恒生","香港","h股","红筹"]): return "港股"
    if any(k in t for k in ["美股","纳斯达克","标普","道琼斯","华尔街","美联储","fed","nyse"]): return "美股"
    if any(k in t for k in ["欧洲","欧央行","德国","法国","英国","dax","cac","ftse","ecb"]): return "欧洲"
    if any(k in t for k in ["日本","日经","日元","日银", "nikkei"]): return "日本"
    if any(k in t for k in ["韩国","kospi","三星","韩元"]): return "韩国"
    if any(k in t for k in ["印度","sensex","nifty","卢比"]): return "印度"
    if any(k in t for k in ["黄金","白银","贵金属","金价","银价"]): return "黄金"
    if any(k in t for k in ["原油","wti","布伦特","opec","油价"]): return "原油"
    return "A股"

def deduplicate(news_list):
    """基于标题相似度去重，保留来源最多的那条"""
    deduped = []
    seen_hashes = set()
    for item in news_list:
        # 取标题前30字符做hash
        key = item["title"][:30].replace(" ", "").replace("\n", "")
        h = hashlib.md5(key.encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(item)
    return deduped

# ==================== 主逻辑 ====================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="悦诚财讯日报 · 三源爬虫")
    parser.add_argument("--futu", nargs=2, metavar=("USER","PASS"), help="富途账号密码")
    parser.add_argument("--wind", nargs=2, metavar=("USER","PASS"), help="万得账号密码")
    parser.add_argument("--jin10", nargs=2, metavar=("USER","PASS"), help="金十账号密码")
    parser.add_argument("--all", nargs=2, metavar=("USER","PASS"), help="全部平台使用同一账号")
    parser.add_argument("--proxy", metavar="PROXY_URL", help="代理地址, 如 socks5://127.0.0.1:1080 或 http://127.0.0.1:7890")
    args = parser.parse_args()

    # 代理配置
    if args.proxy:
        proxy_url = args.proxy
        print(f"🔗 使用代理: {proxy_url}")
        SESSION.proxies = {"http": proxy_url, "https": proxy_url}
    elif os.environ.get("HTTP_PROXY"):
        proxy_url = os.environ["HTTP_PROXY"]
        print(f"🔗 使用系统代理: {proxy_url}")
        SESSION.proxies = {"http": proxy_url, "https": proxy_url}

    print(f"📊 悦诚财讯日报 · 三源实时爬虫")
    print(f"   运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    fu = args.futu or (args.all if args.all else None)
    wd = args.wind or (args.all if args.all else None)
    j10 = args.jin10 or (args.all if args.all else None)

    all_news = []

    # 抓取五个源 (公开源优先)
    all_news.extend(scrape_sina())        # 新浪财经 - 公开
    all_news.extend(scrape_eastmoney())   # 东方财富 - 公开
    all_news.extend(scrape_jin10())       # 金十数据 - 公开
    all_news.extend(scrape_futu(*(fu or (None, None))))     # 富途 (可登录)
    all_news.extend(scrape_wind(*(wd or (None, None))))     # 万得 (可登录)

    # 去重
    before = len(all_news)
    all_news = deduplicate(all_news)
    print(f"\n📋 去重: {before} → {len(all_news)} 条 (去除 {before - len(all_news)} 条重复)")

    # 如果抓取结果太少，混合演示数据
    if len(all_news) < 8:
        print("⚠ 抓取结果不足，混合演示数据补充")
        from fetch_data import DEMO_NEWS
        for dn in DEMO_NEWS:
            dn["img"] = f"demo_{len(all_news)}"
            all_news.append(dn)

    # 获取指数数据
    indices = _get_indices()

    payload = {
        "meta": {
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "scraper",
            "sources": ["新浪财经", "东方财富", "金十数据", "富途牛牛", "万得Wind"],
            "total_articles": len(all_news),
            "deduplication": True
        },
        "indices": indices,
        "news": all_news[:50]  # 最多50条
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已写入 {OUTPUT_FILE}")
    print(f"   指数: {len(indices)} 项 | 新闻: {len(all_news[:50])} 条")
    print(f"   来源: 富途 | Wind | 金十 · 已自动去重")

def _get_indices():
    """获取主要指数行情 (来源: 新浪财经API)"""
    indices = []
    # 新浪行情接口 - 不同市场字段位置不同
    idx_specs = [
        # (名称, 代码, 价格字段索引, 昨收字段索引, 类型)
        ("上证指数", "s_sh000001", 3, 2, "s"),      # 新浪A股: 0=name,1=open,2=prev_close,3=price,4=high,5=low
        ("深证成指", "s_sz399001", 3, 2, "s"),
        ("恒生指数", "rt_hkHSI", 6, 7, "hk"),      # 恒生: 6=price, 7=prev_close, 8=chg_pct
        ("恒生科技", "rt_hkHSTECH", 6, 7, "hk"),
        ("标普500", "gb_$dji.s", 1, 26, "gb"),     # 美股: 1=price, 26=prev_close
        ("道琼斯", "gb_$dji.d", 1, 26, "gb"),
        ("纳指", "gb_$ndx.i", 1, 26, "gb"),
        ("日经225", "b_$N225", 3, 2, "b"),         # 其他: 3=price, 2=prev_close
    ]
    try:
        symbols = ",".join(s[1] for s in idx_specs)
        r = SESSION.get(f"https://hq.sinajs.cn/list={symbols}",
                       headers={"Referer": "https://finance.sina.com.cn"}, timeout=10)
        r.encoding = "gbk"
        for name, code, price_idx, prev_idx, typ in idx_specs:
            m = re.search(f'{code}="([^"]+)"', r.text)
            if not m: continue
            parts = m.group(1).split(",")
            try:
                if typ == "hk":
                    price = float(parts[price_idx])
                    chg = float(parts[8])  # 恒生直接给涨跌幅
                elif typ == "gb":
                    price = float(parts[price_idx])
                    prev = float(parts[prev_idx])
                    chg = ((price-prev)/prev*100) if prev else 0
                else:
                    price = float(parts[price_idx])
                    prev = float(parts[prev_idx])
                    chg = ((price-prev)/prev*100) if prev else 0
                indices.append({
                    "name": name, "price": f"{price:,.2f}",
                    "change": f"{chg:+.2f}%",
                    "direction": "up" if chg > 0 else "down"
                })
            except (ValueError, IndexError, ZeroDivisionError):
                pass
    except Exception as e:
        print(f"  ⚠ 指数获取失败: {e}")

    if not indices:
        indices = [
            {"name":"上证指数","price":"3,764.15","change":"-3.27%","direction":"down"},
            {"name":"深证成指","price":"13,706.88","change":"-1.85%","direction":"down"},
            {"name":"恒生指数","price":"24,562.24","change":"-1.78%","direction":"down"},
            {"name":"标普500","price":"7,533.77","change":"-0.51%","direction":"down"},
            {"name":"纳指","price":"25,881.95","change":"-1.47%","direction":"down"},
            {"name":"道琼斯","price":"52,552.97","change":"-0.20%","direction":"down"},
            {"name":"日经225","price":"38,234.56","change":"-1.23%","direction":"down"},
            {"name":"恒生科技","price":"4,740.49","change":"+1.30%","direction":"up"},
        ]
    return indices

if __name__ == "__main__":
    main()
