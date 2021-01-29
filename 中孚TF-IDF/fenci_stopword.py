import jieba
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

# 给出文档路径
filename = "Init.txt"
outfilename = "out.txt"
inputs = open(filename, 'r', encoding='UTF-8')
outputs = open(outfilename, 'w', encoding='UTF-8')
# 创建一个停用词列表
stopwords = stopwordslist()
# 将输出结果写入ou.txt中
for line in inputs:
    line_seg = seg_depart(line,stopwords)
    outputs.write(line_seg + '\n')
    print("-------------------正在分词和去停用词-----------")
outputs.close()
inputs.close()
print("删除停用词和分词成功！！！")
