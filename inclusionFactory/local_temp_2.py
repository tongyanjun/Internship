# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 18:15:15 2019

@author: ychu4
"""

import os
from flask import Flask, request, jsonify
import requests
import json
import base64
#from cfenv import AppEnv
# import pyhdb
import pulp
#import xlrd
import numpy as np
import math
from math import isnan
import json
import pandas as pd
import time
import copy

###读取本地文件 
f = open("Test Data.txt",encoding = "utf-8-sig")
line = f.readlines()
f.close()
responseText = line[0]

###主程序
def lower_bound(order,j): #计算某种产品的最低产量要求,这里order是dataframe，而j是product id字符串
    #product_name = "Product" + str.upper(j) #因为数据库中的名字是ProductA之类的
    order_j = []
    for i in range(len(order)):
        if order["product_id"][i] == j:
            order_j.append([order["quantity"][i],order["days"][i]])
    low = 0
    for i in order_j:
        if (float(i[0]) != 0) & (float(i[1]) != 0):
            low += float(i[0])/float(i[1])
    return low

def upper_bound(order,j):
    #product_name = "Product" + str.upper(j) #因为数据库中的名字是ProductA之类的
    order_j = []
    for i in range(len(order)):
        if order["product_id"][i] == j:
            order_j.append([order["quantity"][i],order["days"][i]])
    up = 0
    total = 0
    for i in order_j :
        if (float(i[0]) != 0) & (float(i[1]) != 0):
            up += 4*float(i[0])/float(i[1]) #四倍是较为合理的，如果一天预计产能超过了4倍，就会对原材料造成影响
            total += float(i[0])
    out = max(up,total*1.1,3000)
    return out


def problem_des(responseText):
    #conn = get_connection()
    #efficiency = get_efficiency(conn) #注意数据结构，需要更改
    try:
        if responseText.startswith(u'\ufeff'):
            responseText = responseText.encode('utf8')[3:].decode('utf8') 
        data = json.loads(responseText,encoding = "UTF-8")
    except:
        if responseText.startswith(u'\ufeff'):
            responseText = responseText.encode('utf8')[3:].decode('utf8') 
        data = responseText
    efficiency = pd.DataFrame(data["output"])
    order = pd.DataFrame(data["plan"])
    eff = pd.DataFrame(efficiency,index = list(map(int,np.linspace(0,len(efficiency),len(efficiency),endpoint = False).tolist())))
    eff.columns = ["output","date","product_id","project_id","worker_id"]
    #order = get_order(conn)
    order.index = list(map(int,np.linspace(0,len(order),len(order),endpoint = False).tolist()))
    #以前的order.columns = ["order_id","project_id","project_name","product_id","product_name","delivery_quan","delivery_date","total_output","quantity","days","create_date","change_date"]
    if (len(order.columns) == 12):
        order.columns = ["change_date","create_date","days","delivery_date","delivery_quan","order_id","product_id","product_name","project_id","project_name","quantity","total_output"]
    elif (len(order.columns) == 13):
        order.columns = ["change_date","checked","create_date","days","delivery_date","delivery_quan","order_id","product_id","product_name","project_id","project_name","quantity","total_output"]
    else:
        pass
    order = order.dropna(axis = 0, how = "any") #防止出现df中有nan
    #需要注意在order中可能出现天数为0的情况，需要判断一下然后改成1
    for i in range(0,len(order["days"])):
        if int(order["days"][i]) <= 0:
            order["days"][i] = 1
        else:
            pass

    m_num = len(eff["worker_id"].drop_duplicates(keep = "first"))
    n_num = len(order["product_id"].drop_duplicates(keep = "first"))
    s_num = 4 #每天有四个shift，当然也可以有所改变，但那样也会导致单个shift时间增长
    worker = sorted(eff["worker_id"].drop_duplicates(keep = "first"))
    product = sorted(order["product_id"].drop_duplicates(keep = "first"))
    worker_efficiency = np.zeros([m_num,n_num],dtype = np.float)  #后续把他改成用最近20次的
    for i in range(m_num):
        for j in range(n_num):
            worker_i = eff[eff["worker_id"] == worker[i]]
            mean = np.mean(list(map(float,worker_i[worker_i["product_id"] == product[j]]["output"].tolist())))
            worker_efficiency[i][j] = mean
    #有可能会出现因为数据不存在而导致的nan出现，故将nan替换为0，也就是默认该工人不会此种工作
    for i in range(m_num):
        for j in range(n_num):
            if isnan(worker_efficiency[i,j]) == True:
                worker_efficiency[i,j] = 0
            else:
                pass
    qualified_worker = []
    for i in range(m_num):
        if sum(worker_efficiency[i,:] == 0) < n_num:
            qualified_worker.append(i)
    
    worker_new = []
    for i in qualified_worker:
        worker_new.append(worker[i])
    worker_efficiency_new = worker_efficiency[qualified_worker,:]
    m_num_new = len(worker_new)
    procedure = pd.DataFrame(data["pp"])
    procedure.columns = ["product_id","project_id","step"]
    project = order["project_id"].drop_duplicates(keep = "first")
    
    return worker_efficiency_new,order,m_num_new,n_num,s_num,worker_new,product,procedure,project



#第一种排班方式，让在岗员工最快的完成当日最低产量要求
def init1(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project):
    ###问题定义
    #变量
    variables = np.array([pulp.LpVariable('x%d_%d_%d'%(i,j,k), lowBound = 0, upBound = 1,cat = pulp.LpInteger) 
    for i in range(0, m_num) for j in range(0, s_num)  for k in range(0,n_num)]) #每个工人每天至多4个shift

    #目标函数
    z = sum(np.random.randint(1,2,m_num*s_num*n_num) * variables)

    #约束条件
    constraints = [] #用来存储限制条件
    res = [] #用来记录每个工人的总班次
    
    #约束条件0 每人每个shift只能有一项工作
    for j in range(s_num):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= 1
            constraints.append(constraint_k)
            
    #约束条件0.1 每一个人工作尽量向前放
    for j in range(s_num-1):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            b = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
                b[i,j+1,k] = 1
            constraint_k = sum(a.flatten()*variables) >= sum(b.flatten()*variables)
            constraints.append(constraint_k)
            
    #约束条件0.2 每一个shift的每一个project并行数量不超过工位上限
    for j in range(s_num):
        for k in range(n_num):
            # 找出该product所属的project的工位上限
            limit = int(procedure[procedure["product_id"] == product[k]]["limit"])
            a = np.zeros([m_num, s_num, n_num])
            for i in range(m_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= limit
            constraints.append(constraint_k)

    #约束条件1 保证当日所有产品的产量超过最低要求
    for k in range(n_num):
        low = lower_bound(order,product[k])
        ek = [] #工人生产产品j的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        for i in range(m_num):
            for j in range(s_num):
                a[i,j,k] = ek[i]
        constraint_k = 2*sum(a.flatten()*variables) >= low
        constraints.append(constraint_k)

    #约束条件2 保证当日所有的商品产量不超过我们设置的上限
    for k in range(n_num):
        up = upper_bound(order,product[k])
        if up >= 2000:
            ek = [] #工人生产产品j的效率
            for i in range(m_num):
                ek.append(worker_efficiency[i][k])
            a = np.zeros([m_num,s_num,n_num])
            for i in range(m_num):
                for j in range(s_num):
                    a[i,j,k] = ek[i]
            constraint_k = 2*sum(a.flatten()*variables) <= up
            constraints.append(constraint_k)
        else:
            ek = [] #工人生产产品j的效率
            for i in range(m_num):
                ek.append(worker_efficiency[i][k])
            a = np.zeros([m_num,s_num,n_num])
            for i in range(m_num):
                for j in range(s_num):
                    a[i,j,k] = ek[i]
            constraint_k = 2*sum(a.flatten()*variables) <= 2000
            constraints.append(constraint_k)
    
    #约束条件3 每个工人每天的shift总数不得超过4
    for i in range(m_num):
        a = np.zeros([m_num,s_num,n_num])
        for j in range(s_num):
            for k in range(n_num):
                a[i,j,k] = 1
        res.append(sum(a.flatten()*variables))
        constraint_k = sum(a.flatten()*variables) <= 4
        constraints.append(constraint_k)
    
    #约束条件4 每个工人工作的shift总数不会相差超过1
    for i in range(m_num):
        for j in range(i+1,m_num):
            constraint_i = (res[i] - res[j]) >= 0
            constraints.append(constraint_i)
            constraint_i = (res[i] - res[j]) <= 0
            constraints.append(constraint_i)
    
    #约束条件5 保证在每一个shift，每个工序有足够的工人工作，先头工序的产能略大于后续的产能
    #我们先以字典形式储存各个shift的各个产品的产能
    shift1 = {}
    shift2 = {}
    shift3 = {}
    shift4 = {}
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift1[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift2[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift3[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift4[product[k]] = sum(a.flatten()*variables)
    
    #然后根据定义的procedure找出各个project的工序，并加入限制条件
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift1[j] + exceed_output >= shift1[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift2[j] + exceed_output >= shift2[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift3[j] + exceed_output >= shift3[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift4[j] + exceed_output >= shift4[k]
                    constraints.append(constraint_k)
        
    
    return z,constraints

#第一种排班方式的求解函数
def solve_ilp1(z, constraints):
    """
    求解问题
    """
    prob = pulp.LpProblem('LP', pulp.LpMinimize) #这里是为了最快产出的排班，故使用LpMinimize
    prob += z
    for cons in constraints:
        prob += cons
    #print(prob) #如果想查看具体的表达式可以print
    status = prob.solve()
    if status != 1:
        return None
    else:
        return [[v,v.varValue.real] for v in prob.variables()]


#第二种排班方式，要求在完成所有产品当日最低产量的前提下，均衡的进行所有产品的最大产出
def init2(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project):
    ###问题定义
    #变量
    variables = np.array([pulp.LpVariable('x%d_%d_%d'%(i,j,k), lowBound = 0, upBound = 1,cat = pulp.LpInteger) 
    for i in range(0, m_num) for j in range(0, s_num)  for k in range(0,n_num)]) #每个工人每天至多4个shift

    #目标函数
    z = 0
    for k in range(n_num):
        #low = lower_bound(order,product[k])
        ek = [] #工人生产产品j的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        for i in range(m_num):
            for j in range(s_num):
                a[i,j,k] = ek[i]
        reward = 2*sum(a.flatten()*variables)
        z += reward
        #if low != 0:
        #    z += (reward-low)/low
        #else:
        #    z += 0
            
    #约束条件
    constraints = [] #用来存储限制条件
    res = [] #用来记录每个工人的总班次
    
    #约束条件0 每人每个shift只能有一项工作
    for j in range(s_num):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= 1
            constraints.append(constraint_k)
            
    #约束条件0.1 每一个人工作尽量向前放
    for j in range(s_num-1):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            b = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
                b[i,j+1,k] = 1
            constraint_k = sum(a.flatten()*variables) >= sum(b.flatten()*variables)
            constraints.append(constraint_k)

    #约束条件0.2 每一个shift的每一个project并行数量不超过工位上限
    for j in range(s_num):
        for k in range(n_num):
            # 找出该product所属的project的工位上限
            limit = int(procedure[procedure["product_id"] == product[k]]["limit"])
            a = np.zeros([m_num, s_num, n_num])
            for i in range(m_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= limit
            constraints.append(constraint_k)
            
    #约束条件1 保证当日所有产品的产量超过最低要求
    for k in range(n_num):
        low = lower_bound(order,product[k])
        ek = [] #工人生产产品j的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        for i in range(m_num):
            for j in range(s_num):
                a[i,j,k] = ek[i]
        constraint_k = 2*sum(a.flatten()*variables) >= low
        constraints.append(constraint_k)

    #约束条件2 保证当日所有的商品产量不超过我们设置的上限
    #for k in range(n_num):
    #    up = upper_bound(order,product[k])
    #    if up >= 2000:
    #        ek = [] #工人生产产品j的效率
    #        for i in range(m_num):
    #            ek.append(worker_efficiency[i][k])
    #        a = np.zeros([m_num,s_num,n_num])
    #        for i in range(m_num):
    #            for j in range(s_num):
    #                a[i,j,k] = ek[i]
    #        constraint_k = 2*sum(a.flatten()*variables) <= up
    #        constraints.append(constraint_k)
    #    else:
    #        ek = [] #工人生产产品j的效率
    #        for i in range(m_num):
    #            ek.append(worker_efficiency[i][k])
    #        a = np.zeros([m_num,s_num,n_num])
    #        for i in range(m_num):
    #            for j in range(s_num):
    #                a[i,j,k] = ek[i]
    #        constraint_k = 2*sum(a.flatten()*variables) <= 2000
    #        constraints.append(constraint_k)
    
    #约束条件3 每个工人每天的shift总数不得超过4
    for i in range(m_num):
        a = np.zeros([m_num,s_num,n_num])
        for j in range(s_num):
            for k in range(n_num):
                a[i,j,k] = 1
        res.append(sum(a.flatten()*variables))
        constraint_k = sum(a.flatten()*variables) <= 4
        constraints.append(constraint_k)
    
    #约束条件4 每个工人工作的shift总数不会相差超过1
    for i in range(m_num):
        for j in range(i+1,m_num):
            constraint_i = (res[i] - res[j]) >= 0
            constraints.append(constraint_i)
            constraint_i = (res[i] - res[j]) <= 0
            constraints.append(constraint_i)
    
    #约束条件5 保证在每一个shift，每个工序有足够的工人工作，先头工序的产能略大于后续的产能
    #我们先以字典形式储存各个shift的各个产品的产能
    shift1 = {}
    shift2 = {}
    shift3 = {}
    shift4 = {}
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift1[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift2[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift3[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift4[product[k]] = sum(a.flatten()*variables)
    
    #然后根据定义的procedure找出各个project的工序，并加入限制条件
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift1[j] + exceed_output >= shift1[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift2[j] + exceed_output >= shift2[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift3[j] + exceed_output >= shift3[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift4[j] + exceed_output >= shift4[k]
                    constraints.append(constraint_k)
        
    
    
    return z,constraints

#第二种排班方式的求解函数
def solve_ilp2(z, constraints):
    """
    求解问题
    """
    prob = pulp.LpProblem('LP', pulp.LpMaximize)
    prob += z
    for cons in constraints:
        prob += cons
    #print(prob)
    status = prob.solve()
    if status != 1:
        return None
    else:
        return [[v,v.varValue.real] for v in prob.variables()]


#地三种排班方式，在完成当日最低产量的前提下，让每个工人在一天内都至少进行两种不同的工作
def init3(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project):
    ###问题定义
    #变量
    variables = np.array([pulp.LpVariable('x%d_%d_%d'%(i,j,k), lowBound = 0, upBound = 1,cat = pulp.LpInteger) 
    for i in range(0, m_num) for j in range(0, s_num)  for k in range(0,n_num)]) #每个工人每天至多4个shift

    #目标函数
    z = 0
    for k in range(n_num):
        #low = lower_bound(order,product[k])
        ek = [] #工人生产产品j的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        for i in range(m_num):
            for j in range(s_num):
                a[i,j,k] = ek[i]
        reward = 2*sum(a.flatten()*variables)
        z += reward
        #if low != 0:
        #    z += (reward-low)/low
        #else:
        #    z += 0

    #约束条件
    constraints = [] #用来存储限制条件
    res = [] #用来记录每个工人的总班次
    
    #约束条件0 每人每个shift只能有一项工作
    for j in range(s_num):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= 1
            constraints.append(constraint_k)
            
    #约束条件0.1 每一个人工作尽量向前放
    for j in range(s_num-1):
        for i in range(m_num):
            a = np.zeros([m_num,s_num,n_num])
            b = np.zeros([m_num,s_num,n_num])
            for k in range(n_num):
                a[i,j,k] = 1
                b[i,j+1,k] = 1
            constraint_k = sum(a.flatten()*variables) >= sum(b.flatten()*variables)
            constraints.append(constraint_k)

    #约束条件0.2 每一个shift的每一个project并行数量不超过工位上限
    for j in range(s_num):
        for k in range(n_num):
            # 找出该product所属的project的工位上限
            limit = int(procedure[procedure["product_id"] == product[k]]["limit"])
            a = np.zeros([m_num, s_num, n_num])
            for i in range(m_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <= limit
            constraints.append(constraint_k)
            
    #约束条件1 保证当日所有产品的产量超过最低要求
    for k in range(n_num):
        low = lower_bound(order,product[k])
        ek = [] #工人生产产品j的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        for i in range(m_num):
            for j in range(s_num):
                a[i,j,k] = ek[i]
        constraint_k = 2*sum(a.flatten()*variables) >= low
        constraints.append(constraint_k)

    #约束条件2 保证当日所有的商品产量不超过我们设置的上限
    #for k in range(n_num):
    #    up = upper_bound(order,product[k])
    #    if up >= 2000:
    #        ek = [] #工人生产产品j的效率
    #        for i in range(m_num):
    #            ek.append(worker_efficiency[i][k])
    #        a = np.zeros([m_num,s_num,n_num])
    #        for i in range(m_num):
    #            for j in range(s_num):
    #                a[i,j,k] = ek[i]
    #        constraint_k = 2*sum(a.flatten()*variables) <= up
    #        constraints.append(constraint_k)
    #    else:
    #        ek = [] #工人生产产品j的效率
    #        for i in range(m_num):
    #            ek.append(worker_efficiency[i][k])
    #        a = np.zeros([m_num,s_num,n_num])
    #        for i in range(m_num):
    #            for j in range(s_num):
    #                a[i,j,k] = ek[i]
    #        constraint_k = 2*sum(a.flatten()*variables) <= 2000
    #        constraints.append(constraint_k)
    
    #约束条件3 每个工人每天的shift总数不得超过4
    for i in range(m_num):
        a = np.zeros([m_num,s_num,n_num])
        for j in range(s_num):
            for k in range(n_num):
                a[i,j,k] = 1
        res.append(sum(a.flatten()*variables))
        constraint_k = sum(a.flatten()*variables) <= 4
        constraints.append(constraint_k)
    
    #约束条件4 每个工人工作的shift总数不会相差超过1
    for i in range(m_num):
        for j in range(i+1,m_num):
            constraint_i = (res[i] - res[j]) >= -1
            constraints.append(constraint_i)
            constraint_i = (res[i] - res[j]) <= 1
            constraints.append(constraint_i)
    
    #约束条件5 保证在每一个shift，每个工序有足够的工人工作，先头工序的产能略大于后续的产能
    #我们先以字典形式储存各个shift的各个产品的产能
    shift1 = {}
    shift2 = {}
    shift3 = {}
    shift4 = {}
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift1[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift2[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift3[product[k]] = sum(a.flatten()*variables)
    for k in range(n_num):
        ek = [] #工人生产产品k的效率
        for i in range(m_num):
            ek.append(worker_efficiency[i][k])
        a = np.zeros([m_num,s_num,n_num])
        j = 0
        for i in range(m_num):
            a[i,j,k] = ek[i]
        shift4[product[k]] = sum(a.flatten()*variables)
    
    #然后根据定义的procedure找出各个project的工序，并加入限制条件
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift1[j] + exceed_output >= shift1[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift2[j] + exceed_output >= shift2[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift3[j] + exceed_output >= shift3[k]
                    constraints.append(constraint_k)
    
    for p in project:
        procedure_p = procedure[procedure["project_id"]==p]
        for i in range(len(procedure_p)-1):
            product_1 = list(procedure_p[procedure_p["step"] == str(i+1)]["product_id"])
            product_2 = list(procedure_p[procedure_p["step"] == str(i+2)]["product_id"])
            for j in product_1:
                for k in product_2:
                    order_j = order[(order["product_id"] == j) & (order["project_id"] == p)]
                    order_k = order[(order["product_id"] == k) & (order["project_id"] == p)]
                    exceed_output = (sum(list(order_j["total_output"])) - sum(list(order_k["total_output"])))/4
                    constraint_k = shift4[j] + exceed_output >= shift4[k]
                    constraints.append(constraint_k)
        
    ##约束条件6 每一个工人每天至少从事两种以上的工作，也就是指每一个工作每天不超过3个shift，即便如此会出现3个一样工作+1个空闲，也不为被我们的初始愿望
    for i in range(m_num):
        for k in range(n_num):
            a = np.zeros([m_num,s_num,n_num])
            for j in range(s_num):
                a[i,j,k] = 1
            constraint_k = sum(a.flatten()*variables) <=3
            constraints.append(constraint_k)
    
    return z,constraints
#地三种排班方式的求解函数
def solve_ilp3(z, constraints):
    """
    求解问题
    """
    prob = pulp.LpProblem('LP', pulp.LpMaximize)
    prob += z
    for cons in constraints:
        prob += cons
    #print(prob)
    status = prob.solve()
    if status != 1:
        return None
    else:
        return [[v,v.varValue.real] for v in prob.variables()]

def result_trans(res, m_num, n_num, s_num, worker_efficiency, product, worker,order):
    wh = np.zeros([m_num,s_num,n_num])
    for v in res:
        wh[int(str(v[0]).replace('x','').split('_')[0])][int(str(v[0]).replace('x','').split('_')[1])][int(str(v[0]).replace('x','').split('_')[2])]= v[1]
    # wh = np.array(res).reshape(m_num,n_num)
    hpp = np.zeros([m_num,n_num]) #每一行代表每个工人当日在每个comp上的shift总数
    for i in range(m_num):
        hpp[i] = wh[i].sum(axis = 0)
    hpps = hpp.sum(axis = 1) #每个元素代表每个工人当日的总shift数
    worker_output = np.zeros([m_num,n_num])
    for i in range(m_num):
        worker_output[i] = hpp[i]*np.array(worker_efficiency[i])*2
    producted = worker_output.sum(axis = 0)
    low = np.zeros(n_num)
    for i in range(n_num):
        low[i]  = math.floor(lower_bound(order,product[i]))
    up = np.zeros(n_num)
    for i in range(n_num):
        up[i] = math.ceil(upper_bound(order,product[i]))
    res2 = pd.DataFrame(res, columns = ["var","value"])
    output = {}
    for i in worker:
        index = np.argwhere(np.array(worker) == i).tolist()[0][0]
        seq = np.arange(index*s_num*n_num,(index+1)*s_num*n_num) #该工人的当天变量
        temp = []
        for j in range(s_num):
            temp1 = seq[np.arange(j*n_num,(j+1)*n_num)]
            temp2 = (res2["value"][temp1]).tolist()
            temp.append(temp2)
        output[i] = copy.deepcopy(temp)

    output2 = np.zeros([m_num,s_num]).tolist()
    for i in range(len(output)):
        for j in range(len(output[list(output.keys())[i]])):
            if len(np.argwhere(np.array(output[list(output.keys())[i]][j]) == 1)) == 0:
                pass
            else:
                a = np.argwhere(np.array(output[list(output.keys())[i]][j]) == 1)[0][0]
                output2[i][j] = product[a]
    
    output3 = copy.deepcopy(output)
    for i in range(len(output3)):
        output3[list(output3.keys())[i]] = output2[i]    
    estimated_output = {}
    for i in range(len(product)):
        estimated_output[product[i]] = producted[i]    
        
    #estimated_duration_product = {}
    #for i in range(len(product)):
    #    if sum(list(order[order["product_id"] == product[i]]["quantity"])) > 0:
    #        estimated_duration_product[product[i]] = math.ceil(sum(list(order[order["product_id"] == product[i]]["quantity"]))/estimated_output[product[i]])
    #    else:
    #        estimated_duration_product[product[i]] = 0
    
    order_id = order["order_id"].drop_duplicates(keep = "first")
    estimated_duration = {}
    for i in order_id:
        order_i = order[order["order_id"] == i]
        order_i_duration = 0
        for j in range(len(order_i)):
            pro_temp = list(order_i["product_id"])[j]
            a = float(list(order_i["quantity"])[j])/estimated_output[pro_temp]
            if (a != np.inf) & (a > 0):
                order_i_duration = max(order_i_duration, math.ceil(a))
            else:
                pass
        if order_i_duration >= 99999:
            order_i_duration = "Infinity"
        estimated_duration[i] = order_i_duration
    
    real_output = json.dumps({"assignment":output3,"estimated output":estimated_output,"total shifts":hpps.sum(),
                               "working load":float('%.2f' % (100*hpps.sum()/(4*m_num))),"estimated duration":estimated_duration})    
    
    return real_output 


###运行部分
worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project = problem_des(responseText)
z1,constraints1 = init1(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project)
res1 = solve_ilp1(z1, constraints1)
if res1 != None:
    real_output1 = result_trans(res1, m_num, n_num, s_num, worker_efficiency, product, worker, order)
else:
    order_id = order["order_id"].drop_duplicates(keep = "first")
    estimated_duration = {}
    estimated_output_temp = {}
    for i in range(n_num):
        estimated_output_temp[product[i]] = sum(worker_efficiency[:,i])*(4/len(order))
        
    for i in order_id:
        order_i = order[order["order_id"] == i]
        order_i_duration = 0
        for j in range(len(order_i)):
            pro_temp = list(order_i["product_id"])[j]
            a = float(list(order_i["quantity"])[j])/estimated_output_temp[pro_temp]
            if (a != np.inf) & (a > 0):
                order_i_duration = max(order_i_duration, math.ceil(a))
            else:
                pass
        if order_i_duration >= 99999:
            order_i_duration = "Infinity"
        estimated_duration[i] = order_i_duration
    real_output1 = json.dumps({"assignment":"No feasible solution","estimated duration":estimated_duration})
    
    
z2,constraints2 = init2(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project)
res2 = solve_ilp2(z2, constraints2)
if res2 != None:
    real_output2 = result_trans(res2, m_num, n_num, s_num, worker_efficiency, product, worker, order)
else:
    order_id = order["order_id"].drop_duplicates(keep = "first")
    estimated_duration = {}
    estimated_output_temp = {}
    for i in range(n_num):
        estimated_output_temp[product[i]] = sum(worker_efficiency[:,i])*(4/len(order))
        
    for i in order_id:
        order_i = order[order["order_id"] == i]
        order_i_duration = 0
        for j in range(len(order_i)):
            pro_temp = list(order_i["product_id"])[j]
            a = float(list(order_i["quantity"])[j])/estimated_output_temp[pro_temp]
            if (a != np.inf) & (a > 0):
                order_i_duration = max(order_i_duration, math.ceil(a))
            else:
                pass
        if order_i_duration >= 99999:
            order_i_duration = "Infinity"
        estimated_duration[i] = order_i_duration
    real_output2 = json.dumps({"assignment":"No feasible solution","estimated duration":estimated_duration})
    
    
    
z3,constraints3 = init3(worker_efficiency,order,m_num,n_num,s_num,worker,product,procedure,project)
res3 = solve_ilp3(z3, constraints3)
if res3 != None:
    real_output3 = result_trans(res3, m_num, n_num, s_num, worker_efficiency, product, worker, order)
else:
    order_id = order["order_id"].drop_duplicates(keep = "first")
    estimated_duration = {}
    estimated_output_temp = {}
    for i in range(n_num):
        estimated_output_temp[product[i]] = sum(worker_efficiency[:,i])*(4/len(order))
    for i in order_id:
        order_i = order[order["order_id"] == i]
        order_i_duration = 0
        for j in range(len(order_i)):
            pro_temp = list(order_i["product_id"])[j]
            a = float(list(order_i["quantity"])[j])/estimated_output_temp[pro_temp]
            if (a != np.inf) & (a > 0):
                order_i_duration = max(order_i_duration, math.ceil(a))
            else:
                pass
        if order_i_duration >= 99999:
            order_i_duration = "Infinity"
        estimated_duration[i] = order_i_duration
    real_output3 = json.dumps({"assignment":"No feasible solution","estimated duration":estimated_duration})
    
print(real_output1)
print(real_output2)
print(real_output3)