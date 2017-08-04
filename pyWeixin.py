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

UNKONWN = 'unkonwn'
SUCCESS = '200'
SCANED = '201'
TIMEOUT = '408'
  
LOG_FILE = 'tst.log'  
logging.basicConfig(level = logging.DEBUG)  
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
        '''初始化数据中...'''

        url = self.base_uri + '/webwxinit?r={0}&lang=en_US&pass_ticket={1}'.format(int(time.time()), self.pass_ticket)
        logger.debug("数据初始化URL为{}".format(url))
        params = {
            'BaseRequest': self.base_request
          }
        logger.debug("数据初始化传送参数为：{}".format(params))
        r = self.session.post(url, data=json.dumps(params))
        logger.debug("数据初始化返回数据为：{}".format(r))
        r.encoding = 'utf-8'
        dic = json.loads(r.text)
        logger.debug("返回的数据JSON化后为：{}".format(dic))
        self.sync_key = dic['SyncKey']
        self.my_account = dic['User']
        self.sync_key_str = '|'.join([str(keyVal['Key']) + '_' + str(keyVal['Val'])
                                      for keyVal in self.sync_key['List']])
        return dic['BaseResponse']['Ret'] == 0

bot = pyWeixin()
print(bot.uuid)
bot.get_uuid()
print(bot.uuid)
bot.show_qr_code()
bot.wait4login()
bot.login()
