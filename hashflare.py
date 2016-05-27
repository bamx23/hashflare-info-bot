#!/usr/bin/env python

import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import urllib

def json_serial(obj):
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

def parse_text_variants(text, variants):
    for v in variants:
        if v in text:
            return v
    return None

def parse_transactions(transactions):
    parsed = dict()
    for tr in transactions.tbody.find_all('tr'):
        tds = tr.find_all('td')
        transaction_id = tds[0].string
        product = tds[1].string.split(' ')[0]
        quantity = tds[2].string
        total = float(tds[3].string.split(' ')[0])
        method = tds[4].string
        time = datetime.strptime(tds[5].string, '%d.%m.%y %H:%M')
        status = tds[6].string
        parsed[transaction_id] = {
            'product': product,
            'quantity': quantity,
            'total': total,
            'method': method,
            'time': time,
            'status': status
        }
    return parsed

def parse_log_message(message, transactions):
    message_type = parse_text_variants(message.lower(), ['maintenance', 'payout', 'allocation', 'purchased'])
    product = parse_text_variants(message, ['SHA-256', 'ETHASH', 'Scrypt'])

    transaction = None
    if message_type == 'purchased':
        transaction_id = message.strip().split('#')[1]
        transaction = transactions[transaction_id]

    currency = None
    if message_type in ['payout', 'maintenance']:
        currency = message.strip().split('(')[1].split(')')[0]
    return { 'type': message_type, 'product': product, 'transaction': transaction, 'currency': currency }

def parse_log(log, transactions, currency):
    parsed = []
    for tr in log.tbody.find_all('tr'):
        tds = tr.find_all('td')
        message = tds[0].string
        data = parse_log_message(message, transactions)
        time = datetime.strptime(tds[1].string, '%d.%m.%y %H:%M')

        delta = float(tds[2].string)
        balance = float(tds[3].string)
        if tds[2].span and ('text-danger' in tds[2].span['class']):
            delta = -delta

        curr_rate = 1
        if data['currency']:
            curr_rate = currency[data['currency']]
        usd = {'delta': curr_rate * delta, 'balance': curr_rate * balance}

        if not data['type']:
            continue

        parsed += [{
            'message': message,
            'time': time,
            'delta': delta,
            'balance': balance,
            'data': data,
            'usd': usd
        }]
    return sorted(parsed, key=lambda x: x['time'], reverse=True)

def get_rates():
    all_rates = dict()
    url = "https://api.coinmarketcap.com/v1/ticker/"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    for rate in data:
        all_rates[rate['symbol']] = float(rate['price_usd'])
    return all_rates

def parse(html):
    soup = BeautifulSoup(html, 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 4:
        print 'Wrong data'
        exit(1)

    currency = get_rates()
    contracts = tables[0]
    recvs = tables[2]
    log = parse_log(tables[3], parse_transactions(tables[1]), currency)
    return log

def getFuture(log, product='SHA-256'):
    plusUSD = []
    minusUSD = []

    daysCount = 0
    delta = 0
    payment = 0
    lastTime = None
    for l in reversed(log):
        if not (l['data']['product'] == product):
            continue
        transaction = l['data']['transaction']
        if transaction:
            payment += transaction['total']
        dayDelta = l['usd']['delta']
        delta += dayDelta
        plusUSD += [delta]
        minusUSD += [payment]
        lastTime = l['time']
        if dayDelta > 0:
            daysCount += 1

    if daysCount == 0:
        return 0, 0, datetime(1970, 1, 1)
    print daysCount
    avgDayDelta = delta / daysCount
    daysLeft = (payment - delta) / avgDayDelta
    fixDate = lastTime + timedelta(daysLeft)

    return avgDayDelta, daysLeft, fixDate

def printLogFuture(log, product='SHA-256'):
    avgDayDelta, daysLeft, fixDate = getFuture(log, product)
    print 'Future of', product
    print 'Per day:', '$' + str(avgDayDelta)
    print 'Days left:', daysLeft
    print 'Fix date:', fixDate

def main():
    filename = None
    if len(sys.argv) >= 2:
        filename = sys.argv[1].strip()

    data = None
    if filename == '-':
        data = sys.stdin.read()
    else:
        with open(filename, 'r') as htmldata:
            data = htmldata.read()
    log = parse(data)
    #print json.dumps(log, default=json_serial)
    for product in ['SHA-256', 'Scrypt', 'ETHASH']:
        printLogFuture(log, product)

if __name__ == '__main__':
    main()
