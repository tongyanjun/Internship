import requests
import json
import re

url = "https://ga.support.sap.com/dtp/viewer/services/backend.xsjs?cmd="


class Node:

    def __init__(self,
                 node_dict=None):
        if node_dict is None:
            node_dict = {'title': None, 'content': None, 'question': None, 'options': None, 'isLeafNode': None}
        self.title = node_dict['title']
        self.content = node_dict['content']
        self.question = node_dict['question']
        self.options = node_dict['options']
        self.isLeafNode = node_dict['isLeafNode']

    def dump(self):
        return {
            "title": self.title,
            "content": self.content,
            "question": self.question,
            "options": self.options,
            "isLeafNode": self.isLeafNode
        }

    def get_option_list(self):
        res = []
        for option in self.options:
            res.append(option)

        return res

    def get_target_id(self, prompt):
        return self.options[prompt]

    def get_next_node(self, prompt):
        if self.isLeafNode is False:
            session = start_session()
            return Node(fetch_solution_node(self.get_target_id(prompt), session))
        else:
            return None


def start_session():
    return json.loads(requests.get(url + "checkSessionInfo").content)


def get_issues(search_conditions, filters=[]):
    data = {
        "searchTerms": search_conditions,
        "filters": filters
    }

    return json.loads(
        requests.post(url + "search", data=json.dumps(data)).content)


def fetch_solution_tree(action_id, a_session):
    if not action_id.isdigit():
        return {}

    data = {"actionList": action_id, "version": None, "sessionInfo": a_session}
    node_info = json.loads(requests.post(url + "getActionChain", data=json.dumps(data)).content)
    if isinstance(node_info, dict):
        # print action_id+" is done."
        return {"error": True}

    node_info = node_info[0]
    if node_info["isLeafNode"] is True:
        # print action_id + " is done."
        return {"title": node_info["title"], "content": node_info["detail"], "isLeafNode": True}

    if "outcomes" in node_info:
        options = {}
        for outcome in node_info["outcomes"]:
            options[outcome['prompt']] = fetch_solution_tree(str(outcome['target']), a_session)

        # print action_id + " is done."
        return {"title": node_info["title"],
                "content": node_info["detail"],
                "question": node_info["question"],
                "options": options,
                "isLeafNode": False}

    return {}


def fetch_solution_node(action_id, a_session):
    if not action_id.isdigit():
        return {}

    data = {"actionList": action_id, "version": None, "sessionInfo": a_session}
    node_info = json.loads(requests.post(url + "getActionChain", data=json.dumps(data)).content)
    if isinstance(node_info, dict):
        # print action_id+" is done."
        return {"error": True}

    node_info = node_info[0]
    if node_info["isLeafNode"] is True:
        # print action_id + " is done."
        return {"title": node_info["title"], "content": node_info["detail"], "isLeafNode": True}

    if "outcomes" in node_info:
        options = {}
        for outcome in node_info["outcomes"]:
            options[outcome['prompt']] = str(outcome['target'])

        # print action_id + " is done."
        return {"title": node_info["title"],
                "content": node_info["detail"],
                "question": node_info["question"],
                "options": options,
                "isLeafNode": False}

    return {}


def get_issue_tree(issue, a_session):
    return fetch_solution_tree(issue["ACTION_ID"], a_session)


def get_issue_start(issue, a_session):
    return fetch_solution_node(issue["ACTION_ID"], a_session)


def get_next_step(node, option_prompt, a_session):
    target_id = node['options'][option_prompt]
    return fetch_solution_node(target_id, a_session)


def iter_all_tree(action_id, node_dict, a_session, depth):
    if action_id not in node_dict:
        print ("id: "+action_id, "depth: "+str(depth))
        k_node = fetch_solution_node(action_id, a_session)
        node_dict[action_id] = k_node
        if ('options' in k_node) and (k_node['isLeafNode'] is False):
            for option in k_node['options']:
                iter_all_tree(k_node['options'][option], node_dict, a_session, depth+1)


def tag_filter(content):
    re_div = re.compile('</?div.*?>')
    re_span = re.compile('</?span.*?>')

    output = re_div.sub('', content)
    output = re_span.sub('', output)

    return output


if __name__ == '__main__':
    # node_dict = {}
    # iter_all_tree("29549", node_dict, session)
    # the_file = open("store/tmp_tree1.json", "w+")
    # the_file.write(json.dumps(node_dict))
    # the_file.flush()
    # the_file.close()
    issues = get_issues("", [])["searchResult"]
    print ("Fetch issues succeed.")
    page = 0
    tmp = {}
    iss_num = 0
    print ("Start fetch issue solution tree.")
    session = start_session()
    for issue in issues:
        iter_all_tree(issue['ACTION_ID'], tmp, session, 0)
        print ("Finish " + str(iss_num) + " tree.")
        if page != iss_num / 10:
            session = start_session()
            tree = open("store/tree" + str(page) + ".json", "w+")
            tree.write(json.dumps(tmp))
            tree.flush()
            tree.close()
            print ("page" + str(page) + " saved.")
            tmp = {}
            page += 1
            print ("turn to next page.")
        iss_num += 1
