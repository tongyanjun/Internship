from flask import Flask, request, jsonify
import string
import re

import requests
import bs4
from bs4 import BeautifulSoup
import lxml
from spider4guide import *
import json as js
import os
from text.predict import *

model = CnnModel()
url_get_token = 'https://10.47.84.207:8100/sap/opu/odata/sap/AI_CRM_GW_CREATE_INCIDENT_SRV/?sap-client=001&sap-language=EN'
url_post = 'https://10.47.84.207:8100/sap/opu/odata/sap/AI_CRM_GW_CREATE_INCIDENT_SRV/IncidentSet?sap-client=001&sap-language=EN'

dictionary = {}

# global crypto_name
app = Flask(__name__)
port = int(os.environ["PORT"])

username = 'I515013'
password = 'team068chatbot'


@app.route('/incident', methods=['POST'])
def creatIncident():
    data = json.loads(request.get_data())
    print(data)
    try:
        error = data['conversation']['memory']['error']
        errorType = data['conversation']['memory']['type']
    except:
        error = ''
        errorType = ''

    ProcessType = data['conversation']['memory']['ProcessType']['raw']
    Description = data['conversation']['memory']['title']
    LongText = data['conversation']['memory']['LongText']
    if error != '':
        LongText += '\nError Reported:\n'
        LongText += error
        LongText += '\n\nReference category given by system: '
        LongText += errorType

    Priority = data['conversation']['memory']['Priority']
    CategoryId = data['conversation']['memory']['CategoryId']
    Partner2 = data['conversation']['memory']['Partner2']
    ConfigurationItemId = data['conversation']['memory']['ConfigurationItemId']

    data = {"ProcessType": ProcessType,
            "Description": Description,
            "LongText": LongText,
            "Priority": Priority,
            "SAPComponent": "",
            "CategoryCatalogType": "D",
            "CategoryAspectId": "SAP_SM_TEMPLATE_V2",
            "CategoryId": CategoryId,
            "Partner2": Partner2,
            "ConfigurationItemId": ConfigurationItemId}

    print('Post data:\n')
    print(data)

    client = requests.Session()
    client.auth = (username, password)
    client.headers.update({'x-csrf-token': 'fetch',
                           'content-type': 'application/json'})
    try:
        r = client.get(url_get_token, verify=False)
    except:
        return jsonify(
            status=200,
            replies=[{
                'type': 'text',
                'content': 'Your network can not connect to the solution manager :('
            }]
        )

    print(r.headers)
    client.headers.update({'x-csrf-token': r.headers['x-csrf-token']})

    r2 = client.post(url_post, data=json.dumps(data), verify=False)
    print(r2.headers)
    print(r2.text)

    soup = BeautifulSoup(r2.text, 'lxml')
    try:
        incident_id = soup.find('d:objectid').string
    except:
        return jsonify(
            status=200,
            replies=[{
                'type': 'text',
                'content': 'There is something wrong, we failed to create the incident:('
            }]
        )
    else:
        return jsonify(
            status=200,
            replies=[{
                'type': 'text',
                'content': 'The incident have been created successfully!'
            },
                {
                    'type': 'text',
                    'content': 'Your incident ID number is %s' % incident_id
                }]
        )


maxResult = 3


@app.route('/fetch_id', methods=['POST'])
def fetch_id():
    try:
        data = json.loads(request.get_data())
        search_condition = data['conversation']['memory']['search_condition']
        searchResult = get_issues(search_condition)['searchResult']
        if len(searchResult) == 0:
            return jsonify(status=200,
                           replies=[{'type': 'text',
                                     'content': 'No results found in \"Guided Answers\" :(\n' +
                                                'Maybe you\'d like to search in help portal or to create a ticket.'},
                                    {"type": "buttons",
                                     "content":
                                         {"title": '',
                                          "buttons": [{"title": 'See what I can do for you',
                                                       "type": "postback",
                                                       "value": 'chatbot'}]}}])

        searchResult.sort(key=lambda x: x["SCORE"], reverse=True)
        replies = []
        i = 0
        for result in searchResult:
            if i >= maxResult:
                break
            else:
                i = i+1
                name = BeautifulSoup(result['NAME']).text
                desc = BeautifulSoup(result['DESCRIPTION']).text
                replies.append({"type": "buttons",
                                        "content":
                                            {"title": name + '\n( ' + desc + ' )',
                                             "buttons": [{"title": name,
                                                          "type": "postback",
                                                          "value": result['ACTION_ID']}]}})
        return jsonify(status=200,
                       replies=[{'type': "text",
                                 'content': 'I found these results for you :) \n' +
                                            'Click the one matching your issue, I will guide you through it.'}]+replies,
                       conversation={
                           'memory': {'guide_on': '1'}
                       })


        # searchResult.sort(key=lambda x: x["SCORE"])
        #
        # start_id = searchResult[-1]["ACTION_ID"]
        #
        # return jsonify(status=200,
        #                conversation={
        #                    'memory': {'search_id': start_id,
        #                               'guide_on': '1'}
        #                })
    except:
        return jsonify(status=200,
                       replies=[{"type": 'text',
                                 "content": 'Error happened when fetching ID number.'}])


@app.route('/guide', methods=['POST'])
def guide():
    data = json.loads(request.get_data())
    print(data)

    node = fetch_solution_node(data['conversation']['memory']['search_id'], start_session())

    content = node['content']
    content = tag_filter(content)
    isLeafNode = node['isLeafNode']
    replies = []
    if len(content)==0:
        pass
    else:
        soup = BeautifulSoup(content, 'lxml')
        for child in soup.body.children:
            if type(child) is bs4.element.NavigableString:
                continue
            elif child.name == 'p':
                text = child.get_text(' ', '<br/>')
                if text == '':
                    pass
                else:
                    replies.append({"type": "text",
                                    "content": text})

                rel = child.find_all('a')
                if len(rel) == 0:
                    pass
                else:
                    for link in rel:
                        replies.append({"type": "buttons",
                                        "content":
                                            {"title": '',
                                             "buttons": [{"title": link.text,
                                                          "type": "web_url",
                                                          "value": link['href'] if 'href' in link.attrs else ''}]}})
            elif child.name == 'ul' or child.name == 'ol':
                ul = child.find_all('li')
                for li in ul:
                    replies.append({"type": "text",
                                    "content": li.text})
                    rel = li.find_all('a')
                    if len(rel) == 0:
                        pass
                    else:
                        for link in rel:
                            replies.append({"type": "buttons",
                                            "content":
                                                {"title": '',
                                                 "buttons": [{"title": link.text,
                                                              "type": "web_url",
                                                              "value": link['href'] if 'href' in link.attrs else ''}]}})

            else:
                pass

        print(replies)


    if isLeafNode:
        return jsonify(status=200,
                       replies=replies,
                       conversation={'memory': {'guide_on': '0'}})
    # content_p = soup.find_all('p')
    # content_li = soup.find_all('li')
    # move = dict.fromkeys((ord(c) for c in u"\xa0\n\t"))
    # text = []
    # for para in content_p:
    #     for string in para.strings:
    #         item = str(string).translate(move)
    #         if item == '':
    #             continue
    #         else:
    #             text.append(item)
    #
    # for li in content_li:
    #     if li.string:
    #         text.append(li.string)
    #
    # content = text
    #
    # replies = []
    # for text in content:
    #     item = {'type': 'text',
    #             'content': text}
    #     replies.append(item)
    #
    # if isLeafNode:
    #
    #     replies.append({'type': 'text',
    #                     'content': 'This is the end of the solution'})
    #     return jsonify(
    #         status=200,
    #         replies=replies
    #     )
    else:
        question = node['question']
        options = node['options']
        if question:
            replies.append({"type": "text",
                            "content": question})

        for option in options:
            button_reply = {
                "type": "buttons",
                "content": {
                    "title": '-- ' + option + ' --',
                    "buttons": [{"title": option,
                                 "type": "postback",
                                 "value": options[option]}]
                }
            }
            replies.append(button_reply)

        return jsonify(
            status=200,
            replies=replies,
            conversation={'memory': {'guide_on': '1'}}
        )

    # try:
    #     question = node['question']
    # except:
    #     question = None
    #
    # options = node['options']
    #
    #
    #
    # buttons = []
    # for option in options:
    #     button = {"title": option,
    #               "type": "postback",
    #               "value": options[option]}
    #     buttons.append(button)
    # button_reply = {
    #     "type": "buttons",
    #     "content": {
    #         "title": question,
    #         "buttons": buttons
    #     }
    # }
    #
    # replies.append(button_reply)
    #
    # return jsonify(
    #     status=200,
    #     replies=replies
    # )


@app.route('/classify', methods=['POST'])
def test():
    data = json.loads(request.get_data())
    problem = data['conversation']['memory']['problem']

    response = model.predict(problem)

    return jsonify(
        status=200,
        replies=[{
            'type': 'text',
            'content': response
        }],
        conversation={'memory': {'type': response,
                                 'error': problem}}
    )

# @app.route('/test', methods=['POST'])
# def test():
#     data = json.loads(request.get_data())
#     print(data)
#
#     conversationID = data['conversation']['id']
#     print(conversationID)
#
#     return jsonify(
#         status=200,
#         replies=[{
#             'type': 'text',
#             'content': 'Response successfully.'
#         }]
#     )


@app.route('/errors', methods=['POST'])
def errors():
    print(json.loads(request.get_data()))
    return jsonify(status=200)


app.run(port=port, host="0.0.0.0")
