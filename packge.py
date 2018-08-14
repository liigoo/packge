# coding = utf-8


from flask import Flask
from flask import Response
from flask import request
from flask_cors import *
import re
import pymysql
import pymysql.cursors
import urllib.parse
from bs4 import BeautifulSoup
import requests
import json
import hashlib
import random
import datetime
from time import sleep


# 主程序，抓大红包
###############################################
class Main:
    def __init__(self):

        self.url = ''
        self.query = ''
        self.group_sn = ''
        self.phone = ''
        self.token = ''
        self.valid = ''
        self.error = 0
        self.request_times = 0
        self.lucky_num = 0
        self.times = 0  # 抢包总次数
        self.try_times = 0  # 小包
        self.last_times = 0  # 大包
        self.large = 0  # 最终大包
        self.surplus_times = 0  # 用户剩余可抢红包次数
        self.conn = ''
        self.message = ''
        self.end_while = False  # 验证抢包结束
        self.request_from = False  # 检查请求来源, 默认代理接口
        self.user_from = 0

    def get_data(self):

        if request.method == 'POST':
            # 初始化数据库
            self.conn = self.conn_db()
            # 获取必填信息
            post_phone = str(request.form['phone'])
            post_url = str(request.form['url'])
            post_token = str(request.form['token'])
            post_from = str(request.form['request_from'])
            post_valid = str(request.form['valid'])

            self.phone = self.check_post_data(post_phone, 'phone')
            self.url = self.check_post_data(post_url, 'url')
            self.token = self.check_post_data(post_token, 'token', post_phone)
            self.request_from = self.check_post_data(post_from, 'request_from')
            # 截取url必要信息
            self.query = self.get_url_data()
            # 验证token, token不受其他因素影响，提前校验
            if not self.token:
                return self.message
            # 获取注册码（可为空）
            self.valid = post_valid
            valid_type = self.check_post_data(self.valid, 'valid')
            # 验证 valid code 1、注册码不为空且真实存在，2、注册码为空
            if valid_type:
                self.check_valid_code(self.valid)
            else:
                # 开始运行
                self.begin()
            # 关闭数据库
            self.die()
        # 返回message到前端
        return self.message

    def begin(self, num=0):
        # 全局变量 rise 控制循环
        global rise

        # 检验传入参数
        if self.phone == '' or not self.url:
            return

        # 插入用户信息
        if not self.get_user_info(False):
            return

        # 插入url信息
        if not self.post_url_info(False):
            return

        # 如果连续3次请求失败 跳出循环（有可能是系统出问题了）
        if self.error > 1 or self.times > 1:
            self.output_json({"errorCode": "10010", "msg": "Too many bad requests"})
            return

        # lucky_num 获取链接里面第几个是大包
        try:
            self.lucky_num = int(self.query['lucky_number'])
        except:
            self.output_json({'errorCode': '10015', 'msg': 'Url type error'})
            return

        if self.lucky_num == '' or self.lucky_num > 10 or self.lucky_num < 5:
            self.output_json({'errorCode': '10015', 'msg': 'Url type error'})
            return

        rise = self.lucky_num * 4
        try_num = self.lucky_num
        if self.times == 0:
            self.do_check(try_num)
        else:
            # 计算循环，如果获取cookie/header/phone失败就再请求一次 rise += num
            rise += num
            self.do_check(try_num)
        self.times += 1

    def do_check(self, try_num):

        # 如果请求失败 跳出循环
        if self.request_times >= 1:
            self.output_json({"errorCode": "10010", "msg": "Too many bad requests"})
            return

        global rise
        while try_num != 0 and not self.end_while:

            # 获取cookie phone header
            cookie = self.cookie_to_data()
            phone = self.get_phone_list()
            header = self.get_header()

            # 如果从数据库及文件获取参数失败，循环次数+1
            if cookie == '' or phone == '' or header == '':
                self.begin(1)
                break

            if try_num == 1:
                try:
                    # 用真实手机号码开抢
                    action = self.request_action(self.phone, header, cookie)
                    self.last_times = action['big_package']
                    self.large = action['big_number']
                    self.try_times = action['small_package']

                    # 判断大包是否出现
                    if self.last_times == 1 and self.try_times == self.lucky_num - 1:
                        self.surplus_times -= 1
                        self.output_json(
                            {'errorCode': '0', 'msg': 'Success', 'user': self.phone, 'large_num': self.large,
                             'surplus_times': self.surplus_times})
                        # 更新用户surplus times
                        self.get_user_info(True)
                        self.post_url_info(True)
                        self.end_while = True
                        break

                    # 确定是大包，没抢成功再抢一次
                    elif self.last_times == 0 and self.try_times == self.lucky_num - 1:
                        self.request_times += 1
                        self.do_check(1)
                        break

                    # 确定有大包出现了，但是小包出现次数大于lucky_num，说明已经被抢过了
                    elif self.last_times == 1 and self.try_times >= self.lucky_num:
                        self.post_url_info(True)
                        self.output_json({"errorCode": "10009", "msg": "A used lucky package"})
                        self.do_check(0)
                        self.end_while = True
                        break
                except:
                    self.do_check(1)
                    break
            else:
                action = self.request_action(phone, header, cookie)
                self.last_times = action['big_package']
                self.large = action['big_number']
                # 抢的小包次数
                self.try_times = action['small_package']

                # 确定小包出现次数大于try_num，说明已经被抢过了
                if int(self.try_times) > try_num or self.large > 4 or self.last_times > 0:
                    self.post_url_info(True)
                    self.output_json({"errorCode": "10009", "msg": "A used lucky package"})
                    self.do_check(0)
                    break

                # 为了保险，在下一个是大包的时候直接跳出循环
                if int(self.try_times) == self.lucky_num - 1:
                    self.do_check(1)
                    break

            # 循环计数器 防止死循环
            rise -= 1
            if rise == 0:
                self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "count"})
                self.do_check(0)
                break

    def conn_db(self):
        try:
            conn = pymysql.connect(host='localhost', user='root', password='aaabbbccc', db='packge', port=3306,
                                   charset='utf8')
            return conn
        except:
            return False

    def die(self):
        self.conn.close()

    def request_action(self, phone, header, cookie):

        # 解析cookie里面snsInfo数据
        try:
            cookie_dic = json.loads(cookie.split(';')[3].split('=')[1])
        except:
            return
        sleep_time = 0
        blind_url = 'https://h5.ele.me/restapi/v1/weixin/' + cookie_dic['openid'] + '/phone'
        lucky_url = 'https://h5.ele.me/restapi/marketing/promotion/weixin/' + cookie_dic['openid']
        blind_data = {
            'sign': cookie_dic['eleme_key'],
            'method': 'phone',
            'phone': str(phone),
        }

        avater = cookie_dic['avatar']
        user_name = phone[:3] + '*' * 4 + phone[7:9]
        sleep(0.1)
		
        request_data = {
            'device_id': self.query['device_id'],
            'group_sn': self.query['sn'],
            'hardware_id': self.query['hardware_id'],
            'method': 'phone',
            'phone': str(phone),
            'platform': self.query['platform'],
            'refer_user_id': self.query['refer_user_id'],
            'sign': cookie_dic['eleme_key'],
            'track_id': self.query['track_id'],
            'unionid': 'fuck',
            'theme_id': self.query['theme_id'],
            'weixin_avatar': avater,
            'weixin_username': user_name,
        }

        # 两个不同请求分开放
        try:
            get_post_result = requests.post(lucky_url, data=json.dumps(request_data), headers=header).text
            sleep(sleep_time)
        except:
            get_post_result = False
            self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "post"})

        try:
            # sleep(3)
            get_put_result = requests.put(blind_url, data=json.dumps(blind_data), headers=header).text
            soup_1 = BeautifulSoup(get_put_result, 'lxml')
            soup = BeautifulSoup(get_post_result, 'lxml').p.get_text()
            soup_string = json.loads(str(soup))

            try_times = last_times = big_number = 0
            promotion_records = soup_string['promotion_records']

            for i in range(len(promotion_records)):
                if promotion_records[i]['is_lucky'] or int(promotion_records[i]['amount']) >= 4:
                    last_times += 1
                    big_number = float(promotion_records[i]['amount'])
                else:
                    try_times += 1

            return {'small_package': try_times, 'big_package': last_times, 'big_number': big_number}
        except:
            self.output_json({"errorCode": "10006", "msg": "Bad request"})
            self.error += 1
            self.begin(1)

    def get_header(self):
        ua_list = []
        fo = open('UA.txt')
        for string in fo:
            ua_list.append(string)
        fo.close()
        user_agent = ua_list[random.randint(0, len(ua_list) - 1)].replace("\n", "")
        header = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": 'keep-alive',
            "DNT": "1",
            "Host": "h5.ele.me",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
        return header

    def get_phone_list(self):

        cursor = self.conn.cursor()
        sql_str = "SELECT * FROM `packge_phone` WHERE `is_good` = 1 AND `p_times` < 600  ORDER BY `p_times` LIMIT 0,1"
        try:
            cursor.execute(sql_str)
            phone_list = cursor.fetchall()[0]
            phone = phone_list[1]
            phone_ids = phone_list[0]
        except:
            self.output_json({"errorCode": "10004", "msg": "Require phone error"})
            cursor.close()
            return

        # 更新phone使用次数
        try:
            sql_update_phone = "UPDATE `packge_phone` SET `p_times` = `p_times` + 1 WHERE id = %d" % int(phone_ids)
            cursor.execute(sql_update_phone)
        except:
            cursor.close()
            self.output_json({"errorCode": "10007", "msg": "Update phone error"})
        cursor.close()
        return phone

    def get_user_info(self, end=False):
        phone = self.phone
        large = self.large
        cursor = self.conn.cursor()
        if not end:
            try:
                sql_str = "SELECT * FROM `packge_user` WHERE `user_phone` = %d " % int(phone)

                cursor.execute(sql_str)
                is_user = cursor.fetchall()

                if is_user == '' or len(is_user) == 0:
                    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sql_str = "INSERT INTO `packge_user` (`user_phone`, `user_type`, " \
                              "`user_surplus_times`, `user_is_good`, `user_login_times`, `create_time`, `user_from`) " \
                              "VALUES ('%d', 0, 3, 1, 1, '%s', '%d')" % (
                                  int(phone), dt, int(self.user_from))

                    self.surplus_times = 3
                    cursor.execute(sql_str)
                    status = True
                else:

                    # 封禁用户规则
                    rule = self.check_bad_user(is_user)

                    if not rule:
                        self.output_json({"errorCode": "10014", "msg": "A forbid account"})
                        status = False
                    else:
                        sql_str = "UPDATE `packge_user` SET `user_login_times` = `user_login_times` + 1 WHERE `user_phone` = %d " % int(
                            phone)
                        cursor.execute(sql_str)

                        if int(is_user[0][5]) < 1:
                            self.surplus_times = is_user[0][5]
                            self.output_json({"errorCode": "10013", "msg": "No enough surplus times"})
                            status = False
                        else:
                            self.surplus_times = is_user[0][5]
                            status = True

            except:
                self.output_json({"errorCode": "10004", "msg": "Require phone error"})
                cursor.close()
                status = False
        else:
            try:
                sql_str = "UPDATE `packge_user` SET `user_surplus_times` = `user_surplus_times` - 1, `user_success_times` = `user_success_times` + 1 WHERE `user_phone` = %d " % int(
                    phone)
                dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sql_lucky_str = "INSERT INTO `packge_lucky` (`lucky_phone`,`lucky_num`,`lucky_time`) VALUES('%d','%f','%s') " % (
                    int(phone), float(large), dt)
                cursor.execute(sql_str)
                self.conn.commit()
                cursor.execute(sql_lucky_str)
                self.conn.commit()
                status = True
            except:
                # 更新信息就不提醒了
                # self.output_json({"errorCode": "10012", "msg": "Update user info error"})
                # cursor.close()
                status = False
        return status

    def post_url_info(self, end=False):

        url = self.url
        hl = hashlib.md5()
        hl.update(url.encode('utf-8'))
        hash_id = hl.hexdigest()
        cursor = self.conn.cursor()
        if not end:
            try:
                sql_str = "SELECT * FROM `packge_url` WHERE `hash_id` = '%s' " % str(hash_id)

                cursor.execute(sql_str)
                is_url = cursor.fetchall()

                if is_url == '' or len(is_url) == 0:
                    dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sql_str = "INSERT INTO `packge_url` (`hash_id`, `url`, `add_time`, `is_useful`, " \
                              "`other`) VALUES ( '%s', '%s', '%s', 1, 0)" % (str(hash_id), str(url), dt)
                    cursor.execute(sql_str)
                    status = True
                else:
                    if int(is_url[0][4]) == 0:
                        self.output_json({"errorCode": "10009", "msg": "A used lucky package"})
                        status = False
                    else:
                        status = True
            except:
                self.output_json({"errorCode": "10009", "msg": "A used lucky package"})
                cursor.close()
                status = False
        else:
            try:
                sql_str = "UPDATE `packge_url` SET `is_useful` = 0 WHERE `hash_id` = '%s' " % str(hash_id)
                cursor.execute(sql_str)
                status = True
            except:
                status = False
        return status

    def check_bad_user(self, is_user):
        # `user_success_times` < 4 AND `user_is_good` = 1 AND `user_times` = 0 AND `user_login_times` > 50 is_user[
        # 0][6]) == 0
        if is_user[0][6] == 0:
            state = False
        # is_user[0][5]: user_surplus_times < 4
        # is_user[0][6]: user_is_good == 1
        # is_user[0][7]: user_times == 0
        # is_user[0][8]: user_success_times < 4
        # is_user[0][9]: user_login_times > 40
        elif is_user[0][5] < 4 and is_user[0][6] == 1 and is_user[0][7] == 0 and is_user[0][8] < 4 and is_user[0][
            9] > 40:
            # TODO ip/datetime

            cursor = self.conn.cursor()
            sql_str = "UPDATE `packge_user` SET `user_is_good` = 0 WHERE `user_phone` = %d" % int(self.phone)
            cursor.execute(sql_str)
            state = False
        else:
            state = True

        return state

    def get_url_data(self):

        if self.url == '':
            return
        url_str = urllib.parse.urlparse(str(self.url)).fragment.split('&')
        query_name = []
        query_value = []

        for i in range(0, len(url_str)):
            try:
                query_name.append(url_str[i].split('=')[0])
                query_value.append(url_str[i].split('=')[1])
            except:
                self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "url-1"})

        query_dict = dict(zip(query_name, query_value))
        return query_dict

    # query_dict数据
    #
    # {'device_id': '',
    #  'hardware_id': '',
    #  'is_lucky_group': 'True',
    #  'lucky_number': '7',
    #  'platform': '0',
    #  'refer_user_id': '17777181',
    #  'sn': '29f0276acd2fd89b',
    #  'theme_id': '1881',
    #  'track_id': ''}

    def cookie_to_data(self):

        # 获取cookie list

        cursor = self.conn.cursor()
        sql_str = "SELECT * FROM `packge_cookies` WHERE `is_good` = 1 AND `c_times` < 600  ORDER BY `c_times` LIMIT 0,1"
        try:
            cursor.execute(sql_str)
            cookie_list = cursor.fetchall()[0]
            real_cookie = cookie_list[1]
            cookies = urllib.parse.unquote(real_cookie)
            cookie_ids = cookie_list[0]
        except:
            cursor.close()
            self.output_json({"errorCode": "10003", "msg": "Require cookies error"})
            return
        # 检查cookie格式
        try:
            # TODO ...
            json.loads(cookies.split(';')[3].split('=')[1])
        except:
            sql_update_cookie = "UPDATE `packge_cookies` SET `is_good` = 0 WHERE id = %d" % int(cookie_ids)
            cursor.execute(sql_update_cookie)
            self.conn.commit()
            cursor.close()
            return

        # 更新cookie使用次数
        try:
            sql_update_cookie = "UPDATE `packge_cookies` SET `c_times` = `c_times` + 1 WHERE id = %d" % int(cookie_ids)
            cursor.execute(sql_update_cookie)
        except:
            self.output_json({"errorCode": "10005", "msg": "Update cookie times error"})
        cursor.close()
        return cookies

    # 检查注册码，并获取相应的surplus times
    def check_valid_code(self, valid):
        if len(str(valid)) != 8:
            self.output_json({"errorCode": "10011", "msg": "Invalid or used valid code"})
            status = False
        else:
            cursor = self.conn.cursor()
            try:
                sql_str = "SELECT * FROM `packge_code` WHERE `is_good` = 1 AND `is_verification` = 0  and `valid_code` = " \
                          "%s "
                cursor.execute(sql_str, str(valid))
                valid_list = cursor.fetchall()
                if valid_list == '' or len(valid_list) == 0 or valid_list == ():
                    self.output_json({"errorCode": "10011", "msg": "Invalid valid code"})
                    status = False
                else:
                    valid_type = valid_list[0][2]
                    valid_surplus_times = valid_list[0][5]
                    self.output_json({'errorCode': '10000', 'msg': 'Success', 'user': self.phone,
                                      'valid_surplus_times': valid_surplus_times})
                    # 检查用户状态
                    sql_str = "SELECT * FROM `packge_user` WHERE `user_phone` = %d " % int(self.phone)
                    cursor.execute(sql_str)
                    is_user = cursor.fetchall()

                    if is_user == '' or len(is_user) == 0:
                        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sql_str = "INSERT INTO `packge_user` (`user_phone`, `user_type`, " \
                                  "`user_surplus_times`, `user_is_good`, `user_login_times`, `create_time`, " \
                                  "`user_from`) VALUES ('%d', 0, 3, 1, 1, '%s', '%d')" % (
                                      int(self.phone), dt, int(self.user_from))
                        self.surplus_times = 3
                        cursor.execute(sql_str)

                    # 更新用户使用次数
                    sql_str = "UPDATE `packge_user` SET `user_type` = %d, `user_surplus_times` = `user_surplus_times` + " \
                              "%d, `user_times` = `user_times` + 1 WHERE user_phone = %d " % (
                                  int(valid_type), int(valid_surplus_times), int(self.phone))
                    cursor.execute(sql_str)
                    # 更新验证码激活状态
                    sql_str_2 = "UPDATE `packge_code` SET `is_verification` = 1, `valid_time` = '%s' WHERE `valid_code` " \
                                "= '%s'" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), valid)
                    cursor.execute(sql_str_2)
                    status = True
            except:
                self.output_json({"errorCode": "10011", "msg": "Invalid valid code"})
                cursor.close()
                status = False
        return status

    # 检查post数据
    def check_post_data(self, data, val_type, valid_data=''):
        # 为了格式统一，这里数据验证失败不退出，只返回False
        if val_type == 'phone':
            res = re.search(re.compile('^1[3-9]\d{9}$'), data)
            if (res == '') or (len(str(data)) != 11) or (res is None):
                self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "phone"})
                return ''
            else:
                return data

        if val_type == 'url':
            res = re.findall(r"h5.ele.me", data)
            if res == '':
                self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "url-2"})
                return False
            else:
                url_str = urllib.parse.urlparse(data).fragment.split('&')
                if len(url_str) < 7:
                    self.output_json({"errorCode": "10002", "msg": "Parameter error", "other": "url_2"})
                    return False
                else:
                    return data

        # 为了防止从其他地方请求接口数据，设置token校验
        if val_type == 'token':

            hl = hashlib.md5()
            var_str = "%sUSER_KEY" % valid_data
            hl.update(var_str.encode('utf-8'))
            valid_token = hl.hexdigest()

            var_str_proxy = "%s7fhdsfd44r4uw32pf94tsDf3f" % valid_data
            hl = hashlib.md5()
            hl.update(var_str_proxy.encode('utf-8'))
            valid_token_proxy = hl.hexdigest()

            if valid_token != str(data) and valid_token_proxy != str(data):
                self.output_json({"errorCode": "10008", "msg": "Invalid token"})
                return False
            else:
                return True

        if val_type == 'valid':

            if data == '' or len(data) == 0:
                return False
            else:
                return True

        if val_type == 'request_from':
            if data == '':
                # 设置用户来源标识 主站来源
                self.user_from = 0
                return True
            else:
                # 设置用户来源标识 代理
                self.user_from = 1
                return False

    def output_json(self, data):

        # "errorCode": "10001", "msg": "Type of data error"
        # "errorCode": "10002", "msg": "Parameter error"
        # "errorCode": "10003", "msg": "Require cookies error"
        # "errorCode": "10004", "msg": "Require phone error"
        # "errorCode": "10005", "msg": "Update cookie times error"
        # "errorCode": "10006", "msg": "Bad request"
        # "errorCode": "10007", "msg": "Update phone error"
        # "errorCode": "10008", "msg": "Invalid token"
        # "errorCode": "10009", "msg": "A used lucky package"
        # "errorCode": "10010", "msg": "Too many bad requests"
        # "errorCode": "10011", "msg": "Invalid or used valid code"
        # "errorCode": "10012", "msg": "Update user info error"
        # "errorCode": "10013", "msg": "No enough surplus times"
        # "errorCode": "10014", "msg": "A forbid account"
        # "errorCode": "10015", "msg": "Url type error"

        if not isinstance(data, dict):

            self.message = json.dumps('{"errorCode": "10001", "msg": "Type of data error"}')
        else:
            self.message = json.dumps(data)

    def __del__(self):
        print("__over__")


# 查询自己剩余次数
###############################################
class Check:
    def __init__(self):
        self.token = ''
        self.phone = ''
        self.conn = ''
        self.message = ''
        self.user_type = ''
        self.user_surplus_times = ''
        self.user_success_times = ''

    def get_check_data(self):
        if request.method == 'POST':
            # 初始化数据库
            self.conn = self.conn_db()
            # 获取必填信息

            post_phone = str(request.form['phone'])
            post_token = str(request.form['token'])

            self.phone = self.check_post_data(post_phone, 'phone')
            self.token = self.check_post_data(post_token, 'token', post_phone)

            # 验证token, phone
            if not self.token or not self.phone:
                return self.message
            else:
                self.get_info_by_phone()
            self.die()

        # 返回message到前端
        return self.message

    def get_info_by_phone(self):
        cursor = self.conn.cursor()
        try:
            sql_str = "SELECT `user_type`,`user_surplus_times`,`user_success_times`,`user_is_good` FROM `packge_user` WHERE  `user_phone` = %d" % int(
                self.phone)
            cursor.execute(sql_str)
            is_user = cursor.fetchall()

            if is_user == '' or len(is_user) == 0:
                self.output_json({"errorCode": "10004", "msg": "Require phone error"})
                status = False
            else:
                if is_user[0][3] == 0:
                    self.output_json({"errorCode": "10014", "msg": "A forbid account"})
                    status = False
                else:
                    self.user_type = is_user[0][0]
                    self.user_surplus_times = is_user[0][1]
                    self.user_success_times = is_user[0][2]
                    self.output_json({'errorCode': '0', 'msg': 'Success', 'user_surplus_times': self.user_surplus_times,
                                      'user_success_times': self.user_success_times,
                                      'user_type': self.user_type})
                    status = True
        except:
            self.output_json({"errorCode": "10006", "msg": "Bad request"})
            cursor.close()
            status = False
        return status

    def conn_db(self):
        try:
            conn = pymysql.connect(host='localhost', user='root', password='aaabbbccc', db='packge', port=3306,
                                   charset='utf8')
            return conn
        except:
            return False

    def die(self):
        self.conn.close()

    # 检查post数据
    def check_post_data(self, data, val_type, valid_data=''):
        # 为了格式统一，这里数据验证失败不退出，只返回False
        if val_type == 'phone':
            res = re.search(re.compile('^1[3-9]\d{9}$'), data)
            if (res == '') or (len(str(data)) != 11) or (res is None):
                self.output_json({"errorCode": "10002", "msg": "Parameter error"})
                return False
            else:
                return data

        # 为了防止从其他地方请求接口数据，设置token校验
        if val_type == 'token':

            hl = hashlib.md5()
            var_str = "%sUSER_KEY" % valid_data
            hl.update(var_str.encode('utf-8'))
            valid_token = hl.hexdigest()

            var_str_proxy = "%s7fhdsfd44r4uw32pf94tsDf3f" % valid_data
            hl = hashlib.md5()
            hl.update(var_str_proxy.encode('utf-8'))
            valid_token_proxy = hl.hexdigest()

            if valid_token != str(data) and valid_token_proxy != str(data):
                self.output_json({"errorCode": "10008", "msg": "Invalid token"})
                return False
            else:
                return True

    def output_json(self, data):

        # "errorCode": "10001", "msg": "Type of data error"
        # "errorCode": "10002", "msg": "Parameter error"
        # "errorCode": "10003", "msg": "Require cookies error"
        # "errorCode": "10004", "msg": "Require phone error"
        # "errorCode": "10005", "msg": "Update cookie times error"
        # "errorCode": "10006", "msg": "Bad request"
        # "errorCode": "10007", "msg": "Update phone error"
        # "errorCode": "10008", "msg": "Invalid token"
        # "errorCode": "10009", "msg": "A used lucky package"
        # "errorCode": "10010", "msg": "Too many bad requests"
        # "errorCode": "10011", "msg": "Invalid or used valid code"
        # "errorCode": "10012", "msg": "Update user info error"
        # "errorCode": "10013", "msg": "No enough surplus times"
        # "errorCode": "10014", "msg": "A forbid account"

        if not isinstance(data, dict):

            self.message = json.dumps('{"errorCode": "10001", "msg": "Type of data error"}')
        else:
            self.message = json.dumps(data)

    def __del__(self):
        print("__over__")


app = Flask(__name__)


@app.route('/')
def test():
    return 'ok'

@app.route('/check', methods=['POST'])
def check():
    info = Check()
    message = info.get_check_data()
    del info
    return message

@app.route('/packge', methods=['POST'])
def main():
    packge = Main()
    message = packge.get_data()
    del packge
    return message

if __name__ == '__main__':
    app.run(
        # processes=5,
        # host='0.0.0.0',
        # port=5500,
        # debug=True
    )
