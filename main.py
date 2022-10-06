import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from itertools import count
from time import sleep

import requests
from dotenv import load_dotenv
from terminaltables import AsciiTable

logger = logging.getLogger(__file__)
HEADERS = {'User-Agent': 'My User Agent 1.0'}
ID_VACANCY_DEVELOPER_HH = 1.221
ID_VACANCY_DEVELOPER_SJ = 48
ID_CITY_MOSCOW_HH = 1
ID_CITY_MOSCOW_CJ = 4


def predict_rub_salary_hh(vacancy):
    salary_from, salary_to = None, None
    if not vacancy.get('salary'):
        return salary_from, salary_to
    salary = vacancy.get('salary')
    if salary.get('currency') == 'RUR':
        salary_from = salary.get('from')
        salary_to = salary.get('to')
    return salary_from, salary_to


def predict_rub_salary_sj(vacancy):
    salary_from, salary_to = None, None
    if not vacancy.get('currency'):
        return salary_from, salary_to
    if vacancy.get('currency') == 'rub':
        salary_from = vacancy.get('payment_from')
        salary_to = vacancy.get('payment_to')
    return salary_from, salary_to


def predict_salary(salary_from, salary_to):
    salary = None
    if salary_from and salary_to:
        salary = salary_from + salary_to / 2
    elif salary_from:
        salary = salary_from * 1.2
    elif salary_to:
        salary = salary_to * 0.8
    return salary


def get_statistics_on_vacancies_from_hh(programming_languages):
    logger.info('get_vacancies_from_hh() was called')
    url = 'https://api.hh.ru/vacancies'
    vacancies_statistics = {}
    for language in programming_languages:
        vacancies_statistics[language] = {}
        processed_vacancies, all_wages, average_salary = 0, 0, 0
        pages = 0
        per_page = 100
        for page_number in count(pages):
            try:
                params = {'text': language, 'area': ID_CITY_MOSCOW_HH,
                          'specialization': ID_VACANCY_DEVELOPER_HH,
                          'only_with_salary': 'true', 'page': page_number,
                          'per_page': per_page}
                response = requests.get(url=url, params=params,
                                        headers=HEADERS, timeout=10)
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_er:
                logger.warning(f'Вакансии {language} на странице поиска - '
                               f'{page_number} не загружаются\n'
                               f'{http_er}\n')
                sys.stderr.write(f'{http_er}\n\n')
                continue
            except requests.exceptions.ConnectionError as connect_er:
                logger.warning(f'Сетевой сбой на вакансии {language}, '
                               f'страница {page_number}\n'
                               f'{connect_er}\n')
                sys.stderr.write(f'{connect_er}\n\n')
                sleep(15)
                continue
            json_response = response.json()
            total_vacancies = json_response.get('found')
            for vacancy in json_response.get('items'):
                salary_from, salary_to = predict_rub_salary_hh(vacancy)
                salary = predict_salary(salary_from, salary_to)
                if salary:
                    all_wages += salary
                    processed_vacancies += 1
            pages = json_response.get('pages')
            if page_number >= pages:
                break
        if processed_vacancies:
            average_salary = all_wages / processed_vacancies
        vacancies_statistics[language] = {
                            'vacancies_found': total_vacancies,
                            'vacancies_processed': processed_vacancies,
                            'average_salary': int(average_salary),
        }
    return vacancies_statistics


def get_statistics_on_vacancies_from_sj(programming_languages, api_key_sj):
    logger.info('get_vacancies_from_superjob() was called')
    url = 'https://api.superjob.ru/2.0/vacancies/'
    headers = {'X-Api-App-Id': api_key_sj}
    vacancies_statistics = {}
    for language in programming_languages:
        vacancies_statistics[language] = {}
        processed_vacancies, all_wages, average_salary = 0, 0, 0
        pages = 0
        per_page = 100
        for page_number in count(pages):
            try:
                params = {'keyword': language, 'town': ID_CITY_MOSCOW_CJ,
                          'id_vacancy': ID_VACANCY_DEVELOPER_SJ,
                          'count': per_page, 'page': page_number}
                response = requests.get(url=url, headers=headers,
                                        params=params)
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_er:
                logger.warning(f'Вакансии {language} на странице поиска - '
                               f'{page_number} не загружаются\n{http_er}\n')
                sys.stderr.write(f'{http_er}\n\n')
                continue
            except requests.exceptions.ConnectionError as connect_er:
                logger.warning(f'Сетевой сбой на вакансии {language}, '
                               f'страница {page_number}\n'
                               f'{connect_er}\n')
                sys.stderr.write(f'{connect_er}\n\n')
                sleep(15)
                continue
            json_response = response.json()
            total_vacancies = json_response.get('total')
            for vacancy in json_response.get('objects'):
                salary_from, salary_to = predict_rub_salary_sj(vacancy)
                salary = predict_salary(salary_from, salary_to)
                if salary:
                    all_wages += salary
                    processed_vacancies += 1
            pages = total_vacancies // per_page
            if page_number >= pages:
                break
        if processed_vacancies:
            average_salary = all_wages / processed_vacancies
        vacancies_statistics[language] = {
                            'vacancies_found': total_vacancies,
                            'vacancies_processed': processed_vacancies,
                            'average_salary': int(average_salary)
        }
    return vacancies_statistics


def create_output_table(vacancies_statistics, table_name):
    table_headers = ('Язык программирования', 'Вакансий найдено',
                     'Вакансий обработано', 'Средняя зарплата')
    table = [[] for _ in range(len(vacancies_statistics) + 1)]
    table[0] = table_headers
    for number, vacancy in enumerate(vacancies_statistics):
        table[number + 1].append(vacancy)
        table[number + 1].append(
            vacancies_statistics.get(vacancy).get('vacancies_found')
            )
        table[number + 1].append(
            vacancies_statistics.get(vacancy).get('vacancies_processed')
            )
        table[number + 1].append(
            vacancies_statistics.get(vacancy).get('average_salary')
            )
    output_table = AsciiTable(table, table_name)
    return output_table.table


def main():
    logging.basicConfig(filename='app.log', filemode='w', level=logging.INFO,
                        format='%(name)s - %(levelname)s '
                               '- %(asctime)s - %(message)s')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler('app.log', maxBytes=3000, backupCount=2)
    logger.addHandler(handler)
    load_dotenv()
    api_key_sj = os.getenv('API_KEY_SJ')
    programming_languages = ('Python', 'Java', 'Javascript', 'Ruby',
                             'C#', 'C++', 'Go', 'Scala', 'PHP', 'Kotlin')
    vacancies_statistics_hh = get_statistics_on_vacancies_from_hh(
        programming_languages)
    vacancies_statistics_sj = get_statistics_on_vacancies_from_sj(
        programming_languages, api_key_sj)
    collected_statistics = {'HeadHunter Moscow': vacancies_statistics_hh,
                            'SuperJob Moscow': vacancies_statistics_sj}
    output_tables = []
    for table_name, vacancies_statistics in collected_statistics.items():
        output_tables.append(create_output_table(
            vacancies_statistics, table_name))
    print(*output_tables, sep='\n\n')


if __name__ == '__main__':
    main()
