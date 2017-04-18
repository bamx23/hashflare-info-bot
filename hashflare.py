#!/usr/bin/env python

import sys
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import urllib

from math import ceil
from scipy.interpolate import UnivariateSpline
import matplotlib.pyplot as plt

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

def parse_quantity(quantity):
    subs = quantity.split()
    value = float(subs[0])
    factors = {'TH/s':10**12, 'GH/s': 10**9, 'MH/s': 10**6, 'KH/s': 10**3}
    value *= factors[subs[1]]
    return value

def format_quantity(quantity):
    factors = {10**12: 'TH/s', 10**9: 'GH/s', 10**6: 'MH/s', 10**3: 'KH/s'}
    for factor in reversed(sorted(factors)):
        if quantity >= factor:
            return str(quantity / factor) + ' ' + factors[factor]
    str(quantity) + ' H/s'

def parse_transactions(transactions):
    parsed = dict()
    for tr in transactions.tbody.find_all('tr'):
        tds = tr.find_all('td')
        transaction_id = tds[0].string
        product = tds[1].string.split(' ')[0]
        quantity = parse_quantity(tds[2].string)
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
    product = parse_text_variants(message, ['SHA-256', 'ETHASH', 'Scrypt', 'X11'])

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
        usd_string = rate['price_usd']
        if usd_string and len(usd_string) > 0:
            all_rates[rate['symbol']] = float(usd_string)
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

def extrapolateDaysLeft(xDay, plusUSD, investment):
    extrapolator = UnivariateSpline(xDay, plusUSD, k=1)
    x = [xDay[-1] + i + 1 for i in xrange(5 * 365)]
    y = extrapolator(x)
    predictedDaysLeft = None
    for i in xrange(len(x)):
        if y[i] >= investment:
            predictedDaysLeft = x[i]
            break
    return predictedDaysLeft

def getFuture(log, product='SHA-256'):
    xDay = []
    plusUSDPerHS = []
    minusUSD = []

    daysCount, delta, deltaPerHS, payment, power = 0, 0, 0, 0, 0
    lastTime = None
    for l in reversed(log):
        if not (l['data']['product'] == product):
            continue
        transaction = l['data']['transaction']
        if transaction:
            payment += transaction['total']
            power += transaction['quantity']
        dayDelta = l['usd']['delta']
        delta += dayDelta
        if power == 0:
            continue
        dayDeltaPerHS = dayDelta / power
        deltaPerHS += dayDeltaPerHS
        plusUSDPerHS += [1.0 * delta / power]
        minusUSD += [payment]
        if l['data']['type'] == 'payout':
            daysCount += 1
        xDay += [daysCount]
        lastTime = l['time']

    if daysCount == 0:
        return 0, 0, datetime(1970, 1, 1), 0, 0, payment, power, delta
    avgDayDelta = deltaPerHS / daysCount * power
    daysLeft = int(ceil((payment - delta) / avgDayDelta))
    fixDate = lastTime + timedelta(daysLeft)
    predictedDL = extrapolateDaysLeft(xDay, plusUSDPerHS, minusUSD[-1] / power)
    predictedFD = lastTime + timedelta(predictedDL)

    return avgDayDelta, daysLeft, fixDate, predictedDL, predictedFD, payment, power, delta

def printLogFuture(log, product='SHA-256'):
    avgDayDelta, daysLeft, fixDate, predictedDL, predictedFD, payment, power, profit = getFuture(log, product)
    print 'Future of', product
    print 'Investment:', '$' + str(payment)
    print 'Power:', format_quantity(power)
    print 'Profit:', '$' + str(profit)
    print 'Profit/day:', '$' + str(avgDayDelta)
    print 'Average:'
    print '\tDays left:', daysLeft
    print '\tFix date:', fixDate
    print 'Predicted:'
    print '\tDays left:', predictedDL
    print '\tFix date:', predictedFD

def dictX(d):
    return sorted(d.keys())

def dictY(d):
    return [d[i] for i in dictX(d)]

def plotLogInfo(log, product='SHA-256', fig_filename=None):
    productsPowF = { 'SHA-256': ('TH/s', 1e12), 'Scrypt': ('MH/s', 1e6), 'ETHASH': ('MH/s', 1e6), 'X11': ('MH/s', 1e6) }
    productPowName, productPowVal = productsPowF[product]
    payouts = dict()
    fees = dict()
    powers = dict()
    power = 0
    allTimes = []
    for l in reversed(log):
        if not (l['data']['product'] == product):
            continue
        if l['data']['type'] == 'payout':
            payouts[l['time']] = l['usd']['delta']
        elif l['data']['type'] == 'maintenance':
            fees[l['time']] = -l['usd']['delta']
        elif l['data']['type'] == 'purchased':
            power += l['data']['transaction']['quantity'] / productPowVal
        powers[l['time']] = power
        allTimes += [l['time']]

    fig1 = plt.figure()
    plt.title('Product: ' + product)

    ax1 = fig1.add_subplot(111)
    line1, = ax1.plot(dictX(payouts), dictY(payouts), 'o-', label='Payout')
    line2, = ax1.plot(dictX(fees), dictY(fees), 'xr-', label='Fee')

    xStart = min(allTimes)
    xMax = max(allTimes)
    allDays = int(ceil((xMax - xStart).total_seconds() / 3600.0 / 24.0))
    x = [xStart + timedelta(t) for t in xrange(allDays)]
    xLabels = [t for t in xrange(allDays)]
    plt.xticks(x, xLabels)
    ax1.set_ylim(bottom=0, top=(max(payouts.values()) * 1.1))
    plt.ylabel("Payout, USD")

    ax2 = fig1.add_subplot(111, sharex=ax1, frameon=False)
    line3, = ax2.plot(dictX(powers), dictY(powers), '.g-', label='Power')
    ax2.yaxis.tick_right()
    ax2.yaxis.set_label_position("right")
    ax2.set_ylim(bottom=0, top=(max(powers.values()) * 1.05))
    plt.ylabel("Investment, " + productPowName)

    plt.legend(handles=[line1, line2, line3], bbox_to_anchor=(0., -0.17, 1., .102), loc=0,
               ncol=3, mode="expand", borderaxespad=0.)

    if fig_filename:
        plt.savefig(fig_filename)

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
    print 'Info:'
    for product in ['SHA-256', 'Scrypt', 'ETHASH', 'X11']:
        printLogFuture(log, product)
        plotLogInfo(log, product, 'plot-' + product + '.png')

if __name__ == '__main__':
    main()
