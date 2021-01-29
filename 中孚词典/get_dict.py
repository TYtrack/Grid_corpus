'''
https://search.qinggl.com/dict-5993.html
'''
from lxml import etree
import time
import requests
from requests import RequestException
import urllib.error
import urllib.request
import os
from bs4 import BeautifulSoup 

def search_url(url_main):
    f1=open("C:/Users/HUST/Desktop/中孚项目/词典构建/dict_from_net.txt","w+")
    word_list=[]
    headers = {
            "user-agent": 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'}
    response = requests.get(url_main, headers=headers)
        # 加一个判断，判断请求URL是否成功
    if response.status_code == 200:
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, 'lxml')

        list_title=soup.select('div[id="box-new"]>span')

        for j in list_title:
            word_list.append(j.text)
            f1.write(j.text+" 3 n\n")

                
        print(len(word_list))
    f1.close()
search_url("https://search.qinggl.com/dict-5993.html")


#search_url("http://www.nc.sgcc.com.cn","华北分部要闻")
#search_url_2("http://www.ne.sgcc.com.cn/dbdwww/zxzx/gsxw/default_1.htm","东北分部要闻","http://www.ne.sgcc.com.cn/dbdwww/zxzx/gsxw")
#search_url_2("http://www.ne.sgcc.com.cn/dbdwww/zxzx/gsxw/default.htm","东北分部要闻","http://www.ne.sgcc.com.cn/dbdwww/zxzx/gsxw")
#search_url("http://www.nc.sgcc.com.cn/zxzx/gsxw/index.shtml","华北分部要闻",pre_url="http://www.nc.sgcc.com.cn")


