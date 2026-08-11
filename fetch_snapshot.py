import json, urllib.request, datetime

def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req, timeout=25))

snap = {'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'crypto': {}, 'sentiment': {}, 'equities': {}, 'fx': {}, 'notes': []}

# Crypto top caps
try:
    m = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=15&page=1&price_change_percentage=24h,7d,30d")
    for c in m:
        snap['crypto'][c['symbol'].upper()] = {
            'price': c['current_price'], 'mcap': c['market_cap'],
            'chg24h': c.get('price_change_percentage_24h'),
            'chg7d': c.get('price_change_percentage_7d_in_currency'),
            'chg30d': c.get('price_change_percentage_30d_in_currency')}
except Exception as e:
    snap['notes'].append('crypto markets failed: ' + str(e))

# BTC + ETH detail
for sym in ('bitcoin', 'ethereum'):
    try:
        d = get("https://api.coingecko.com/api/v3/coins/%s?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false" % sym)['market_data']
        key = sym.upper()
        base = snap['crypto'].get(key, {})
        base.update({'high24h': d['high_24h']['usd'], 'low24h': d['low_24h']['usd'],
                     'ath': d['ath']['usd'], 'ath_chg': d['ath_change_percentage']['usd'],
                     'chg24h': d['price_change_percentage_24h'],
                     'chg7d': d['price_change_percentage_7d'],
                     'chg30d': d['price_change_percentage_30d']})
        snap['crypto'][key] = base
    except Exception as e:
        snap['notes'].append(sym + ' detail failed: ' + str(e))

# Fear & Greed
try:
    f = get("https://api.alternative.me/fng/?limit=1")['data'][0]
    snap['sentiment'] = {'fng_value': int(f['value']), 'fng_class': f['value_classification']}
except Exception as e:
    snap['notes'].append('FNG failed: ' + str(e))

# Equities attempt (Stooq)
try:
    u = "https://stooq.com/q/l/?s=spx.us&f=sd2t2ohlcv&h&e=csv"
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
    snap['equities']['raw'] = urllib.request.urlopen(req, timeout=15).read().decode()
except Exception as e:
    snap['notes'].append('equities (stooq) unavailable: ' + str(e))

json.dump(snap, open('market_snapshot.json', 'w'), indent=2)
print("WROTE market_snapshot.json")
print("crypto:", list(snap['crypto'].keys()))
print("sentiment:", snap['sentiment'])
print("notes:", snap['notes'])
