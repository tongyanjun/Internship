import sapcai
import numpy as np

REQUEST_TOKEN = "ee4a7412e20ae96843353c0fce71aa27"

build = sapcai.Build(REQUEST_TOKEN)

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
