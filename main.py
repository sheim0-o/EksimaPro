from fastapi import FastAPI, Query
from bs4 import BeautifulSoup
import requests
import re
import pandas as pd
import datetime
import os
from dotenv import load_dotenv
import click

load_dotenv()
DEF_URL = os.getenv('URL') or 'https://rostender.info' 
DEF_MAX = int(os.getenv('MAX_DATA_LEN')) if os.getenv('MAX_DATA_LEN') else 5
DEF_START_PAGE = int(os.getenv('START_PAGE')) if os.getenv('START_PAGE') else 1
DEF_LAST_PAGE = int(os.getenv('LAST_PAGE')) if os.getenv('LAST_PAGE') else 50
searched_data = {
    'Начальная цена': 'price',
    'Окончание (МСК)': 'end_date',
    'Обеспечение заявки': 'securing_the_application',
    'Отрасли': 'branches'
}


app = FastAPI()

@app.get('/')
def read_root():
    return {'message': 'test'}

@app.get('/endpoint/tenders')
def give_tenders(max: int = Query(DEF_MAX, description="Maximum tenders to return")):
    return get_tenders(max)



def read_detail_page(detail_page_url):
    data = {}

    response = requests.get(detail_page_url)
    bs = BeautifulSoup(response.text,'html.parser')

    name = bs.find(class_='tender-header__title').find('h1').text
    name_search = re.search(r'Тендер: (.*)', name.strip())
    if name_search:
        data['name'] = name_search.group(1)
    else:
        data['name'] = ''

    detail_info_cols = bs.find_all(class_='tender-body__col')
    for detail_info_col in detail_info_cols:
        branches_tag = searched_data.get('Отрасли')
        if 'tender-body__col--full' in detail_info_col['class'] and 'last' in detail_info_col['class'] and branches_tag:
            detail_info_blocks = detail_info_col.find_all(class_='tender-body__block')
            for detail_info_block in detail_info_blocks:
                list_of_branches = detail_info_block.find('ul')
                if list_of_branches:
                    data[branches_tag] = []
                    for branch in list_of_branches.find_all('a'):
                        data[branches_tag].append({
                            'link': branch['href'],
                            'name': branch['title']
                        })
        else:
            detail_info_blocks = detail_info_col.find_all(class_='tender-body__block')
            for detail_info_block in detail_info_blocks:
                detail_info_block_title = detail_info_block.find(class_='tender-body__label')
                if detail_info_block_title:
                    di_tag = searched_data.get(detail_info_block_title.text)
                    if di_tag:
                        di_field = detail_info_block.find(class_="tender-body__field")
                        di_field_value = ''

                        if(di_field.text != None):
                            di_field_value = di_field.text
                        else:
                            di_field_value = di_field.select_one('span')

                        match di_tag:
                            case 'price':
                                di_field_value = di_field_value.strip().replace('-', '')
                            case 'end_date':
                                di_field_value = di_field_value.strip().replace('\xa0', ' ')
                        
                        data[di_tag] = di_field_value




    return data

def read_page(page_url, max_elements):
    response = requests.get(page_url)
    bs = BeautifulSoup(response.text,'html.parser')
    
    data = []

    list_of_tenders_block = bs.find(id='table-constructor-body')
    list_of_tenders = list_of_tenders_block.find_all(class_='tender-row')

    count_of_received_tenders = min(max_elements, len(list_of_tenders))
    received_tenders = list_of_tenders[:count_of_received_tenders]

    for received_tender in received_tenders:
        tender_data = {}
        tender_number = received_tender.find(class_='tender__number').text

        id_search = re.search(r'№\d*', tender_number)
        if id_search:
            tender_data['id'] = id_search.group(0).replace('№', '')
        else:
            tender_data['id'] = ''

        tender_link = received_tender.find(class_='tender-info__link')['href']
        tender_data['link'] = tender_link

        tender_data.update(read_detail_page(DEF_URL + tender_link))
        data.append(tender_data)

    return data


def get_tenders(max):
    result_data = []
    current_page=DEF_START_PAGE

    while len(result_data) < max:
        if current_page >= DEF_LAST_PAGE:
            break

        result_data_from_page = read_page(DEF_URL+'/extsearch?page='+str(DEF_START_PAGE), max - len(result_data))
        result_data.extend(result_data_from_page)

        current_page = current_page + 1
    return result_data

@click.command()
@click.option('--max', default=DEF_MAX)
@click.option('--output', default='')
def main(max, output):
    result_data = get_tenders(max)
    df = pd.DataFrame(result_data)
    csv_path = './output/{date:%Y-%m-%d_%H-%M-%S}.csv'.format(date=datetime.datetime.now()) if output == '' else  './output/{name}.csv'.format(name=output)
    df.to_csv(csv_path, index=False)

if __name__ == '__main__':
    main()