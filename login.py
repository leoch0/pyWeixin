#!/usr/bin/python

def login():
    print("this is login")

def get_QRuuid():
    url = "https://login.weixin.qq.com/jslogin"
    params = {
        'appid' : 'wx782c26e4c19acffb',
        'fun'   : 'new', }
    headers = { 'User-Agent' : config.USER_AGENT }
