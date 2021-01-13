# 报道
"""
北极星电力网首页
"""
from lxml import etree
import time
import requests
from requests import RequestException
import urllib.error
import urllib.request
import os
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def search_url_13(url_main, filefolder):
    headers = {
        "user-agent": 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'}
    response = requests.get(url_main, headers=headers, verify=False)
    # 加一个判断，判断请求URL是否成功
    if response.status_code == 200:
        response.encoding = "GBK"
        soup = BeautifulSoup(response.text, 'lxml')

        list_title = soup.select('ul[class="list_left_ul"]>li')

        for j in list_title:
            try:
                temp_url = j.find("a").attrs["href"]
                code = get_one_page_13(temp_url, filefolder)
                if code == 404:
                    return 404
            except Exception:
                pass


def get_one_page_13(url, filefolder):
    try:
        # 需要重置requests的headers。
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.1 (KHTML, like Gecko) Chrome/13.0.782.41 Safari/535.1 QQBrowser/6.9.11079.201"}
        response = requests.get(url, headers=headers, verify=False)

        # 加一个判断，判断请求URL是否成功
        if response.status_code == 200:
            response.encoding = "GBK"
            soup = BeautifulSoup(response.text, 'lxml')
            write_txt(filefolder, get_biaoti_13(soup), get_key_list(soup), get_full_13(soup))
        elif response.status_code == 404:
            response.close()
            return 404
        response.close()
        return None
    except RequestException:
        response.close()
        return None


def get_key_list(soup):
    try:
        key = soup.select('div[class="list_key"]')[0].text
    # print(key)
    except Exception:
        key = ""
    return key


def get_biaoti_13(soup):
    s1 = soup.select('div[class="list_detail"]>h1')[0].text
    return s1


def get_full_13(soup):
    full_txt = ""
    zz = soup.find("div", attrs={"class": "list_detail"}).find_all("p")

    for i in zz:
        full_txt += i.text + "\n"
    return full_txt


def write_txt(filefolder, biaoti, key, full_text):
    biaoti = biaoti.strip()
    url_now = ""
    f = open(filefolder + "/" + biaoti + ".txt", "w+", encoding='utf-8')
    f.write(biaoti + "\n")
    f.write(key + "\n")
    f.write(full_text)
    f.close()


def mkdir(path):
    folder = os.path.exists(path)
    if not folder:  # 判断是否存在文件夹如果不存在则创建为文件夹
        os.makedirs(path)  # makedirs 创建文件时如果路径不存在会创建这个路径
        print("---  new folder...  ---  ", path)
    else:
        print("---  There is this folder!  ---  ", path)



if __name__ == '__main__':
    f1 = open("../url.txt", "r", encoding='utf-8')
    all_lines = f1.readlines()
    f1.close()

    f2 = open("../url_son_net.txt", "r", encoding='utf-8')
    son_lines = f2.readlines()
    f2.close()

    for son in son_lines:
        son_line = son.split()
        son_url = son_line[0]
        folder_1 = son_line[1]
        file_1 = '''../语料库2/''' + folder_1
        mkdir(file_1)  # 调用函数
        for i in all_lines:
            line = i.split()
            filefolder_2 = line[0]
            url_number = line[1]
            file_2 = file_1 + '''/''' + filefolder_2
            mkdir(file_2)  # 调用函数
            for k in tqdm(range(1,500)):
                url_k = "https://" + son_url + ".bjx.com.cn/NewsList?id=" + url_number + "&page=" + str(k)
                code = search_url_13(url_k, file_2)
                if code == 404:
                    break

