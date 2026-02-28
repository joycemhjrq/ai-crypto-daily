import os
import requests
from datetime import datetime
import time
from openai import OpenAI
import openai

# -------------------------
# 配置
# -------------------------
SCT_KEY = os.getenv("SCT_KEY")
OPENAI_KEY = os.getenv("OPENAI_KEY")
ALPHA_KEY = os.getenv("ALPHA_KEY")
FRED_KEY = os.getenv("FRED_KEY")
NEWS_KEY = os.getenv("NEWS_KEY")

# -------------------------
# Step 1: 抓取加密货币价格
# -------------------------
def get_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,binancecoin,ethereum",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    resp = requests.get(url, params=params).json()
    btc = resp.get('bitcoin', {})
    bnb = resp.get('binancecoin', {})
    eth = resp.get('ethereum', {})
    return btc, bnb, eth

# -------------------------
# Step 2: 抓取股票收盘价（免费 symbol + 容错）
# -------------------------
def get_stock_indices():
    base = "https://www.alphavantage.co/query"
    symbols = {"IBM": "IBM", "MSFT": "MSFT"}  # 免费 symbol
    result = {}
    for name, symbol in symbols.items():
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": ALPHA_KEY
        }
        r = requests.get(base, params=params).json()
        print(symbol, r)
        if "Time Series (Daily)" not in r:
            print(f"Warning: {symbol} 数据无法获取，可能是免费接口限制")
            continue
        last_day = list(r['Time Series (Daily)'].keys())[0]
        close = r['Time Series (Daily)'][last_day]['4. close']
        result[name] = close
        time.sleep(15)  # 避免超频
    return result

# -------------------------
# Step 3: 抓取宏观数据
# -------------------------
def get_macro_data():
    treasury_url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={FRED_KEY}&file_type=json"
    treasury = requests.get(treasury_url).json()
    latest_treasury = treasury['observations'][-1]['value']

    dxy_url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DTWEXM&api_key={FRED_KEY}&file_type=json"
    dxy = requests.get(dxy_url).json()
    latest_dxy = dxy['observations'][-1]['value']

    return latest_treasury, latest_dxy

# -------------------------
# Step 4: 抓取新闻
# -------------------------
def get_news():
    url = "https://newsapi.org/v2/everything"
    today = datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "q": "AI OR OpenAI OR Anthropic OR DeepMind OR 'CZ Binance' OR 'He Yi' OR 'BNB'",
        "from": today,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 5,
        "apiKey": NEWS_KEY
    }
    r = requests.get(url, params=params).json()
    articles = []
    for item in r.get("articles", []):
        articles.append(f"- {item['title']} ({item['source']['name']})")
    return "\n".join(articles) if articles else "No major news today."

# -------------------------
# Step 5: 调用 OpenAI GPT-4o-mini 生成深度分析（兼容 v1+ SDK）
# -------------------------
def generate_analysis(btc, bnb, eth, stocks, treasury, dxy, news_text):
    try:
        client = OpenAI(api_key=OPENAI_KEY)
        system_prompt = (
            "你是专业宏观+AI+加密市场分析师。"
            "请生成一份深度日报，包含宏观、科技股、AI动态、BTC/BNB/ETH分析、市场情绪等。"
            "10-15分钟阅读量。"
        )
        user_prompt = (
            f"数据:\nBTC:{btc}\nBNB:{bnb}\nETH:{eth}\n"
            f"Stocks:{stocks}\n10Y Treasury:{treasury}\nDXY:{dxy}\nNews:{news_text}\n"
            "请生成深度分析日报，中文或英文均可。"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        return response.choices[0].message.content

    except (openai.RateLimitError, openai.OpenAIError, Exception) as e:
        print("⚠️ OpenAI 生成失败或 quota 超限:", e)
        # 返回基础行情 + 新闻作为备用日报
        report = (
            "⚠️ OpenAI quota 超限或出现错误，无法生成深度分析。\n\n"
            f"【加密货币行情】\nBTC: {btc}\nBNB: {bnb}\nETH: {eth}\n\n"
            f"【股票行情】\n{stocks}\n\n"
            f"【宏观指标】\n10Y Treasury: {treasury}\nDXY: {dxy}\n\n"
            f"【今日新闻】\n{news_text}"
        )
        return report

# -------------------------
# Step 6: 推送微信
# -------------------------
def send_wechat(title, content):
    url = f"https://sctapi.ftqq.com/{SCT_KEY}.send"
    payload = {"title": title, "desp": content}
    requests.post(url, data=payload)

# -------------------------
# Step 7: 主程序
# -------------------------
if __name__ == "__main__":
    btc, bnb, eth = get_crypto_prices()
    stocks = get_stock_indices()
    treasury, dxy = get_macro_data()
    news_text = get_news()

    report = generate_analysis(btc, bnb, eth, stocks, treasury, dxy, news_text)
    send_wechat("AI + Crypto 深度日报", report)
    print("日报推送完成 ✅")
