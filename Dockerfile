FROM python:2.7-onbuild
ENV TOKEN="your bot token here"
CMD [ "python", "./hashflare-bot.py" ]
