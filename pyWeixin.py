#!/usr/bin/python
# coding: utf-8

import os
import sys
import requests
import json
import time
import random
import re
import logging  
import logging.handlers  
import pyqrcode
import xml.dom.minidom
import urllib

UNKONWN = 'unkonwn'
SUCCESS = '200'
SCANED = '201'
TIMEOUT = '408'
  
LOG_FILE = 'tst.log'  
logging.basicConfig(level = logging.INFO)  
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes = 1024*1024, backupCount = 5) # 实例化handler   
fmt = '%(asctime)s - %(filename)s:%(lineno)s - %(name)s - %(message)s'  
  
formatter = logging.Formatter(fmt)   # 实例化formatter  
handler.setFormatter(formatter)      # 为handler添加formatter  
  
logger = logging.getLogger('tst')    # 获取名为tst的logger  
logger.addHandler(handler)           # 为logger添加handler  
#logger.setLevel(logging.DEBUG)  
  
  


class SafeSession(requests.Session):
    def request(self, method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
                timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None,
                json=None):
        for i in range(3):
            try:
                return super(SafeSession, self).request(method, url, params, data, headers, cookies, files, auth,
                                                        timeout,
                                                        allow_redirects, proxies, hooks, stream, verify, cert, json)
            except Exception as e:
                print(e.message, traceback.format_exc())
                continue

        #重试3次以后再加一次，抛出异常
        try:
            return super(SafeSession, self).request(method, url, params, data, headers, cookies, files, auth,
                                                    timeout,
                                                    allow_redirects, proxies, hooks, stream, verify, cert, json)
        except Exception as e:
            raise e


class pyWeixin:

    def __init__(self):
        self.uuid = ''
        self.base_uri = ''
        self.base_host = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.device_id = 'e' + repr(random.random())[2:17]
        self.base_request = {}
        self.sync_key_str = ''
        self.sync_key = []
        self.sync_host = ''

        self.session = SafeSession()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux i686; U;) Gecko/20070322 Kazehakase/0.4.5'})


    def get_uuid(self):
        '''获取登录需要的UUID'''

        logger.info("获取UUID中...")
        url = 'https://login.weixin.qq.com/jslogin'
        logger.debug("获取UUID的URL地址为：{}".format(url))
        params = {
            'appid': 'wx782c26e4c19acffb',
            'fun': 'new',
            'lang': 'zh_CN',
            '_': int(time.time()) * 1000 + random.randint(1, 999),
        }
        logger.debug("获取UUID请求的参数为；{}".format(params))
        r = self.session.get(url, params=params)
        r.encoding = 'utf-8'
        data = r.text
        logger.debug("获取UUID返回的数据为：{}".format(data))
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            logger.debug(code)
            self.uuid = pm.group(2)
            logger.debug("获取到的UUID为：{}".format(self.uuid))
            logger.info("UUID获取成功！！！")
            return code == '200'
        logger.error("获取UUID失败！！！")
        return False

    def show_qr_code(self):
        '''显示登录二维码'''

        logger.info("正在加载登录二维码...")
        qr_code_url = "https://login.weixin.qq.com/l/{}".format(self.uuid)
        logger.debug("登录二维码URL为：{}".format(qr_code_url))
        qr = pyqrcode.create(qr_code_url)
        print(qr.terminal(quiet_zone=1))
        logger.info("登录二维码加载成功")

    def do_request(self, url):
        '''获取用户扫描状态码和扫描状态'''

        r = self.session.get(url)
        r.encoding = 'utf-8'
        data = r.text
        param = re.search(r'window.code=(\d+);', data)
        code = param.group(1)
        return code, data

    def wait4login(self):
        """
        http comet:
        tip=1, 等待用户扫描二维码,
               201: scaned
               408: timeout
        tip=0, 等待用户确认登录,
               200: confirmed
        """

        logger.info("使用移动端微信扫描该二维码进行登录！！！")
        LOGIN_TEMPLATE = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip={0}&uuid={1}&_={2}'
        tip = 1

        try_later_secs = 1
        MAX_RETRY_TIMES = 10

        code = UNKONWN

        retry_time = MAX_RETRY_TIMES
        while retry_time > 0:
            url = LOGIN_TEMPLATE.format(tip, self.uuid, int(time.time()))
            logger.debug("获取用户扫描状态的URL为{}".format(url))
            code, data = self.do_request(url)
            logger.debug("扫描码为{0},扫描说明为{1}".format(code, data))
            if code == SCANED:
                logger.info("扫描成功，在移动端点击确认登录")
                tip = 0
            elif code == SUCCESS:  # 确认登录成功
                logger.info("点击确认登录成功，正在获取数据...")
                param = re.search(r'window.redirect_uri="(\S+?)";', data)
                redirect_uri = param.group(1) + '&fun=new'
                self.redirect_uri = redirect_uri
                self.base_uri = redirect_uri[:redirect_uri.rfind('/')]
                temp_host = self.base_uri[8:]
                self.base_host = temp_host[:temp_host.find("/")]
                return code
            elif code == TIMEOUT:
                logger.error('登录超时，{}秒后重试...'.format(try_later_secs))

                tip = 1  # 重置
                retry_time -= 1
                time.sleep(try_later_secs)
            else:
                logger.error('登录失败，失败码为{0}. {1}秒后重试...'.format(code, try_later_secs))
                tip = 1
                retry_time -= 1
                time.sleep(try_later_secs)
        return code

    def login(self):
        '''判断是否登录成功'''

        logger.info("判断是否成功登录...")
        if len(self.redirect_uri) < 4:
            loggin.warn("由于未知原因，登录失败，请重试！！！")
            return False
        r = self.session.get(self.redirect_uri)
        r.encoding = 'utf-8'
        data = r.text
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement
        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.base_request = {
            'Uin': self.uin,
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.device_id,
        }
        logger.info("登录成功")
        return True

    def init(self):
        '''微信初始化'''

        logger.info("微信初始化中...")
        url = self.base_uri + '/webwxinit?r={0}&lang=en_US&pass_ticket={1}'.format(int(time.time()), self.pass_ticket)
        logger.debug("微信初始化URL为{}".format(url))
        params = {
            'BaseRequest': self.base_request
          }
        logger.debug("微信初始化传送参数为：{}".format(params))
        r = self.session.post(url, data=json.dumps(params))
        logger.debug("微信初始化返回数据为：{}".format(r))
        r.encoding = 'utf-8'
        dic = json.loads(r.text)
        logger.debug("初始化返回的数据JSON化后为：{}".format(dic))
        self.sync_key = dic['SyncKey']
        self.my_account = dic['User']
        self.sync_key_str = '|'.join([str(keyVal['Key']) + '_' + str(keyVal['Val'])
                                      for keyVal in self.sync_key['List']])
        return dic['BaseResponse']['Ret'] == 0

    def status_notify(self):
        '''开启微信状态通知'''

        logger.info("开启微信状态通知中...")
        url = self.base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket{}'.format(self.pass_ticket)
        logger.debug("开启微信状态通知的URL为：{}".format(url))
        self.base_request['Uin'] = int(self.base_request['Uin'])
        params = {
            'BaseRequest': self.base_request,
            "Code": 3,
            "FromUserName": self.my_account['UserName'],
            "ToUserName": self.my_account['UserName'],
            "ClientMsgId": int(time.time())
        }
        logger.debug("开启微信状态通知的请求参数为：{}".format(params))
        r = self.session.post(url, data=json.dumps(params))
        r.encoding = 'utf-8'
        dic = json.loads(r.text)
        logger.debug("开启微信状态通知请求结果为：{}".format(dic))
        return dic['BaseResponse']['Ret'] == 0

    def get_contact(self):
        """获取当前账户的所有相关账号(包括联系人、公众号、群聊、特殊账号)"""

        logger.info("获取联系人列表中")
        dic_list = []
        url = self.base_uri + '/webwxgetcontact?seq=0&pass_ticket={0}&skey={1}&r={2}'.format(self.pass_ticket, self.skey, int(time.time()))

        #如果通讯录联系人过多，这里会直接获取失败
        try:
            r = self.session.post(url, data='{}', timeout=180)
        except Exception as e:
            return False
        r.encoding = 'utf-8'
        dic = json.loads(r.text)
        dic_list.append(dic)
        logger.debug("联系人列表信息：{}".format(dic_list))

    def proc_msg(self):
        self.test_sync_check()
        self.status = 'loginsuccess'  #WxbotManage使用
        while True:
            if self.status == 'wait4loginout':  #WxbotManage使用
                return 
            check_time = time.time()
            try:
                [retcode, selector] = self.sync_check()
                logger.debug('sync_check:{0},{1}'.format(retcode, selector))
                if retcode == '1100':  # 从微信客户端上登出
                    break
                elif retcode == '1101':  # 从其它设备上登了网页微信
                    break
                elif retcode == '0':
                    if selector == '2':  # 有新消息
                        logger.debug("有新的消息")
                        r = self.sync()
                        if r is not None:
                            break
                            #self.handle_msg(r)
                    elif selector == '3':  # 未知
                        r = self.sync()
                        if r is not None:
                            break #self.handle_msg(r)
                    elif selector == '4':  # 通讯录更新
                        r = self.sync()
                        if r is not None:
                            self.get_contact()
                    elif selector == '6':  # 可能是红包
                        r = self.sync()
                        if r is not None:
                            break#self.handle_msg(r)
                    elif selector == '7':  # 在手机上操作了微信
                        r = self.sync()
                        if r is not None:
                            break#self.handle_msg(r)
                    elif selector == '0':  # 无事件
                        pass
                    else:
                        logger.debug('sync_check:{0},{1}'.format(retcode, selector))
                        r = self.sync()
                        if r is not None:
                            break#self.handle_msg(r)
                else:
                    logger.debug('sync_check:{0},{1}'.format(retcode, selector))
                    time.sleep(10)
                self.schedule()
            except:
                logger.debug('[ERROR] Except in proc_msg')
                logger.debug(format_exc())
            check_time = time.time() - check_time
            if check_time < 0.8:
                time.sleep(1 - check_time)

    def test_sync_check(self):
        for host1 in ['webpush.', 'webpush2.']:
            self.sync_host = host1+self.base_host
            try:
                retcode = self.sync_check()[0]
            except:
                retcode = -1
            if retcode == '0':
                return True
        return False

    def sync_check(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.device_id,
            'synckey': self.sync_key_str,
            '_': int(time.time()),
        }
        url = 'https://' + self.sync_host + '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
        try:
            r = self.session.get(url, timeout=60)
            r.encoding = 'utf-8'
            data = r.text
            pm = re.search(r'window.synccheck=\{retcode:"(\d+)",selector:"(\d+)"\}', data)
            retcode = pm.group(1)
            selector = pm.group(2)
            return [retcode, selector]
        except:
            return [-1, -1]

    def sync(self):
        url = self.base_uri + '/webwxsync?sid={0}&skey={1}&lang=en_US&pass_ticket={2}'.format(self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            'SyncKey': self.sync_key,
            'rr': ~int(time.time())
        }
        try:
            r = self.session.post(url, data=json.dumps(params), timeout=60)
            r.encoding = 'utf-8'
            dic = json.loads(r.text)
            if dic['BaseResponse']['Ret'] == 0:
                self.sync_key = dic['SyncCheckKey']
                self.sync_key_str = '|'.join([str(keyVal['Key']) + '_' + str(keyVal['Val'])
                                              for keyVal in self.sync_key['List']])
            return dic
        except:
            return None


bot = pyWeixin()
print(bot.uuid)
bot.get_uuid()
print(bot.uuid)
bot.show_qr_code()
bot.wait4login()
bot.login()
bot.init()
bot.status_notify()
bot.get_contact()
bot.proc_msg()
