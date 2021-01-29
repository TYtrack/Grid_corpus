import pyhanlp
#-*- coding:utf-8 -*-
from jpype import *
import os
import tqdm

HanLP = JClass('com.hankcs.hanlp.HanLP')

def walk_file(rootDir):
    list_dirs = os.walk(rootDir)
    dirs_list=[]
    for root, dirs, files in list_dirs:
        for d in files:
            dirs_list.append((os.path.join(root, d)))
    print('总共文件数量：  ',len(dirs_list))
    return dirs_list

def fileReader(path):
    line = []
    rows = 0
    file_list = walk_file(path)
    for filename in tqdm.tqdm(file_list):
        try :
            with open(filename, 'r', encoding='utf-8') as f:
                paras = f.readlines()
                rows += len(paras)
                line += paras
        except FileNotFoundError:
            print("false")

    print("总共读 ", rows, " 行")
    return "".join(line)
    pass

def output_phrase(phrase_list,output_file):
    print(output_file)
    with open(output_file, 'w', encoding="utf-8") as file_2_gram:
        for phrase in phrase_list:
            file_2_gram.write(phrase+"\n")
        #print(aps)

def get_folder_phrase(root_path):
    folder_list=os.listdir(root_path)
    for folder in folder_list:
        path = os.path.join(root_path,folder)
        s=fileReader(path)
        output_phrase(HanLP.extractPhrase(s, 1000),folder+"_phrase.txt")
get_folder_phrase("../语料库2/火力发电")
