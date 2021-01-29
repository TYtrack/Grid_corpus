#!/usr/bin/env python3
# coding=utf-8

import os
import urllib
import re
import random
import string
import operator
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import jieba
from tqdm import tqdm
import heapq


sent_re = re.compile(u'([\%。:：;；？！’、，（）,\'.\\\])')
num_re = re.compile(u'[0-9１２３４５６７８９０]')
alp_re = re.compile(u'[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqresuvwxyz]')
cn_num_re = re.compile(u'[一二三四五六七八九十百千万]')
'''
实现了 NGram 算法，并对 markov 生成的句子进行打分；
'''


jieba.load_userdict("D:\\华科NLP项目\\中孚电网\\中孚词典\\分词词典.txt")


# 创建停用词列表
def stopwordslist():
    stopwords = [line.strip() for line in open('stopwords.txt', encoding='UTF-8').readlines()]
    return stopwords


# 对句子进行中文分词
def seg_depart(sentence, stopwords):
    # 对文档中的每一行进行中文分词
    print("正在分词")
    sentence_depart = jieba.cut(sentence.strip())

    # 输出结果为outstr
    outstr = ''
    # 去停用词
    for word in sentence_depart:
        if (word not in stopwords) and (not word.isnumeric()):
            if word != '\t':
                outstr += word
                outstr += " "
    return outstr


def strconcat(str_list):
    temp_str = ""
    for i in str_list:
        temp_str += i
    return temp_str


def readcsv_demo(file):
    csv_1 = pd.read_csv(file, encoding="utf-8")
    x = csv_1.groupby("label")['full_text'].apply(strconcat).to_dict()

    print(x.keys())
    print(type(x))
    return x


def get_tf_idf(x):
    # 先分词
    corpus = []
    label = []
    stopwords = stopwordslist()
    for key in tqdm(x.keys()):
        x[key] = seg_depart(x[key], stopwords)
        label.append(key)
        corpus.append(x[key])
    print(len(corpus))

    cv = CountVectorizer()
    words = cv.fit_transform(corpus)

    tfidf = TfidfTransformer().fit_transform(words).toarray()

    for temp_index, now_label in enumerate(label):
        temp_list = list(tfidf[temp_index])
        # 获得最大的10个数的索引
        re2 = list(map(temp_list.index, heapq.nlargest(10, temp_list)))
        paiming = [cv.get_feature_names()[i] for i in re2]
        print("{} 类别中tfidf最大的10个词：  {}".format(now_label, paiming))


get_tf_idf(readcsv_demo("sample_file.csv"))


class ScoreInfo:
    score = 0
    content = ''


class N_2_Gram:
    __dicWordFrequency = dict()  # 词频
    __dicPhraseFrequency = dict()  # 词段频
    __dicPhraseProbability = dict()  # 词段概率

    def printNGram(self):
        print('词频')
        for key in self.__dicWordFrequency.keys():
            print('%s\t%s' % (key, self.__dicWordFrequency[key]))
        print('词段频')
        for key in self.__dicPhraseFrequency.keys():
            print('%s\t%s' % (key, self.__dicPhraseFrequency[key]))
        print('词段概率')
        for key in self.__dicPhraseProbability.keys():
            print('%s\t%s' % (key, self.__dicPhraseProbability[key]))

    def print_1(self):
        with open("n_gram关键字/2_gram.txt", 'w', encoding="utf-8") as file_2_gram:
            aps = sorted(self.__dicPhraseFrequency.items(), key=lambda d: d[1], reverse=True)
            for n_gram in aps:
                file_2_gram.write(n_gram[0]+"\t"+str(n_gram[1])+"\n")
            print(aps)


    def append(self, content):
        '''
        训练 ngram  模型
        :param content: 训练内容
        :return:
        '''
        # clear
        content = re.sub('\s|\n|\t', '', str(content))
        ie = self.getIterator(content)  # 2-Gram 模型
        keys = []
        for w in ie:
            # 词频

            k1 = w[0]
            k2 = w[1]

            if k1 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k1] = 0
            if k2 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k2] = 0
            self.__dicWordFrequency[k1] += 1
            self.__dicWordFrequency[k2] += 1
            # 词段频
            key = '%s%s' % (w[0], w[1])
            if sent_re.findall(key) or num_re.findall(key) or cn_num_re.findall(key) or alp_re.findall(key):
                continue
            keys.append(key)
            if key not in self.__dicPhraseFrequency.keys() :
                self.__dicPhraseFrequency[key] = 0
            self.__dicPhraseFrequency[key] += 1

        # 词段概率
        for w1w2 in keys:
            w1 = w1w2[0]
            w1Freq = self.__dicWordFrequency[w1]
            w1w2Freq = self.__dicPhraseFrequency[w1w2]
            # P(w1w2|w1) = w1w2出现的总次数/w1出现的总次数 = 827/2533 ≈0.33 , 即 w2 在 w1 后面的概率
            self.__dicPhraseProbability[w1w2] = round(w1w2Freq / w1Freq, 2)
        pass

    def getIterator(self, txt):
        '''
        bigram 模型迭代器
        :param txt: 一段话或一个句子
        :return: 返回迭代器，item 为 tuple，每项 2 个值
        '''
        ct = len(txt)
        if ct < 2:
            return txt
        for i in range(ct - 1):
            w1 = txt[i]
            w2 = txt[i + 1]
            yield (w1, w2)

    def getScore(self, txt):
        '''
        使用 ugram 模型计算 str 得分
        :param txt:
        :return:
        '''
        ie = self.getIterator(txt)
        score = 1
        fs = []
        for w in ie:
            key = '%s%s' % (w[0], w[1])
            freq = self.__dicPhraseProbability[key]
            fs.append(freq)
            score = freq * score
        # print(fs)
        # return str(round(score,2))
        info = ScoreInfo()
        info.score = score
        info.content = txt
        return info

    def sort(self, infos):
        '''
        对结果排序
        :param infos:
        :return:
        '''
        return sorted(infos, key=lambda x: x.score, reverse=True)


class N_3_Gram:
    __dicWordFrequency = dict()  # 词频
    __dicPhraseFrequency = dict()  # 词段频
    __dicPhraseProbability = dict()  # 词段概率

    def printNGram(self):
        print('词频')
        for key in self.__dicWordFrequency.keys():
            print('%s\t%s' % (key, self.__dicWordFrequency[key]))
        print('词段频')
        for key in self.__dicPhraseFrequency.keys():
            print('%s\t%s' % (key, self.__dicPhraseFrequency[key]))
        print('词段概率')
        for key in self.__dicPhraseProbability.keys():
            print('%s\t%s' % (key, self.__dicPhraseProbability[key]))

    def print_1(self):
        with open("n_gram关键字/3_gram.txt", 'w', encoding="utf-8") as file_3_gram:
            aps = sorted(self.__dicPhraseFrequency.items(), key=lambda d: d[1], reverse=True)
            for n_gram in aps:
                file_3_gram.write(n_gram[0]+"\t"+str(n_gram[1])+"\n")
            print(aps)


    def append(self, content):
        '''
        训练 ngram  模型
        :param content: 训练内容
        :return:
        '''
        # clear
        content = re.sub('\s|\n|\t', '', str(content))
        ie = self.getIterator(content)  # 2-Gram 模型
        keys = []
        for w in ie:
            # 词频
            k1 = w[0]
            k2 = w[1]
            k3 = w[2]

            if k1 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k1] = 0
            if k2 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k2] = 0
            if k3 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k3] = 0

            self.__dicWordFrequency[k1] += 1
            self.__dicWordFrequency[k2] += 1
            self.__dicWordFrequency[k3] += 1

            # 词段频
            key = '%s%s%s' % (w[0], w[1], w[2])
            if sent_re.findall(key) or num_re.findall(key) or cn_num_re.findall(key) or alp_re.findall(key):
                continue
            keys.append(key)
            if key not in self.__dicPhraseFrequency.keys() :
                self.__dicPhraseFrequency[key] = 0
            self.__dicPhraseFrequency[key] += 1

        # 词段概率
        for w1w2w3 in keys:
            w1 = w1w2w3[0]
            w1Freq = self.__dicWordFrequency[w1]
            w1w2w3Freq = self.__dicPhraseFrequency[w1w2w3]
            # P(w1w2|w1) = w1w2出现的总次数/w1出现的总次数 = 827/2533 ≈0.33 , 即 w2 在 w1 后面的概率
            self.__dicPhraseProbability[w1w2w3] = round(w1w2w3Freq / w1Freq, 2)
        pass


    def getIterator(self, txt):
        '''
        bigram 模型迭代器
        :param txt: 一段话或一个句子
        :return: 返回迭代器，item 为 tuple，每项 2 个值
        '''
        ct = len(txt)
        if ct < 3:
            return txt
        for i in range(ct - 2):
            w1 = txt[i]
            w2 = txt[i + 1]
            w3 = txt[i+2]
            yield (w1, w2, w3)


    def getScore(self, txt):
        '''
        使用 ugram 模型计算 str 得分
        :param txt:
        :return:
        '''
        ie = self.getIterator(txt)
        score = 1
        fs = []
        for w in ie:
            key = '%s%s' % (w[0], w[1])
            freq = self.__dicPhraseProbability[key]
            fs.append(freq)
            score = freq * score
        # print(fs)
        # return str(round(score,2))
        info = ScoreInfo()
        info.score = score
        info.content = txt
        return info

    def sort(self, infos):
        '''
        对结果排序
        :param infos:
        :return:
        '''
        return sorted(infos, key=lambda x: x.score, reverse=True)


class N_4_Gram:
    __dicWordFrequency = dict()  # 词频
    __dicPhraseFrequency = dict()  # 词段频
    __dicPhraseProbability = dict()  # 词段概率

    def printNGram(self):
        print('词频')
        for key in self.__dicWordFrequency.keys():
            print('%s\t%s' % (key, self.__dicWordFrequency[key]))
        print('词段频')
        for key in self.__dicPhraseFrequency.keys():
            print('%s\t%s' % (key, self.__dicPhraseFrequency[key]))
        print('词段概率')
        for key in self.__dicPhraseProbability.keys():
            print('%s\t%s' % (key, self.__dicPhraseProbability[key]))

    def print_1(self):
        with open("n_gram关键字/4_gram.txt", 'w', encoding="utf-8") as file_4_gram:
            aps = sorted(self.__dicPhraseFrequency.items(), key=lambda d: d[1], reverse=True)
            for n_gram in aps:
                file_4_gram.write(n_gram[0]+"\t"+str(n_gram[1])+"\n")
            print(aps)


    def append(self, content):
        '''
        训练 ngram  模型
        :param content: 训练内容
        :return:
        '''
        # clear
        content = re.sub('\s|\n|\t', '', str(content))
        ie = self.getIterator(content)  # 2-Gram 模型
        keys = []
        for w in ie:
            # 词频
            k1 = w[0]
            k2 = w[1]
            k3 = w[2]
            k4 = w[3]

            if k1 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k1] = 0
            if k2 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k2] = 0
            if k3 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k3] = 0
            if k4 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k4] = 0
            self.__dicWordFrequency[k1] += 1
            self.__dicWordFrequency[k2] += 1
            self.__dicWordFrequency[k3] += 1
            self.__dicWordFrequency[k4] += 1

            # 词段频
            key = '%s%s%s%s' % (w[0], w[1], w[2],w[3])
            if sent_re.findall(key) or num_re.findall(key) or cn_num_re.findall(key) or alp_re.findall(key):
                continue
            keys.append(key)
            if key not in self.__dicPhraseFrequency.keys() :
                self.__dicPhraseFrequency[key] = 0
            self.__dicPhraseFrequency[key] += 1

        # 词段概率
        for w1w2w3w4 in keys:
            w1 = w1w2w3w4[0]
            w1Freq = self.__dicWordFrequency[w1]
            w1w2w3w4Freq = self.__dicPhraseFrequency[w1w2w3w4]
            # P(w1w2|w1) = w1w2出现的总次数/w1出现的总次数 = 827/2533 ≈0.33 , 即 w2 在 w1 后面的概率
            self.__dicPhraseProbability[w1w2w3w4] = round(w1w2w3w4Freq / w1Freq, 2)
        pass


    def getIterator(self, txt):
        '''
        bigram 模型迭代器
        :param txt: 一段话或一个句子
        :return: 返回迭代器，item 为 tuple，每项 2 个值
        '''
        ct = len(txt)
        if ct < 4:
            return txt
        for i in range(ct - 3):
            w1 = txt[i]
            w2 = txt[i + 1]
            w3 = txt[i + 2]
            w4 = txt[i + 3]
            yield (w1, w2, w3, w4)


    def getScore(self, txt):
        '''
        使用 ugram 模型计算 str 得分
        :param txt:
        :return:
        '''
        ie = self.getIterator(txt)
        score = 1
        fs = []
        for w in ie:
            key = '%s%s' % (w[0], w[1])
            freq = self.__dicPhraseProbability[key]
            fs.append(freq)
            score = freq * score
        # print(fs)
        # return str(round(score,2))
        info = ScoreInfo()
        info.score = score
        info.content = txt
        return info

    def sort(self, infos):
        '''
        对结果排序
        :param infos:
        :return:
        '''
        return sorted(infos, key=lambda x: x.score, reverse=True)


def fileReader():
    path = "语料库2/火力发电/综合"
    filelist=os.listdir(path)
    line = []
    rows = 0
    for filename in filelist:
        with open(os.path.join(path,filename), 'r', encoding='utf-8') as f:

            paras = f.readlines()
            rows += len(paras)
            line += paras

    print("总共读 ", rows, " 行")
    yield line

    pass




def main():
    ng = N_4_Gram()
    reader = fileReader()
    # 将语料追加到 bigram 模型中
    for row in reader:
        #print(row)
        ng.append(row)
    # ng.printNGram()
    # 测试生成的句子，是否合理

    print("*" * 100)
    ng.print_1()
    print("*" * 100)
    pass


if __name__ == '__main__':
    main()
    pass