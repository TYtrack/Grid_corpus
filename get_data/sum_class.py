#-*- coding:utf-8 -*-
#汇总语料库，把所有“会议”的文章放在一起
import os
import shutil


def mkdir(path):
    folder = os.path.exists(path)
    if not folder:  # 判断是否存在文件夹如果不存在则创建为文件夹
        os.makedirs(path)  # makedirs 创建文件时如果路径不存在会创建这个路径
        #print("---  new folder...  ---  ", path)
    else:
        pass
        #print("---  There is this folder!  ---  ", path)

# -*- coding: utf-8 -*-
"""import os
def Test1(rootDir):
    list_dirs = os.walk(rootDir)
    for root, dirs, files in list_dirs:
        for d in dirs:
            print(os.path.join(root.split('/')[-1], d))
        for f in files:
            print(os.path.join(root.split('/')[-1], f))

Test1("../n_gram关键字")"""
if __name__ == '__main__':
    mkdir("../语料库")
    classes = os.listdir("../语料库2/火力发电")
    all_son = os.listdir("../语料库2")
    for son in all_son:
        source_path=os.path.join("../语料库2",son)
        for root, dirs, files in os.walk(source_path):
            try :
                for file in files:
                    src_file = os.path.join(root, file)
                    print(root)
                    target_path = os.path.join("../语料库", root.split('\\')[-1])
                    mkdir(target_path)
                    shutil.copy(src_file, target_path)
                    #print(src_file)
            except FileNotFoundError:
                print("false")