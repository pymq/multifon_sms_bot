import random
from io import BytesIO

from PIL import Image
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumrequests import Chrome


class UmsConnection():

    def __init__(self, user_phone, user_password):
        self._user_phone = user_phone
        self._user_password = user_password
        self._is_authorized = False
        self._captcha = None  # REMOVE
        options = Options()
        options.add_argument("--headless")
        WINDOW_SIZE = "1620,880"  # ?
        options.add_argument("--window-size=%s" % WINDOW_SIZE)
        self.webdriver = Chrome(chrome_options=options)
        self.webdriver.get(r"https://messages.megafon.ru/onebox/mix.do")

        phone_input = self.webdriver.find_element_by_id('user12')
        phone_input.send_keys(user_phone)

        password_input_secinfo = self.webdriver.find_element_by_id('secinfo')
        password_input_secinfo.click()
        password_input = self.webdriver.find_element_by_id("secinfo2")
        password_input.send_keys(user_password)

    def get_captcha(self) -> bytes:
        captcha = self.webdriver.find_element_by_id('imageC')
        location = captcha.location
        size = captcha.size
        screenshot = self.webdriver.get_screenshot_as_png()
        im = Image.open(BytesIO(screenshot))
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']
        im = im.crop((left, top, right, bottom))
        self._captcha = im  # REMOVE
        stream = BytesIO()
        im.save(stream, format="PNG")
        return stream.getvalue()

    def send_captcha_key(self, key) -> bool:
        captcha_input = self.webdriver.find_element_by_id('imageObj')
        captcha_input.send_keys(key)
        submit_button = self.webdriver.find_element_by_id('index_login')
        submit_button.click()
        try:
            WebDriverWait(self.webdriver, 2).until(
                EC.url_contains(("messages.megafon.ru/onebox/mix.do")))
            self._is_authorized = True
            self._captcha.save(f'captchas/{key}.png')  # REMOVE
            return True
        except exceptions.TimeoutException:
            return False

    @property
    def is_authorized(self):
        return self._is_authorized

    def get_chat_list(self, number=10):
        url = r"https://messages.megafon.ru/onebox/getChatList.do"
        get_chats_url_params = {
            'startNum': '1',
            'endNum': number,
            'reFreshFlag': '1',
            'operation': '1',
            'chatMsgType': '10100000000110000000000000000000',
            't': random.random()
        }
        response = self.webdriver.request('GET', url, params=get_chats_url_params)
        return response.text

    def get_one_box(self, address, number=10, from_num=1):
        url = r"https://messages.megafon.ru/onebox/oneboxList.do"
        params = [
            ('umReq.ctlg', '1,2'),
            ('umReq.numFlg', '1'),
            ('umReq.mType', '6149'),
            ('umReq.srt', '0'),
            ('umReq.lType', '0'),
            ('umReq.dFlg', '0'),
            ('umReq.srtDr', '0'),
            ('umReq.rdFlg', '0'),
            ('umReq.bNum', from_num),
            ('umReq.eNum', number),
            ('umReq.snd', address),
            ('umReq.rcv', self._user_phone),
            ('umReq.bTime', ''),
            ('umReq.eTime', ''),
            ('umReq.impt', '-1'),
            ('umReq.t', ''),
            ('umReq.threadFlag', '1'),
            ('rownid', random.random()),
        ]
        response = self.webdriver.request('GET', url, params=params)
        return response.text

    def close(self):
        self.webdriver.close()
