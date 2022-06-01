# Trading Bot
Cryptocurrency trading bot that allows users to create strategies and then backtest, optimize, simulate, or run live bots using them. Telegram integration has been added to support easier and remote trading.

# Features
- [x] Create strategies
- [x] Run live bots
- [x] Telegram integration

# Prerequisites
The following variables needs to be set in your environment:
```sh
ENV=''
BINANCE_KEY=''
BINANCE_SECRET=''
TELEGRAM_CHANNEL=''
TELEGRAM_BOT=''
```
The `ENV` variable could be 'production' or 'development' and you will get your own credentials from [Binance](https://www.binance.com/en/signup) and [Telegram](https://telegram.org/).

# Installation with docker
1. Clone the repository
```bash
git clone git@github.com:JehuSilva/trading-bot.git
```
2. Create the docker image
```bash
docker build -t backtrader .
```
3. Run the application in the background
```bash
docker run -d --name backtrader-bot --env-file .env backtrader:latest
```
4. Run this command in order to see the logs
```bash
docker logs -f backtrader-bot
```





