import hashflare
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import uuid, os

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def start(bot, update):
    bot.sendMessage(update.message.chat_id, text='Type /help for more info.\nMore info: https://github.com/BamX/hashflare-info-bot')


def help(bot, update):
    bot.sendMessage(update.message.chat_id, text='Send me your "History" page saved as html file for some information about SHA-256 mining future.')


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
    temp_filename = '/tmp/' + str(uuid.uuid1())
    new_file.download(temp_filename)
    data = None
    with open(temp_filename, 'r') as ff:
        data = ff.read()
    os.remove(temp_filename)
    log = hashflare.parse(data)
    avgDayDelta, daysLeft, fixDate = hashflare.getFuture(log)
    message = 'Your future for SHA-256:\nPer day: $%f\nDays left: %f\nFix date: %s' % (avgDayDelta, daysLeft, fixDate.isoformat())
    bot.sendMessage(update.message.chat_id, text=message)

def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))
    bot.sendMessage(update.message.chat_id, text='Oops! Error: "%s"' % error)

def main():
    token = None
    with open('token.txt', 'r') as tokenfile:
        token = tokenfile.read().strip()

    if not token:
        return

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

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
