from datetime import datetime as dt, timedelta
from typing import List
import collections
import logging
import re

import config

from aiogram import Bot, Dispatcher, executor, types
import matplotlib.pyplot as plt
import aiohttp

logging.basicConfig(level=logging.INFO)

TOKEN = config.BOT_TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

RESULT_DICT = {}


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message) -> None:
    await message.reply(
        "Hi! You can use this commands to get rates:\n"
        "/list or /lst - returns list of all available rates\n"
        "/exchange $10 to CAD or  /exchange 10 USD to CAD\n"
        "/history USD/CAD for 7 days\n"
    )


@dp.message_handler(commands=['list', 'lst'])
async def rates_list(message: types.Message) -> None:
    global RESULT_DICT

    await check_rates_dict()

    result_str = get_rates_str(RESULT_DICT['rates'])
    await message.reply(result_str)


@dp.message_handler(commands=['exchange'])
async def exchange(message: types.Message) -> None:
    global RESULT_DICT
    await check_rates_dict()

    msg = re.split(' to ', message.text.replace('/exchange', ''))
    res = get_values_from_request(msg)

    await message.reply(res)


@dp.message_handler(commands=['history'])
async def history(message: types.Message) -> None:
    """
    /history USD/CAD for 7 days - return an image graph chart which shows the exchange rate graph/chart of the
    selected currency for the last 7 days. Here it is not necessary to save anything in the local database, you should
    request every time the currency data for the last 7 days.
    """
    msg = re.split('/', message.text.replace('/history', ''))
    if len(msg) != 2:
        await message.reply("Please, check your request!")
        return

    first_currency, second_currency = get_currencies(msg)
    if not first_currency and not second_currency:
        await message.reply("Please, check your request!")
        return

    now = dt.now().date()
    week_ago = now - timedelta(days=7)
    url = f'https://api.exchangeratesapi.io/history?start_at={week_ago}&end_at={now}&base={first_currency}&symbols={second_currency}'

    try:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            async with session.get(url) as response:
                r = await response.json()

            x, y = [], []
            ordered_rates_dict = collections.OrderedDict(sorted(r['rates'].items()))
            for date, value in ordered_rates_dict.items():
                x.append(date)
                y.append(value[second_currency])
            plt.plot(x, y)

            plt_name = f'{first_currency}-{second_currency}-{now}.png'
            plt.savefig(plt_name)

        with open(plt_name, 'rb') as rates:
            await message.reply_photo(rates, caption=f'Rates {first_currency}/{second_currency}')

    except aiohttp.ClientResponseError:
        await message.reply("No exchange rate data is available for the selected currency.")
        return


async def check_rates_dict():
    if RESULT_DICT.get('timestamp'):
        if dt.now() - dt.fromtimestamp(RESULT_DICT['timestamp']) < timedelta(minutes=10):
            pass
    else:
        async with aiohttp.ClientSession(raise_for_status=True) as session:
            url = 'https://api.exchangeratesapi.io/latest?base=USD'
            async with session.get(url) as response:
                r = await response.json()
                RESULT_DICT['rates'] = r.get('rates')
                RESULT_DICT['timestamp'] = dt.now().timestamp()


def get_rates_str(rates: dict) -> str:
    result_str = ''
    for cur, val in rates.items():
        result_str += f"{cur}: {round(val, 2)}\n"
    return result_str


def get_values_from_request(msg: List[str]) -> str:
    if len(msg) != 2:
        return "Please, check your request!"

    first_currency, second_currency = get_currencies(msg)

    amount_r = re.search(r"\d+", msg[0])
    amount = float(amount_r.group()) if amount_r else None

    if not first_currency and second_currency and amount:
        return "Please, check your request!"

    if first_currency.upper() != 'USD' and first_currency != '$':
        return "Please, check your request! Work only with USD as first currency"

    rate = RESULT_DICT['rates'].get(second_currency.upper())
    if not rate:
        return f"Please, check your request! Can't understand second currency"

    return f"${round(rate * amount, 2)}"


def get_currencies(msg: List[str]) -> (str, str):
    first_currency, second_currency = '', ''

    first = re.search(r"[a-zA-Z]{3}\b|\$", msg[0])
    if first: first_currency = first.group()

    second = re.search(r"\b[a-zA-Z]{3}\b", msg[1])
    if second: second_currency = second.group()

    if not first_currency and second_currency:
        return "", ""

    return first_currency, second_currency


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
