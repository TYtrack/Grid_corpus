from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import jieba
from tqdm import tqdm
import heapq

jieba.load_userdict("C:/Users/HUST/Desktop/中孚项目/词典构建/分词词典.txt")

# 创建停用词列表
def stopwordslist():
    stopwords = [line.strip() for line in open('stopwords.txt',encoding='UTF-8').readlines()]
    return stopwords

# 对句子进行中文分词
def seg_depart(sentence,stopwords):
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
    temp_str=""
    for i in str_list:
        temp_str+=i
    return temp_str

def readcsv_demo(file):
    csv_1=pd.read_csv(file,encoding="utf-8")
    x= csv_1.groupby("label")['full_text'].apply(strconcat).to_dict()

    print(x.keys())
    print(type(x))
    return x
    
    

def get_tf_idf(x):
    #先分词
    corpus=[]
    label=[]
    stopwords = stopwordslist()
    for key in tqdm(x.keys()):
        x[key]=seg_depart(x[key],stopwords)
        label.append(key)
        corpus.append(x[key])
    print(len(corpus))
    
    cv = CountVectorizer()
    words=cv.fit_transform(corpus)

    
    tfidf = TfidfTransformer().fit_transform(words).toarray()
    
    for temp_index,now_label in enumerate(label):
        temp_list=list(tfidf[temp_index])
        #获得最大的10个数的索引
        re2 = list(map(temp_list.index, heapq.nlargest(10, temp_list)))
        paiming= [cv.get_feature_names()[i] for i in re2]
        print("{} 类别中tfidf最大的10个词：  {}".format(now_label, paiming )) 
    
    
get_tf_idf(readcsv_demo("sample_file.csv"))

'''
words = CountVectorizer().fit_transform(corpus)
tfidf = TfidfTransformer().fit_transform(words)
 
#print (cv.get_feature_names())
print (words.toarray())
print (tfidf)
'''