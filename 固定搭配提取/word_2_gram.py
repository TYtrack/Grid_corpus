#coding:utf-8
import os
import jieba
import re
import tqdm
sent_re = re.compile(u'([\%。:：;；？！’、，（）,\'.\\\])')
num_re = re.compile(u'[0-9１２３４５６７８９０]')
alp_re = re.compile(u'[ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqresuvwxyz]')
cn_num_re = re.compile(u'[一二三四五六七八九十百千万]')
# 创建停用词列表
stopwords = [line.strip() for line in open('stopwords.txt',encoding='UTF-8').readlines()]


def fenci_demo(str_1):
    word_list = jieba.cut(str_1)
    # print("|".join(word_list))
    return list(word_list)
    #return word_list


'''
原文：
12月22日，国网四川省电力公司“配电网三相电能计量系统现场整体检测系统”
发明专利获英国专利局授权。此次成功授权英国专利，标志着中国在配电网三相
电能计量系统整体检测技术能力已处于国际领先水平。该发明专利始于国网四川
电力计量中心专家江波于2007年展开的研究项目《高压三相组合互感器检定标准
装置研究》。该发明专利于2011年申报成功中国国家发明专利。这项发明专利是
一种配电网三相电能计量装置整体检测系统，解决了现场接近运行工况下测试分
析的关键技术问题，能够还原现场实际运行条件，整体检测配电网计量装置，得
到配电网三相供电系统较为准确的误差数据，有效解决了目前只能开展单相检测
检定方式的问题，提升了配电网计量装置检修和故障排查的技术能力。
'''


class N_2_word_Gram:
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
        with open("2_word_gram.txt", 'w', encoding="utf-8") as file_2_gram:
            aps = sorted(self.__dicPhraseFrequency.items(), key=lambda d: d[1], reverse=True)
            for n_gram in aps:
                file_2_gram.write(n_gram[0]+"\t"+str(n_gram[1])+"\n")
            #print(aps)


    def append(self, content):
        '''
        训练 ngram  模型
        :param content: 训练内容
        :return:
        '''
        # clear
        content = re.sub('\s|\n|\t', '', str(content))
        print("zzz")
        ie = self.getIterator(content)  # 2-Gram 模型
        keys = []
        for w in ie:
            # 词频

            k1 = w[0]
            k2 = w[1]
            if k1 in stopwords or k2 in stopwords:
                continue
            # 词段频
            key = '%s%s' % (w[0], w[1])
            if sent_re.findall(key) or num_re.findall(key) or cn_num_re.findall(key) or alp_re.findall(key):
                continue
            if k1 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k1] = 0
            if k2 not in self.__dicWordFrequency.keys():
                self.__dicWordFrequency[k2] = 0
            self.__dicWordFrequency[k1] += 1
            self.__dicWordFrequency[k2] += 1



            keys.append(key)
            if key not in self.__dicPhraseFrequency.keys() :
                self.__dicPhraseFrequency[key] = 0
            self.__dicPhraseFrequency[key] += 1

        '''
        # 词段概率
        for w1w2 in keys:
            w1 = w1w2[0]
            w1Freq = self.__dicWordFrequency[w1]
            w1w2Freq = self.__dicPhraseFrequency[w1w2]
            # P(w1w2|w1) = w1w2出现的总次数/w1出现的总次数 = 827/2533 ≈0.33 , 即 w2 在 w1 后面的概率
            self.__dicPhraseProbability[w1w2] = round(w1w2Freq / w1Freq, 2)
        '''
        pass

    def getIterator(self, txt):
        '''
        bigram 模型迭代器
        :param txt: 一段话或一个句子
        :return: 返回迭代器，item 为 tuple，每项 2 个值
        '''
        fenci_res=fenci_demo(txt)

        ct = len(fenci_res)

        if ct < 2:
            return fenci_res[0]
        for i in range(ct - 1):
            w1 = fenci_res[i]
            w2 = fenci_res[i + 1]
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


def walk_file(rootDir):
    list_dirs = os.walk(rootDir)
    dirs_list=[]
    for root, dirs, files in list_dirs:
        for d in files:
            dirs_list.append((os.path.join(root, d)))
    print('总共文件数量：  ',len(dirs_list))
    return dirs_list



def fileReader():
    path = "../语料库2/火力发电/人物"
    #folderlist=os.listdir(path)
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
    yield line
    pass

def main():
    ng = N_2_word_Gram()
    reader = fileReader()
    # 将语料追加到 bigram 模型中
    for row in tqdm.tqdm(reader):
        #print(row)
        ng.append(row)
    # ng.printNGram()
    # 测试生成的句子，是否合理

    print("*" * 100)
    ng.print_1()
    print("*" * 100)
    pass

main()