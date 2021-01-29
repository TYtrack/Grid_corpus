
import os
import shutil
from tqdm import tqdm
import random
import csv
import pandas as pd

def mkdir(path):
	folder = os.path.exists(path)
	if not folder:                   #判断是否存在文件夹如果不存在则创建为文件夹
		os.makedirs(path)            #makedirs 创建文件时如果路径不存在会创建这个路径
		print("---  new folder...  ---")
	else:
		print("---  There is this folder!  ---")

'''
语料库采样
首先不考虑大的类别，并按小类别进行汇总
'''
def gather():
    big_class_file=os.path.join(os.getcwd(),"url_son_net.txt")
    f1=open(big_class_file,"r",encoding='utf-8')
    all_big=f1.readlines()
    f1.close()
    
    small_class_file=os.path.join(os.getcwd(),"url.txt")
    f2=open(small_class_file,"r",encoding='utf-8')
    all_small=f2.readlines()
    f2.close()

    for i in all_small:
        line=i.split()
        filefolder=line[0]
        
        small_path = os.path.join(os.getcwd(),"汇总",filefolder)
        print("dododo",small_path)
        mkdir(small_path)
        for j in tqdm(all_big):
            line_temp=j.split()
            big_folder=line_temp[1]
            every_file_path=os.path.join(os.path.abspath(os.path.dirname(os.getcwd())),"语料库",big_folder,filefolder)

            file_list=os.listdir(os.path.join(os.path.abspath(os.path.dirname(os.getcwd())),"语料库",big_folder,filefolder))
            for file in file_list:
                try:    
                    shutil.copy(os.path.join(every_file_path,file),small_path)
                except FileNotFoundError:
                    print("No such file or directory")

def sample_file(sample_num=1000):
    sample_csv = open('sample_file.csv', 'w+',encoding='utf-8')
    writer = csv.writer(sample_csv)
    writer.writerow(["label",'title' , 'keywords',"full_text"])

    file_path_2=os.path.join(os.getcwd(),"汇总")

    small_class_file=os.path.join(os.getcwd(),"url.txt")
    f2=open(small_class_file,"r",encoding='utf-8')
    all_small=f2.readlines()
    f2.close()

    for i in all_small:
        line=i.split()
        filefolder=line[0]
        dirlist=os.listdir(os.path.join(file_path_2,filefolder))
        len_list=len(dirlist)
        sample_num=min(sample_num,len_list)
        file_samples = random.sample(dirlist, sample_num)
        for file in tqdm(file_samples):
            with open(os.path.join(file_path_2,filefolder,file),encoding = 'utf-8') as f1:
                texts=f1.readlines()
                texts.insert(0,filefolder)
                texts=[text.strip() for text in texts]
                if len(texts)==4:
                    writer.writerow(texts)
    sample_csv.close()
def readcsv_demo(file):
    csv_1=pd.read_csv(file,encoding="utf-8")
    print(csv_1.shape)
    print(csv_1.head)
    print(csv_1.loc[1:5]['full_text'])

sample_file()
readcsv_demo("sample_file.csv")            

# gather()