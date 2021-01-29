import random
import time


def random_walk_1(left,right,walk_num):
    for i in range(walk_num):
        z = random.randint(0, 1)
        if z == 0:
            z = -1
        right+=z
        if left==right:
            print("\nsuccessful   ",i)
            return i
            break
        x = right//2 * "_"
        print("\r  A{}B".format(x), end='')
        time.sleep(0.001)
    print("\nfailed   ",right)
    return -1


def random_walk_2(left,right,walk_num):
    for i in range(walk_num):
        z = random.randint(0, 1)
        if z == 0:
            z = -1
        right+=z
        k = random.randint(0, 1)
        if k == 0:
            k = -1
        left += k
        if left>=right:
            print("successful   ",i)
            return i
            break
    print("failed   ",left ," -> ",right)
    return -1

left=0
right=200
walk_num=1000000




succ_cishu=0
sum_walk=0
experiment_num=1
for x in range(experiment_num):
    k=random_walk_1(left,right,walk_num)
    if k!=-1:

        succ_cishu+=1
        sum_walk+=k
print("Random_walk_1:")
print("成功次数:  ",succ_cishu)
print("平均步数:  ",sum_walk)
print("失败次数:  ",experiment_num-succ_cishu)
