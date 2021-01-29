# -*- coding: utf-8 -*-
import os
import re
import time
from multiprocessing import Process, Manager, Lock

import common.LogManager as LogManager
import common.config_manager as config_manager
import common.utils as utils
from common.utils import myopen
from preprocess.nlp_model import NLP_MODEL
from preprocess.arclist import ArcList
from common.database_manager import Database
from common.search_engine_manager import LoadElasticSearch

logger = LogManager.getLog()
min_word_num = 1
max_word_num = 5
min_char_num = 4
max_char_num = 10
sent_re = re.compile(u'([。；？！])')
num_re = re.compile(u'[0-9１２３４５６７８９０]')
cn_num_re = re.compile(u'[一二三四五六七八九十百千万]')
pos_pass_re = re.compile(r'n[sih]|wp')
fuhao_re = re.compile(r'[、，和与]')
cut_re = re.compile(r'[“”]')
group_title_num = 1000  # 每次从数据库查询语句的条数
phra_index = "znxz_phra"

# 如果txt文档的sentence数据都存到sentence表，则不需要在本文件中处理txt文件并存到txt_sentence表。
sentence_table_name = 'sentence'

db = Database.get_db()


def save_phrase( process_count=4):
    """
    从所有文件里得到固定搭配，所有文件都分析完以后存到数据库
    :param doc_dir: 要读取的文档路径
    :param process_count: 进程数量
    :param init_doc:是否初始化读取文档内容分割存储到数据库
    """
    # start_time = time.time()
    # if init_doc:
    #     read_doc(doc_dir)
    #     end_time = time.time()
    #     logger.info('读取文件，分割语句完成，耗时%.2f秒' % (end_time - start_time))
    # ltp模型要用多线程只能每个线程获取一个实例，否则会直接中断。
    # 多进程中ltp模型可以共用，并不会中断
    if process_count > 0:
        start_process(process_count)


def start_process(process_count):
    """
    多线程改成多进程，cpu利用率才能提高为多倍
    开启多进程，提取固定搭配
    :param process_count: 线程数量
    """
    sql = "select count(id) from %s" % sentence_table_name
    all_sentence_count = db.fetchone(sql)[0]
    one_process_count = all_sentence_count / process_count
    start_time = time.time()
    process_list = []
    logger.info('语句总数：%s，即将开启%s个进程进行处理' % (all_sentence_count, process_count))
    # 主进程中先清空计数表的数据，
    phrase_list = PhraseList()
    phrase_list.truncate_table()
    phrase_count_list = PhraseCountList()
    phrase_count_list.truncate_table()

    manager = Manager()
    phrase_global_id = manager.Value('tmp', 1)  # 进程间共享的phrase编号，防止编号重复

    lock = manager.Lock()
    for i in range(process_count):

        # 每个进程中自己维护list
        start_index = i * one_process_count
        if i < process_count - 1:
            end_index = (i + 1) * one_process_count
        else:
            end_index = all_sentence_count
        t = Process(target=process_work, args=(i, start_index, end_index, phrase_global_id, lock))
        process_list.append(t)
        t.start()
    for t in process_list:
        t.join()
    end_time = time.time()
    phrase_count_list.merge_count()
    filter_verified()
    # insert2es()
    # verify_white()
    logger.info('固定搭配提取完成，总耗时%.2f' % (end_time - start_time))


def insert2es():
    """
    读取固定搭配表的数据，写到es中。
    """
    phrase_table_name = 'phrase_count_verified'
    es_object = LoadElasticSearch(phra_index)
    final_phrase_id = int(db.fetchone('select id from %s order by id desc limit 1' % phrase_table_name)[0])
    group_start_id = 0
    group_num = 1000
    insert_list = []
    curr_phrase_id = 1
    while group_start_id < final_phrase_id:
        group_end_id = group_start_id + group_num
        phrases = db.fetchall(
            'select id,content,ncontent,times from  %s where id > %s and id <= %s' % (phrase_table_name,
                                                                                      group_start_id, group_end_id))
        for phrase in phrases:
            phra_obj = {
                "_id": curr_phrase_id,
                "content": phrase[1],
                "ncontent": phrase[2],
                "times": phrase[3]
            }
            insert_list.append(phra_obj)
            curr_phrase_id += 1
        es_object.add_date_bulk(insert_list)
        insert_list = []
        group_start_id = group_end_id
    if len(insert_list) > 0:
        es_object.add_date_bulk(insert_list)


def get_phrase(sentence, nlp_model):
    """
    单句话提取固定搭配，用来测试
    :param sentence: 要提取固定搭配的语句
    """
    phrase_list = PhraseList()
    phrase_count_list = PhraseCountList()
    check_phrase(0, 0, sentence, phrase_list, phrase_count_list, nlp_model)
    phrase_count_list.print_n_count(0)


def process_work(process_id, start_index, end_index, phrase_global_id, lock):
    """
    每一个子进程都把数据写进数据库以后再在主进程中读取数据，把计数合并。
    :param process_id:
    :param start_index:
    :param end_index:
    """
    # 多进程操作数据库需要开启多个连接，否则报Lost connection to MySQL server during query异常
    db_t = Database()  # 创建Database数据库对象
    sen_index = start_index
    start_time = time.time()
    nlp_model = NLP_MODEL(black=True)
    phrase_list = PhraseList(process_id)
    phrase_count_list = PhraseCountList(process_id)
    while sen_index < end_index:
        left_id = sen_index
        right_id = sen_index + group_title_num
        if right_id > end_index:
            right_id = end_index
        sql = "select id,content from %s where id >%s and id <=%s" % (
            sentence_table_name, left_id, right_id)
        results = db_t.fetchall(sql)
        end_time = time.time()
        logger.debug('进程%s，正在处理语句(%s,%s]，已耗时%.2f秒' % (process_id, left_id, right_id, (end_time - start_time)))
        for row in results:
            # 对文件分词
            sentence = row[1]
            sid = row[0]
            check_phrase(phrase_global_id, sid, sentence, phrase_list, phrase_count_list, nlp_model, lock)
        sen_index = right_id
    end_time = time.time()
    # phrase_list.insert_db(process_id)
    # logger.debug('进程%s，完成phrase插入，共耗时%.2f秒' % (process_id, (end_time - start_time)))

    # phrase_count_list.insert_db(process_id)

    logger.debug('进程%s，完成%s条语句，共耗时%.2f秒' % (process_id, (end_index - start_index), (end_time - start_time)))


def check_pos_pass(pos):
    """
    判断词性是否要跳过，也就是不符合要求
    :param pos:词性
    :return: 是否跳过
    """
    if type(pos) == type([]):
        for p in pos:
            if pos_pass_re.match(p):
                return True
    else:
        if pos_pass_re.match(pos):
            return True
    return False


def check_pos_equal(posb, posn):
    """
    验证符号前后两部分的词性是否匹配
    :param posb: 符号前部分的词性列表
    :param posn: 符号后部分的词性列表
    :return: 返回匹配结果，1是匹配，其他是不匹配
    """
    eql_fuhao = 'nvjai'
    if check_pos_pass(posb) or check_pos_pass(posn):
        # 符号
        return -1
    elif posb == posn:
        # 匹配
        return 1
    else:
        for pb, pn in zip(posb, posn):
            if check_pos_pass(posb) or check_pos_pass(posn):
                return -1
            pb = pb[0]
            pn = pn[0]
            if pb == pn:
                continue
            elif pn in eql_fuhao and pb in eql_fuhao:
                continue
            else:
                # 不匹配
                return 0
        return 1


# 判断句子中的固定搭配，并存入列表中
def check_phrase(phrase_global_id, sid, sentence, phrase_list, phrase_count_list, nlp_model, lock=None):
    """
    判断句子中是否存在固定搭配，若存在则存入phrase_list和phrase_count_list列表中
    :param first_id:初始id表示第一个phrase的id，用来给phrase_index一直累加
    :param sid:对应的sentence表的id
    :param sentence:待提取的语句
    :param phrase_list:用来存储phrase对象的列表
    :param phrase_count_list:用来存储phraseCount对象的列表
    :param nlp_model:初始化完成的ltp模型
    :return:返回这句话中找到的固定搭配数量，用来修改下一次的初始id
    """
    phrase_count = 0
    try:
        sentence = sentence.decode('utf8')
    except:
        pass
    sentence = cut_re.sub('', sentence)
    words = nlp_model.apdapsegment_sentence(sentence)
    fuhao_indexs = []
    continuous_indexs = set()
    group_continuous_indexs = []

    fuhao_all = fuhao_re.search(sentence)
    if fuhao_all is None:
        return 0

    # 如果遇到依存关系为CMP，并且词数=另一组的词数+1，则合并CMP的词，再次计算词性和句法
    # 例：看好自己的门、管好自己的人。原始分词中将“看好”分到一起，“管”，“好”分开。现在将“管好”合并。
    _arclist = None
    postags=None
    cmp_fuhao_indexs = [-1]
    cmp_words_indexs = []
    for word_i, word in enumerate(words):
        if utils.is_python_2():
            w=word.decode('utf8')
        else:
            w=word
        if fuhao_re.match(w):
            # 当前词为符号
            cmp_fuhao_indexs.append(word_i)
    half_word_lens = []  # 每个短语中词的数量
    for i, index in enumerate(cmp_fuhao_indexs):
        if i == 0:
            continue
        half_word_lens.append(index - cmp_fuhao_indexs[i - 1])
    min_max_len = []
    for i, half_word_len in enumerate(half_word_lens):
        if i==len(half_word_lens)-1:break
        if half_word_len<min_word_num + 1 or half_word_len>max_word_num + 1:continue
        if abs(half_word_len - half_word_lens[i + 1]) == 1:
            # 计算相邻两个短语的词数，保证两个短语的词数相差1
            if len(min_max_len) == 0:
                min_max_len = [half_word_len, half_word_lens[i + 1]]
            elif len(cmp_words_indexs) == 0:
                min_max_len = [half_word_len, half_word_lens[i + 1]]
            elif half_word_lens[i + 1] not in min_max_len:
                min_max_len = [half_word_len, half_word_lens[i + 1]]
        elif len(min_max_len) == 0:
            continue
        if _arclist is None:
            postags = nlp_model.get_pos(words)
            _arclist = ArcList(nlp_model.get_arc(words, postags))  # 句法分析
        if half_word_len == max(min_max_len):
            word_indexs = range(cmp_fuhao_indexs[i] + 1, cmp_fuhao_indexs[i + 1] )
            for word_index in word_indexs:
                word_arc = _arclist.get_arcitem(word_index + 1)
                if word_arc.get_relation() == 'CMP':
                    cmp_words_indexs.append([word_arc.get_head() - 1, word_arc.get_index() - 1])

    if len(cmp_words_indexs) > 0:
        cmp_words_indexs.reverse()
        words=list(words)
        for cmp_words_index in cmp_words_indexs:
            words[cmp_words_index[0]] += words[cmp_words_index[1]]
            words.pop(cmp_words_index[1])
        # logger.debug('更新分词结果为：%s' % ' '.join(words))
    for word_i, word in enumerate(words):
        # 先找到连续符号并归组
        if utils.is_python_2():
            w=word.decode('utf8')
        else:
            w=word
        if fuhao_re.match(w):
            # 当前词为符号
            if len(fuhao_indexs) > 0:
                last_fuhao_index = fuhao_indexs[-1]
                last_fuhao = words[last_fuhao_index]
                current_fuhao_range = list(
                    range(last_fuhao_index + min_word_num + 1, last_fuhao_index + max_word_num + 2))
                if word_i in current_fuhao_range and (
                        (last_fuhao == '，' and word != '、') or (last_fuhao == '、' and word != '，')):
                    # 与最后一个符号的距离满足词数要求
                    # 前一个是顿号，现在是逗号则逗号连接的和前面的不在一个组内；
                    continuous_indexs.add(last_fuhao_index)
                    continuous_indexs.add(word_i)
                elif len(continuous_indexs) > 0:
                    # 连续的符号归组后排序
                    continuous_indexs_list = sorted(continuous_indexs)
                    group_continuous_indexs.append(continuous_indexs_list)
                    continuous_indexs = set()
                else:
                    group_continuous_indexs.append([last_fuhao_index])
            fuhao_indexs.append(word_i)
    if len(continuous_indexs) > 0:
        # 最后一组连续的符号归组后排序
        continuous_indexs_list = sorted(continuous_indexs)
        group_continuous_indexs.append(continuous_indexs_list)
    elif len(fuhao_indexs) > 0:
        group_continuous_indexs.append([fuhao_indexs[-1]])
    # 如果找不到连续符号则直接返回
    if len(group_continuous_indexs) == 0:
        return phrase_count
    # 处理连续符号
    if len(cmp_words_indexs) > 0 or _arclist is None:
        #更新词性和句法
        postags = nlp_model.get_pos(words)
        _arclist = ArcList(nlp_model.get_arc(words, postags))  # 句法分析
    postags = list(postags)
    words = list(words)
    # words = [w.encode('utf8') for w in words]
    # 如果有时间，可以把句法分析放在词（包含数字、字数限制、黑名单）和词性验证都通过以后，可以减少计算句法的次数。
    for group_indexs in group_continuous_indexs:
        group_len = len(group_indexs)
        if group_len > 1:
            phrase_before_list, phrase_next_list = multi_fuhao_group(_arclist, words, postags, word,
                                                                     group_indexs)
        else:
            phrase_before_list, phrase_next_list = one_fuhao_group(_arclist, words, postags, word,
                                                                   group_indexs)
        if lock is not None:
            for phrase_before, phrase_next in zip(phrase_before_list, phrase_next_list):
                add_checked_phrase(phrase_global_id, sid, phrase_before, phrase_next, phrase_list, phrase_count_list,
                                   nlp_model, lock)
    return phrase_count


def cul_cont_word_num(group_indexs, word_i):
    """
    根据当前符号在连续符号组中的位置，向前找词的个数，向后找词的个数，取这两者的较大值作为这个符号前后的词的个数
    :param group_indexs: 连续符号组中每个符号的索引列表
    :param word_i: 当前符号的索引
    :return: 这个符号前后的词的个数
    """
    index_gaps = []
    left = -1
    for i, index in enumerate(group_indexs):
        if index > word_i:
            break
        if word_i == index and left > -1:
            index_gaps.append(index - left - 1)
        if i + 1 < len(group_indexs):
            index_gaps.append(group_indexs[i + 1] - index - 1)
        left = index

    return max(index_gaps)


def check_pos_list(pos_before, pos_next):
    """

    :param pos_before:
    :param pos_next:
    :return:
    """
    checked_pos = 0
    for b, n in zip(pos_before, pos_next):
        checked_pos += check_pos_equal(b, n)
    return checked_pos


def check_arc_list(arc_before, arc_next, pos_before, pos_next, can_reverse):
    """
    在连续符号组中可能会要递归判断句法是否满足条件，
    :param arc_before:
    :param arc_next:
    :param can_reverse:句法关系匹配的词在相反的位置上再找一次
    :return:
    """

    reverse_arc_before = []
    reverse_pos_before = []
    for ab, an, pb, pn in zip(arc_before, arc_next, pos_before, pos_next):
        if ab is None or an is None:
            return -1
        if ab.index == an.head:
            # 并列关系的两个词如果位置顺序相同则通过
            # 并列关系的两个词如果位置顺序相反，比较两个词的词性，词性不一样则通过
            if an.relation == 'COO' and (can_reverse or pb != pn):
                return 1
            else:
                return 0
        elif an.relation == 'COO' and ab.relation == 'COO':
            if ab.head == an.head:
                return 1
            else:
                return 0
        reverse_arc_before.insert(0, ab)
        reverse_pos_before.insert(0, pb)
    if can_reverse:
        return check_arc_list(reverse_arc_before, arc_next, reverse_pos_before, pos_next, False)
    return -1


def check_arc_coo(arcb, arcn):
    """
    验证句法关系是否匹配
    :param arcb: 前部分句法列表
    :param arcn: 后部分句法列表
    :return: 返回为1则匹配，其他则不匹配
    """
    for ab, an in zip(arcb, arcn):
        if ab is None or an is None:
            return -1
        if ab.index == an.head:
            if an.relation == 'COO':
                return 1
            else:
                return 0
        elif an.relation == 'COO' and ab.relation == 'COO':
            if ab.head == an.head:
                return 1
            else:
                return 0
    return -1


def multi_fuhao_group(_arclist, words, postags, word, group_indexs):
    """
    这个组里有多个符号，对组内多个符号进行处理。
    :param _arclist:句法结构对象
    :param words:分词后的词列表
    :param postags:词性列表
    :param word:当前符号
    :param group_indexs:多个符号的符号索引列表
    :return:返回元组（前部分短语列表，后部分短语列表）
    """
    # 构造进行验证的词性列表和句法列表
    phrase_before_list = []
    phrase_next_list = []
    last_arc_before = None
    for word_i in group_indexs:
        # 词的个数等于符号两边最多的连续词个数
        cont_word_num = cul_cont_word_num(group_indexs, word_i)
        pos_before = []
        pos_next = []
        arc_before = []
        arc_next = []
        word_before = []
        word_next = []
        word = words[word_i]
        before_break = False
        next_break = False
        for i in range(cont_word_num):
            before_index = word_i - 1 - i
            next_index = word_i + i + 1
            wb, wn = None, None
            if before_index >= 0:
                wb = words[before_index]
                if word_has_num(wb):
                    # 如果词中包含数字，则舍弃这个搭配
                    break
            if next_index < len(postags):
                wn = words[next_index]
                if word_has_num(wn):
                    # 如果词中包含数字，则舍弃这个搭配
                    break
            if wb is not None and wb == wn:
                # before的结尾和next的开头相同，则舍弃这个搭配
                break
            if before_index not in group_indexs:
                # 从靠近符号的地方开始判断词，插入词的顺序反转才可以得到正确的词顺序
                if before_index >= 0:
                    pos_before.insert(0, postags[before_index])
                    arc_before.insert(0, _arclist.get_arcitem(before_index + 1))
                    word_before.insert(0, wb)
            else:
                before_break = True
            if next_index not in group_indexs:
                if next_index < len(postags):
                    pos_next.append(postags[next_index])
                    arc_next.append(_arclist.get_arcitem(next_index + 1))
                    word_next.append(wn)
            else:
                next_break = True
            if before_break or next_break:
                break
        phrase_before = ''.join(word_before)
        phrase_next = ''.join(word_next)
        if len(pos_before) == len(pos_next):
            # 词的数量相等
            checked_pos = check_pos_list(pos_before, pos_next)
            checked_arc = check_arc_list(arc_before, arc_next, pos_before, pos_next, True)
            if checked_arc < 1 and last_arc_before:
                checked_arc = check_arc_list(last_arc_before, arc_next, pos_before, pos_next, True)
            else:
                last_arc_before = arc_before
            if checked_pos * 5 < len(pos_next) * 4 or checked_arc < 1:
                # 有至少2/3的词性是匹配的，才添加进搭配库
                phrase_before = ''
                phrase_next = ''
        # elif len(phrase_before) == len(phrase_next):
        #     # 字数相等
        #     if 'i' in pos_next or 'i' in pos_before:
        #         pass
        #     else:
        #         phrase_before = ''
        #         phrase_next = ''
        else:
            phrase_before = ''
            phrase_next = ''
        phrase_before_list.append(phrase_before)
        phrase_next_list.append(phrase_next)
    return phrase_before_list, phrase_next_list


def one_fuhao_group(_arclist, words, postags, word, group_indexs):
    """
    这个组里就一个符号，所以不涉及到连续符号组的判断问题
    :param _arclist:句法结构对象
    :param words:分词后的词列表
    :param postags:词性列表
    :param word:当前符号
    :param group_indexs:只有一个符号的符号索引列表
    :return:返回元组（前部分短语列表，后部分短语列表）
    """
    word_i = group_indexs[0]
    # 顿号前后比对词性，相同词性
    cursor = 1
    if len(postags) > word_i + 1:
        pb = postags[word_i - 1]
        pn = postags[word_i + 1]
        # _arclist中的索引是从1开始的，所以这里的索引比词性用的索引要大1
        ab = _arclist.get_arcitem_range(word_i)
        an = _arclist.get_arcitem_range(word_i + 2)
        phrase_word_num = 0
        while cursor < 6:
            wb = words[word_i - cursor]
            wn = words[word_i + cursor]
            if word_has_num(wb) or word_has_num(wn):
                # 如果词中包含数字，则舍弃这个搭配
                break
            if wb == wn:
                # before的结尾和next的开头相同，则舍弃这个搭配
                break
            check_pos = check_pos_equal(pb, pn)
            check_arc = check_arc_coo(ab, an)
            if check_pos == -1:  # 如果是符号，结束寻找
                break
            elif check_pos == 1 and check_arc > 0:
                phrase_word_num = cursor
            cursor += 1
            if word_i - cursor < 0 or word_i + cursor + 1 >= len(words):
                break
            pb = postags[word_i - cursor:word_i]
            pn = postags[word_i + 1:word_i + cursor + 1]
            ab = _arclist.get_arcitem_range(word_i - cursor + 1, word_i + 1)
            an = _arclist.get_arcitem_range(word_i + 2, word_i + cursor + 2)
        # phrase_word_num = cursor - 1
        if phrase_word_num > 0:
            if phrase_word_num > 1:
                phrase_before = ''.join(
                    words[word_i - phrase_word_num:word_i])
                phrase_next = ''.join(
                    words[word_i + 1:word_i + phrase_word_num + 1])
            else:
                phrase_before = ''.join(words[word_i - 1])
                phrase_next = ''.join(words[word_i + 1])
            return [phrase_before], [phrase_next]
        else:
            pass
    return [], []


def word_has_num(word):
    """
    在验证词中是否包含数字，如果有则不通过
    :param word:
    :return:
    """
    try:
        word = word.decode('utf8')
    except:
        pass
    if num_re.search(word):
        return True
    else:
        return False


def check_content(content):
    """
    判断当前短语是否符合规则：字数在4-10
    :param content: 短语内容
    :return: 是否符合规则
    """
    # 中文的用str编码长度是3，要decode才行
    try:
        content = content.decode('utf8')
    except:
        pass
    len_content = len(content)
    if len_content >= min_char_num and len_content <= max_char_num:
        return True
    else:
        return False


def add_checked_phrase(phrase_global_id, sid, phrase_before, phrase_next, phrase_list, phrase_count_list, nlp_model,
                       lock):
    """
    向list对象添加短语，添加之前先检查是否符合规则。
    :param phrase_index: 短语编号
    :param sid: 对应sentence表中的语句编号
    :param phrase_list:存储Phrase对象的列表
    :param phrase_count_list: 存储PhraseCount对象的列表
    :param phrase_before: 前部分phrase文本
    :param phrase_next: 后部分phrase文本
    :return: 是否添加成功
    """
    if check_content(phrase_next) and check_content(phrase_before):
        if nlp_model.black_dict.find_in_dict(phrase_before, phrase_next):
            # 在黑名单中找到了这个搭配，舍弃之
            return False
        with lock:
            phrase_index = phrase_global_id.value
            # phrase表中要添加两条记录
            ph = Phrase(phrase_index, sid, phrase_before, 0)
            phrase_list.append(ph)
            ph = Phrase(phrase_index + 1, sid, phrase_next, phrase_index)
            phrase_list.append(ph)
            pc = PhraseCount(phrase_before, phrase_next, sid, '、')
            # 先全部加到phrase_count_tmp表，再统一计数，所以这里添加过程不进行判断
            phrase_count_list.append(pc)
            phrase_global_id.value += 2
            # logger.debug('after lock:%s' % process_id)
        return True
    return False


class Phrase(object):
    def __init__(self, id, sid, content, bid):
        """
        初始化一个短语对象
        :param id: 对应数据库中phrase表的主键id
        :param sid: 对应数据库中sentence表的主键id
        :param content:短语文本
        :param bid:后续短语编号
        """
        self.id = id
        self.sid = sid
        self.content = content
        self.bid = bid


class PhraseList(object):
    def __init__(self, process_id=-1):
        """
        短语列表
        """
        self.list = []
        self.process_id = process_id

    def append(self, phrase):
        self.list.append(phrase)
        if len(self.list) >= 1000:
            self.insert_db()
            self.list = []

    def truncate_table(self):
        # 初次将短语列表的所有记录添加到数据库，首先要清空表
        db.truncate('phrase')
        logger.debug('已清空phrase表数据')

    def insert_db(self):

        base_sql = 'insert into phrase(id,sid,bid,content) values('
        sql = ''
        all_count = len(self.list)
        inserted_count = 0
        for i, phrase in enumerate(self.list):
            sql += "%s,%s,%s,'%s'),(" % (
                phrase.id, phrase.sid, phrase.bid, phrase.content)
            # 如果i+1不加括号，这里判断有误，导致一次判断都不会成功
            if (i + 1) % 1000 == 0:
                sentence_sql = base_sql + sql
                commit_insert(sentence_sql)
                sql = ""
        if len(sql) > 0:
            sentence_sql = base_sql + sql
            commit_insert(sentence_sql)
        # logger.debug('进程%s，已插入%s条phrase记录' % (self.process_id, all_count))


class PhraseCount(object):
    def __init__(self, content, ncontent, sid, type):
        """
        短语计数对象
        :param content: 前部分短语
        :param ncontent: 后部分短语
        :param type: 符号类型
        """
        self.content = content
        self.ncontent = ncontent
        self.sid = sid  # 句子编号
        self.type = type

    # def add_one(self):
    #     """
    #     次数加1
    #     """
    #     self.count += 1


class PhraseCountList(object):
    def __init__(self, process_id=-1):
        """
        存储固定搭配计数对象列表
        """
        self.pclist = []
        self.process_id = process_id
        # self.content_set = set()  # hash集合存储前部分短语，用来验证是否存在
        # self.ncontent_set = set()  # hash集合存储后部分短语，用来验证是否存在

    def append(self, pc):
        """
        添加记录
        :param pc: 短语计数对象
        """
        self.pclist.append(pc)
        if len(self.pclist) >= 1000:
            # logger.debug('进程%s，总共%s条记录' % (self.process_id, len(self.pclist)))
            self.insert_db()
            self.pclist = []

    def print_n_count(self, min_n=1):
        """
        将提取的固定搭配打印到控制台
        :param min_n:要打印的最少固定搭配重复次数
        :return:
        """
        result_list = []
        # f = file("/home/luo/znxz/guowang.txt", "a+")
        for pc in self.pclist:
            str = '%s%s%s' % (pc.content, pc.type,
                              pc.ncontent)
            result_list.append(
                {'content': str, 'score': 1, 'match_content': ''})

        return result_list

    def truncate_table(self):
        """
        清空phrase_count和phrase_count_tmp表的数据
        """
        db.truncate('phrase_count')
        logger.debug('已清空phrase_count表数据')
        db.truncate('phrase_count_tmp')
        logger.debug('已清空phrase_count_tmp表数据')

    def insert_db(self):
        """
        把所有文件中提取到的固定搭配存入数据库,涉及到phrase_count表
        """
        base_sql = 'insert into phrase_count_tmp(sid,content,ncontent) values('
        sql = ''
        all_count = len(self.pclist)
        for i, pc in enumerate(self.pclist):
            sql += "%s,'%s','%s'),(" % (pc.sid, pc.content, pc.ncontent)
            # 如果i+1不加括号，这里判断有误，导致一次判断都不会成功
            if (i + 1) % 1000 == 0:
                sentence_sql = base_sql + sql
                commit_insert(sentence_sql)
                sql = ""
        if len(sql) > 0:
            sentence_sql = base_sql + sql
            commit_insert(sentence_sql)
        # logger.debug('进程%s，已插入%s条phrase_count_tmp记录' % (self.process_id, all_count))

    def merge_count(self):
        """
        将phrase_count_tmp表中的数据分组计数后全部读取出来，再写入phrase_count表中。
        """
        sql = 'SELECT content,ncontent,count(*) cc FROM phrase_count_tmp group by content,ncontent order by cc desc;'
        results = db.fetchall(sql)
        base_sql = 'insert into phrase_count(content,ncontent,times) values('
        sql = ''
        all_count = len(results)
        for i, row in enumerate(results):
            sql += "'%s','%s',%s),(" % (
                row[0], row[1], row[2])
            # 如果i+1不加括号，这里判断有误，导致一次判断都不会成功
            if (i + 1) % 1000 == 0:
                sentence_sql = base_sql + sql
                commit_insert(sentence_sql)
                sql = ""
                if (i + 1) % 10000 == 0:
                    logger.debug('已插入%s条phrase_count记录，总共%s条记录' % (i + 1, all_count))
        if len(sql) > 0:
            sentence_sql = base_sql + sql
            commit_insert(sentence_sql)


def commit_insert(sql):
    """
    执行数据库插入操作
    :param sql: sql语句
    """
    s_sql = sql[:len(sql) - 2]
    db.execute(s_sql)


def read_doc(doc_dir):
    """
    将所有文件的内容分割，存到数据库
    """
    project_path = utils.get_project_path()
    doc_path = os.path.join(project_path, doc_dir)
    path_list = []
    read_deep_file(doc_path, path_list)
    doc_sentence_id = 1
    doc_id = 1
    doc_paragraph_id = 1
    db.truncate('txt_sentence')
    base_sentence_sql = 'insert into txt_sentence(id,fid,pid,content) values('
    # sentence_sql = ''
    doc_sentence_sql = ""
    doc_all_count = len(path_list)
    for path in path_list:
        # if doc_id<4478:
        #     doc_id+=1
        #     continue
        # 如果txt文件的换行符是\r\n，python读取会出错，所以open中模式应改为'rU'
        with myopen(path, 'rU') as file:
            line = file.readline()
            while line:
                line = utils.clean_text(line)
                if len(line) > 0:
                    sentences = []
                    last_sent = ''
                    splits = sent_re.split(line)
                    for ss in splits:
                        # 分割成句子，并且将符号拼接
                        if not sent_re.search(ss):
                            last_sent = ss.strip()
                        else:
                            sentences.append(last_sent + ss)
                    for sentence in sentences:
                        short_sentences = utils.long_sentence_split(sentence)
                        for ss in short_sentences:
                            doc_sentence_sql += "%s,%s,%s,'%s'),(" % (
                                doc_sentence_id, doc_id, doc_paragraph_id, ss)
                            doc_sentence_id += 1
                    doc_paragraph_id += 1
                line = file.readline()
        doc_id += 1

        if doc_id % 100 == 0:
            sentence_sql = base_sentence_sql + doc_sentence_sql
            commit_insert(sentence_sql)
            doc_sentence_sql = ""
        if doc_id % 1000 == 0:
            logger.debug('已读取%s个文件，总共%s个文件' % (doc_id, doc_all_count))
    if len(doc_sentence_sql) > 0:
        sentence_sql = base_sentence_sql + doc_sentence_sql
        commit_insert(sentence_sql)


def read_deep_file(file_path, path_list):
    """
    递归读取文件夹，找到所有的文件存入path_list中
    :param file_path: 文件夹目录
    :param path_list: 存储路径的列表
    """
    if os.path.isdir(file_path):
        file_list = os.listdir(file_path)
        for filename in file_list:
            file = os.path.join(file_path, filename)
            read_deep_file(file, path_list)
    else:
        if file_path.endswith('.txt'):
            path_list.append(file_path)


def list_verifying_phrase():
    """
    将待验证的固定搭配写到文件中。目前需要验证：
    1、含有中文数字的搭配。（提取出的文件存到cn_num_phrase.txt中）
    2、前短语的末尾和后短语开头相同。（提取出的文件存到same_phrase.txt中）
    """
    project_path = utils.get_project_path()
    num_file_path = os.path.join(project_path, 'files', 'verifying', 'cn_num_phrase.txt')
    same_file_path = os.path.join(project_path, 'files', 'verifying', 'same_phrase.txt')
    sql = "select content,ncontent,times from phrase_count"
    results = db.fetchall(sql)
    num_line_count = 0
    same_line_count = 0
    with myopen(num_file_path, 'w') as f_num, myopen(same_file_path, 'w') as f_same:
        for row in results:
            cb = row[0]
            cn = row[1]
            cc = row[2]
            if cn_num_re.search(cb) is not None or cn_num_re.search(cn) is not None:
                f_num.write(cb + '\t' + cn + '\t' + str(cc) + '\n')
                num_line_count += 1
                if num_line_count % 1000 == 0:
                    f_num.flush()
            if cb[2:4] != cn[0:2] and cb[0:2] == cn[2:4]:
                f_same.write(cb + '\t' + cn + '\t' + str(cc) + '\n')
                same_line_count += 1
                if same_line_count % 1000 == 0:
                    f_same.flush()
        f_num.flush()
        f_same.flush()


def filter_verified():
    """
    调用之前，先在数据库中创建存储过程，创建的sql语句在database/procedure_create文件中
    调用存储过程，从phrase_count表中剔除已经验证过的记录，剔除前后长度不一致的记录，出现次数过少的记录。
    phrase_count_verified表中的即为已经验证过的记录。
    最少出现次数在配置文件中配置。
    """
    db.call_proce('phrase_process', config_manager.get_config_values("phrase", "min_times"))
    logger.info('已完成存储过程，对phrase_count表进行过滤')


# def verify_white():
#     """
#     暂时不用白名单进行验证。
#     验证白名单中的固定搭配，通过的写入phrase_count_verified表中
#     """
#     db.truncate('phrase_count_verified')
#     sql = "select content,ncontent,times from phrase_count"
#     results = db.fetchall(sql)
#     base_sql = 'insert into phrase_count_verified(content,ncontent,times) values('
#     sql = ''
#     white_count = 0
#     for i, row in enumerate(results):
#         cb = row[0]
#         cn = row[1]
#         cc = row[2]
#         if white_dict.find_in_dict(cb, cn):
#             sql += "'%s','%s',%s),(" % (cb, cn, cc)
#             white_count += 1
#             if white_count % 1000 == 0:
#                 insert_sql = base_sql + sql
#                 commit_insert(insert_sql)
#                 sql = ""
#         if (i + 1) % 10000 == 0:
#             logger.debug('已验证%s条记录，其中通过白名单的有%s条记录' % ((i + 1), white_count))
#     if len(sql) > 0:
#         insert_sql = base_sql + sql
#         commit_insert(insert_sql)
#     logger.debug('验证%s条记录完成，其中通过白名单的有%s条记录' % (len(results), white_count))


if __name__ == "__main__":
    # doc_dir = '/home/luo/PycharmProjects/AI_Writter/files/source'
    # project_path = utils.get_project_path()
    # black_file_path = os.path.join(project_path, 'files', 'tools', 'phrase_black.txt')
    nlp_model = NLP_MODEL()
    # save_phrase( process_count=4)
    # filter_verified()
    insert2es()
    s = '当用户输入标点符号触发推荐请求到系统后台服务器时，服务器通过推荐评分模块计算合适的推荐内容响应文本推荐请求，输出到前台界面。'
    # s = '总结上半年工作，分析面临的形势，安排下半年任务，牢牢把握雄安新区规划建设重大历史机遇，统一思想、坚定信心、开拓奋进，推动公司和电网创新发展，以优异成绩迎接党的十九大胜利召开。'
    # # s='当用户输入标点符号，触发推荐，请求到系统后台服务器时，凭借顽强的意志成功应对高强度工作和强对流天气多重考验'
    s = '“开拓进取，改革创新、振奋精神、提质增效”'
    # s = '面对成绩不自满，遇到问题不绕道，永不懈怠地向更高目标迈进进。'
    # s = '同时，通过对大量用户对推荐内容选择情况，可以统计分析出不同个人、角色、部门对不同文本推荐内容的偏好，更新用户画像。'
    # s = '收集内外部知识和信息，形成干部之窗、干部培训观测平台、案例平台等数据库。开展与国内和国际机构在业务合作、理论创新、政策研究、人才培养等方面的交流活动。'
    # s = '各地区各部门不断增强政治意识、大局意识、核心意识、看齐意识，深入贯彻落实新发展理念，“十二五”规划胜利完成，“十三五”规划顺利实施，经济社会发展取得历史性成就、发生历史性变革。'
    # s = '时刻保持高度的责任心，面对成绩不自满，遇到问题不绕道，永不懈怠地向更高目标迈进。时刻保持高度的责任心，面对成绩不自满，遇到问题不绕道，永不懈怠地向更高目标迈进。'
    # s='团体一等奖、最强红军奖、最强蓝军奖'
    s = '开拓进取，改革创新、振奋精神、提质增效，开拓进取，改革创新、振奋精神、提质增效。'
    # s='3月9日，国家电网公司党组成员、总会计师罗乾宜在公司总部会见了到访的招商银行党委委员、北京分行行长汪建中一行，双方就国家电网公司与招商银行合作事宜进行了沟通交流。'
    s = u'我在发言中表示，一方面，希望与德方深化技术标准合作，在新能源并网与消纳、电动汽车和储能领域深化研究，加快实施“中国制造2025”和德国工业4.0标准对接，重点深化电动汽车充换电设施、新能源、智慧城市方面标准合作，会上也宣传了我们国家能源转型、经济转型、迈向中高端所取得的成就，从我们电网的用电分析上看，我们的计算机、软件还有新业态，电量的增长都在10%到30%以上，在这个期间，我去看了一个创新创业园，在德国柏林，这是一个大院子，这里面有几十家科研院所、企业在这里设计研发的团队，这就是在中国搞得大众创业万众创新，那也是几十家，看了一个公司，是一个微网，看了他们的介绍，这个微网和我们现在讲的微网是一样的，跟电网连着的一台变压器，剩下是院子里是自己的事情，屋顶上是太阳能，整个院子是充电桩，有多家的充电桩，谁都在这儿可以比，第二个充电桩的一些研究，比如充电汽车，各种各样的充电汽车，怎么样运行最优化，新能源怎么储能，跟电网来的电怎么储能，自己太阳能发的电，就是直流电网，跟自己直流去储能，我看那个从电网上买电的时候是2毛9吧，但是它这个多的时候，卖电不到2毛，电网是稳赚不赔啊，因为我给你备用了啊，因为卖的电量很少啊，最终大家得共赢，从这点是很讲道理的，咱们也在弄这个微网，不讲电压等级，也不讲我这边建多少，建几块太阳能板，我这儿就要低价，正好相反，你这显然是没有道理的，到那去看，微网搞得，起码展示的是很好，我到那里去看，也受启发，德国人做事细，你比如人家弄一个演示版，我们在一带一路演示，就是弄一些小的塑料杆子一连，几个方块就是智能家居，人家那个可不是，人家设计的太阳能、风能、核电、煤电、电动汽车互动，再有一些用电的负荷，高峰低谷，你要加大新能源的投入，新能源的并网，渗透率要提高，立刻电网就会变成什么情况，有不足啊，失控啊，再一加强，都需要电网的统一控制，这个就平衡了，这个演示啊，给人一种内部的运行规律，社会上的各种用电，有机地联系在一起了，外行人一看，很清楚，很生动，我们这个都是静态的，包括大楼里这些演示，我跟于军他们讲，真正的演示，真正把电力系统这么复杂的东西，发、输、变、配同时完成，有这个太阳能、风电这种高度的波动，又得需要大家怎么样去高度地调节，电网的作用，基础设施的作用，这个控制的作用，真得要点功夫，大家这个电力系统的运行控制的东西和知识都有，平常我们也这么做，真像人家表现的那么好，真没有，所以你要在咱们这里面弄，或者在一带一路上面，把它变成非常动态的，体现电力系统本质运行规律的，那咱还真是得下一番功夫，这还是次要的，他弄得各种汽车在那里充电，各种付费的方式，还展示了一段无人驾驶、无线充电，你站上去车就走了，我觉得很受启发，以前彭建国他们说搞一个体验馆，我看这些，包括今后在苏州搞这个城市变革的新区，甚至在我们的风光储输，提高他的科技含量，这个展示能力，这个很震撼，他公司的很小，15个人，天天在那研究这些个事，没有新的理论突破，就是集成，把它演示的非常好，这是我看到的一个从微网也好，从展示也好，对社会上的形象，展现未来电网的发展，新能源你涨到30%以后，这系统会是什么样，都能得到展示，所以我们说在这个张家口示范区都应该有这么一套，需要把我们的风、光、储，在张家口还有一个抽水蓄能，综合起来，这个控制系统，它的功能，什么时候充，什么时候放，风电来了什么时候充，负荷是什么样，再把张家口那个地区电动汽车，以煤代电，这些东西，能够储热，能够储能，把它展示出来，它的水平就高了，我去的那个，就那么一个小屋子，有这半个大，外面是大棚，大棚上面是太阳能，下边是光伏，刘延东副总理去过，孟建柱同志也去过，你别看就这个，它展示的非常好，我们也有这个水平，就是我们做事粗，我们肯定有这个水平，这软件也很容易，我也没有想到，就在我们一带一路上面，我说怎么弄得那么简陋，还不如那个核电，就弄一个大圆的，核反应堆的模型，我说于军这就是你们弄的，我们就是想不到，太匆忙，这次陪总理去，看了创业园区，这个创业园区不少人，成为德国创新的一个集中的展示地方，能源变革，新技术，新产品，我说一直到无线电充电、自动驾驶都有，这个在世界上就很有名了，德国的创新啊就是做的很新，我们也搞这么一个，就把各个电动汽车搞起来，促进战略新兴产业发展你就算做了贡献，微网你也有了，总理提的大众创业万众创新是最生动的一个展示，我们都看了以后很受启发，下来以后要好好规划，研究一下，花不了多少钱，另外，今年1-5月份我们狠抓了，新能源的消纳还是很有效果的，像风电我们增长了17%，太阳能光伏电量增长了84%，这是电量啊，跨区消纳增长了32%，下决心搞，总理提出来新能源消纳的问题，提了三次啊，从葡萄牙回来我们给写，后来我们弄了20条，给总理写了5条措施，一个是加强基础设施建设，加大跨区跨省的电网建设，为新能源在更大范围的消纳提供更大的网络平台，各国都是这样搞得，我说欧洲要在2030年把各国之间的电网容量扩大一倍，也是为了新能源的发展，这是第一条，第二条要增加我们国家的传统能源的调峰建设，我们提出要把火电进行调峰改造，能够压到20%的出力，而且能够跟踪风电这种速率，第三要靠负荷效应，就是用户侧管理，今后有大量的可切断负荷，包括电动汽车这种储能这种建设，今后大规模的风电，新能源的替代还是靠经济规模的储能，第四是市场机制的建设，充分发挥市场在资源配置中的决定性作用，现在省间壁垒阻碍着新能源的跨省消纳，我们要下决心，如果有新能源弃风，我们的跨省输电通道有容量，东部地区有消纳空间，要坚决地调，冲破这个市场壁垒，市场壁垒是省长搞得，省里搞得，我们一个企业你要不冲破这个就消纳不了新能源，现在靠局部消纳已经不行了，这是我们国家的新能源的发展模式决定的，要冲破这种模式，最终要靠市场机制的作用，现在没有，现在各省省长都说不能要了，我们新能源不能超过多少亿，那我们说总理任务怎么完成啊，我们也惹不起省长啊，但这件事情坚决惹，就楞一点，调过来见成效，你看我们跨区的风电增长了30%几，我们反过来去找能源局，你要在日交易当中，在跨省跨区新能源消纳当中给政策，政策的事情我们要坚持，第五是新能源要借鉴国际经验，加强技术交流和合作，根据总理指示要求，我们到了葡萄牙，过几天我们还要跟德国开一个新能源研讨会，这两天宣传也不错，给我们压力也很大，这是倒逼啊，说2020年国家电网公司风电弃风率5%，我们是研究有这么个目标，但是你说出去了，我们就要按这个目标来实现，但是要搞好规划，这都是亮点的工作，一会儿我要讲到还有一些。'
    # ss = long_sentence_split(s)
    s = '通过日内电力交易系统达成各类日前、实时交易2392笔，交易电量25.46亿千瓦时，成功化解了青藏地区用电紧张、陕西时段性电力偏紧、“三华”地区电力供应不足等问题，全面保障电网供需平衡、促进新能源消纳。'
    s = '十九大报告指出，当前党和国家事业发生深层次、根本性的变革，我国已站在新的历史起点上,社会主要矛盾已转化为人民日益增长的美好生活需要和不平衡不充分的发展之间的矛盾。'
    s = '西北分部将积极适应新形势，坚持以电网安全运行和新能源优先消纳为己任，做好新能源调度运行相关工作，为促进国家节能减排，服务经济社会发展做出更大的贡献。'
    s = '每次网格员培训课前，专业负责人向网格员阐述业务末端融合的合理性、重要性和趋势性，并要求网格员积极转变工作角色，稳住身子、耐住性子、想出点子，保持学习热情，充分挖掘自身潜力，提高理论知识和业务技能水平，争做“一专多能”的复合型人才。'
    s = '青岛市委市政府提出，以提高经济发展质量和效益为中心，适应新常态，深入实施蓝色引领、全域统筹、创新驱动战略，深化改革扩大开放，着力保障民生，发展生态文明，加快建设宜居幸福的现代化国际城市。'
    # s='科学做好项目储备和投资安排，配电网投资要向开发区、工业园区等优质市场及新能源送出、异地扶贫搬迁项目倾斜。'
    # s='供电知音服务”的一项重要组成部分，通过定期开展座谈、联谊、交流等活动，增进政府部门、产业园区、重要客户与供电部门的“黏合度”，更加及时准确地了解掌握开发区招商引资、产业园区发展动态，及时修编电网规划，优化建设时序，科学做好项目储备和投资安排，努力实现“园区发展到哪里，电网就建设到哪里；'
    s = '公司年中工作会议是公司贯彻落实党中央、国务院决策部署，凝心聚力、攻坚克难，优质高效推进各项工作，以优异成绩迎接党的十九大胜利召开的一次重要会议。'
    s = '充分发挥同国家“一校五院”等专业机构的常态联络优势，把握研究重点，以更高站位、更严要求、更高标准，推动党建研究再出新成果、再上新台阶。'
    s = '针对当前安全稳定、优质服务和廉政建设工作面临的新形势、新任务，强调要进一步统一思想、提高认识，解决突出问题，消除风险隐患，防微杜渐、举一反三，确保公司安全健康发展。'
    s = '强化审计成果应用，定期通报，举一反三，做到发现一个问题，整改一类隐患。'
    s = '职能部门要肩负主体责任，主动思考、主动作为，确保管理更扁平。'
    s = '推进内控体系建设，解决历史遗留问题，将规范管理向站所延伸。'
    s = '进一步统一思想，深化对发展特高压电网、“三集五大”体系建设、解决历史遗留问题、当前发展形势的认识；'
    s = '科学编制培训计划，以“五大”体系建设、配电网标准、通用制度、人财物管理等为重点，集中组织培训，提高干部员工履职能力。'
    s = '总部九个部门围绕电网发展诊断分析、电网施工检修能力和队伍建设、电网运行与管理、“三集五大”体系建设、主多分开、集体企业清产核资、加强农电有关工作、供电营业区及自备电厂管理、制度标准职责一体化建设、内控机制建设等作了10个专题报告，有关部门和单位分别作了专题汇报和大会发言。'
    s = '持续深化“大检修”体系建设，有序推进市县运维业务一体化和输电通道运维属地化，着力提高运维效率。'
    s = '与会代表结合当前企业管理面临的形势和任务，就深化标准化体系建设和推广应用等重点难点问题、谋划好2013年企业管理工作思路进行认真讨论，积极建言献策。'
    s = '加快公司科技创新体系建设，深入开展大电网安全与控制、新能源发电、网源协调、柔性直流、先进配电自动化等关键技术研究，确保大电网规划与运行控制技术研究等44项重大课题实现预期目标。'
    s = '加强工程在建、验收、启动、档案、工程预（结）算、竣工结算的各个过程的控制，并将工程的安全质量管理贯穿于全过程，提升改造工程的综合水平。'
    s = '２个单位、３位个人都要学习并研究（基础理论和基本技能）'
    s = '加快公司建设，管好自己的人、看好自己的门、做好自己的事、管理好自己的人，职能部门要肩负主体责任，主动思考、主动作为，确保管理更扁平。'
    # get_phrase(s, nlp_model)
    # nlp_model = NLP_MODEL()
    #
    # get_phrase(s, nlp_model)
    # rootdir = "/home/luo/PycharmProjects/AI_Writter/files/source/国网公司新闻/test"
    #
    # filelist = os.listdir(rootdir)
    #
    # for i in range(0, len(filelist)):
    #     path = os.path.join(rootdir, filelist[i])
    #     if os.path.isfile(path):
    #         print(filelist[i])
    #         setence = Utils.readFile(path)
    #         for s in setence:
    #             get_phrase(s, nlp_model)

    # setence = Utils.readFile("/home/luo/PycharmProjects/AI_Writter/files/source/国网公司新闻/test/国网青海电力国网公司系统 2017年年中工作会议优秀报告.docx_1.txt")
    #
    # for s in setence:
    #     get_phrase(s, nlp_model)
