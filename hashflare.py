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

        usd = {'delta': currency * delta, 'balance': currency * balance}

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

def get_currency():
    url = "https://blockchain.info/ru/ticker"
    response = urllib.urlopen(url)
    data = json.loads(response.read())
    return float(data['USD']['last'])

def parse(html):
    soup = BeautifulSoup(html, 'html.parser')

    tables = soup.find_all('table')
    if len(tables) < 4:
        print 'Wrong data'
        exit(1)

    currency = get_currency()
    contracts = tables[0]
    recvs = tables[2]
    log = parse_log(tables[3], parse_transactions(tables[1]), currency)

    return log

def getFuture(log):
    plusUSD = []
    minusUSD = []

    xTime = []

    delta = 0
    payment = 0
    for l in reversed(log):
        if not (l['data']['product'] in ['SHA-256', 'Scrypt']):
            continue
        transaction = l['data']['transaction']
        if transaction:
            payment += transaction['total']
        delta += l['usd']['delta']
        time = l['time']
        plusUSD += [delta]
        minusUSD += [payment]
        xTime += [time]

    timeDelta = xTime[-1] - xTime[0]
    avgDayDelta = delta / timeDelta.days
    daysLeft = payment / avgDayDelta
    fixDate = xTime[0] + timedelta(daysLeft)

    return avgDayDelta, daysLeft, fixDate

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
    avgDayDelta, daysLeft, fixDate = hashflare.getFuture(data)
    print 'Per day: ', avgDayDelta
    print 'Days left: ', daysLeft
    print 'Fix date: ', fixDate

if __name__ == '__main__':
    main()
