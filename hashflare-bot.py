import hashflare
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import uuid, os

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start(bot, update):
    bot.sendMessage(update.message.chat_id, text='Type /help for more info.\nThis bot is open source.\nRepository: https://github.com/BamX/hashflare-info-bot')


def help(bot, update):
    bot.sendMessage(update.message.chat_id, text='Send me your "History" page saved as html file for some information about mining future.\nUse /currency to see currency rates.\nUse /repeat to see your future again.')


def echo(bot, update):
    bot.sendMessage(update.message.chat_id, text=update.message.text)


def parseAndShowFuture(bot, update):
    document = update.message.document
    if document['mime_type'] != 'text/html':
        bot.sendMessage(update.message.chat_id, text='Wrong file type(mime type not "text/html")')
        return
    if document['file_size'] > (1 << 20):
        bot.sendMessage(update.message.chat_id, text='File is too large(>1Mb)')
        return
    file_id = document['file_id']
    new_file = bot.getFile(file_id)
    filename = '/tmp/hashflare-history-%s.htm' % update.message.from_user.id
    new_file.download(filename)
    printLatest(bot, update)


def futureMessage(update, log, product):
    avgDayDelta, daysLeft, fixDate, payment, power = hashflare.getFuture(log, product)
    message = '%s, your future for %s:\nPayed: $%f\nPower: %s\nPer day: $%f\nDays left: %f\nFix date: %s' % \
        (update.message.from_user.first_name, product, \
            payment, hashflare.format_quantity(power), avgDayDelta, daysLeft, fixDate.isoformat())
    return message


def printLatest(bot, update):
    filename = '/tmp/hashflare-history-%s.htm' % update.message.from_user.id
    data = None
    with open(filename, 'r') as ff:
        data = ff.read()
    log = hashflare.parse(data)
    for product in ['SHA-256', 'Scrypt', 'ETHASH']:
        bot.sendMessage(update.message.chat_id, text=futureMessage(update, log, product))


def printBTCCurrency(bot, update):
    currency = hashflare.get_rates()
    target_currs = {'BTC', 'ETH'}
    rates = []
    for curr in currency:
        if curr in target_currs:
            rates += ['1 %s = %f USD' % (curr, currency[curr])]
    bot.sendMessage(update.message.chat_id, text='\n'.join(rates))


def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))
    bot.sendMessage(update.message.chat_id, text='Oops! Error: "%s"' % error)


def main():
    token = os.environ.get('TOKEN')

    if not token:
        return

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("currency", printBTCCurrency))
    dp.add_handler(CommandHandler("repeat", printLatest))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler([Filters.document], parseAndShowFuture))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
