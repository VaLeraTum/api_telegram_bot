import logging
from logging.handlers import RotatingFileHandler
import os
import time
import sys
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIError
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('program.log', maxBytes=50000000, backupCount=5)
logger.addHandler(logging.StreamHandler())
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    }
    for token, value in tokens.items():
        if value is None:
            logger.critical(f'{token} не найден')
            sys.exit()


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение доставлено {message}')
    except telegram.TelegramError as error:
        logger.error(f'Сообщение не доставлено {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту сервиса."""
    payload = {'form_data': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception:
        raise APIError(
            f'API неправельный,'
            f'проверьте эндпоинт-{ENDPOINT},хэдер-{HEADERS} или дату-{payload}'
        )
    if response.status_code != HTTPStatus.OK:
        raise APIError(
            f'Эндпоинт не отвечает, статус ошибки: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверка API на соответсвие."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Неверный тип данных у объекта response, тип {type(response)}'
        )
    elif "homeworks" not in response:
        raise KeyError('В ответе homeworks отсутсвует')
    elif not isinstance(response["homeworks"], list):
        raise TypeError('Неверный тип данных у элемента homeworks')
    return response.get("homeworks")


def parse_status(homework):
    """Извлекает информацию о статусе домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status is None:
        raise KeyError('Пустой статус')
    if homework_name is None:
        raise KeyError('Нет имени работы')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус домашней работы неврен,пришёл статус:{status}')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Проверка токена')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message_error = ''
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                message = 'Отсутсвует домашняя работа'
            else:
                message = parse_status(homeworks[0])
            if last_message != message:
                send_message(bot, message)
                if send_message():
                    last_message = message
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_message_error != message:
                send_message(bot, message)
                if send_message():
                    last_message_error = message
            logger.exception(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
