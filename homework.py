import logging
import os
import time
import sys

import requests
from http import HTTPStatus

import telegram
import telegram.ext

from dotenv import load_dotenv

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

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


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
    return all(tokens.values())


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение доставлено {message}')
    except telegram.TelegramError as error:
        logger.error(f'Сообщение не доставлено {error}')
    finally:
        logger.debug(f'Сообщение доставлено {message}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту сервиса."""
    payload = {'form_data': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        raise error('Ошибка API')
    if response.status_code != HTTPStatus.OK:
        logging.error('Код статуса не равен 200')
        raise TypeError
    return response.json()


def check_response(response):
    """Проверка API на соответсвие."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных')
    elif "homeworks" not in response:
        raise TypeError('В ответе homeworks отсутсвует')
    elif not isinstance(response["homeworks"], list):
        raise TypeError('Неверный тип данных у элемента homeworks')
    return response.get("homeworks")


def parse_status(homework):
    """Извлекает информацию о статусе домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status is None:
        raise TypeError('Пустой статус')
    if homework_name is None:
        raise TypeError('Нет имени работы')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Неверный статус')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Проверка токена')
    if not check_tokens():
        logger.critical('Токенов нет')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = ''
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
                last_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_error != error:
                send_message(bot, message)
                last_error = error
            logger.exception(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
