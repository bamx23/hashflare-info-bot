FROM python:2.7-onbuild
COPY token.txt /usr/src/app/
CMD [ "python", "./hashflare-bot.py" ]
