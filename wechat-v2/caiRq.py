import sapcai
import numpy as np

REQUEST_TOKEN = "c90dc2143f8dbc523f83b2200aec7e66"

build = sapcai.Build(REQUEST_TOKEN, 'en')

# CON_ID = np.random.randint(100000000, 999999999)
CON_ID = 8738264736


def talk(text_in):
    if text_in != '':
        response = build.dialog({'type': 'text', 'content': text_in}, CON_ID)
        return response.messages
    else:
        return None


class FakeResponse:
    def __init__(self, p_type, p_content):
        self.type = p_type
        self.content = p_content
