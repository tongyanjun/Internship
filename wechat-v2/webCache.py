import time


class Cache:
    def __init__(self, filename, length, split_sym):
        self.filename = filename
        self.length = length
        self.split_sym = split_sym
        self.cache = {}
        self.cache_access_time = {}

        out_file = open(filename, "w")
        out_file.write('')

    def find_earliest_ele(self):
        earliest_key = ""
        earliest_value = time.time()
        for key in self.cache_access_time:
            if self.cache_access_time[key] < earliest_value:
                earliest_key = key

        return earliest_key

    def remove_ele(self, removing_key):
        del self.cache[removing_key]
        del self.cache_access_time[removing_key]

    def remove_ele_with_task(self, removing_key):
        task_id = removing_key.split(self.split_sym)[0]
        keys = []
        for key in self.cache:
            if task_id == key.split(self.split_sym)[0]:
                keys.append(key)

        for key in keys:
            self.remove_ele(key)

    def add(self, key, value):
        if len(self.cache) >= self.length:
            removing_key = self.find_earliest_ele()
            self.remove_ele(removing_key)

        self.add_to_file(key, value)
        self.cache[key] = value
        self.cache_access_time[key] = time.time()

    def find(self, key):
        if key in self.cache:
            result = self.cache[key]
        else:
            result = self.get_from_file(key)

        self.remove_ele_with_task(key)
        return result

    def add_to_file(self, key, value):
        out_file = open(self.filename, "a")
        out_file.write(key + " " + value + "\n")
        out_file.flush()
        out_file.close()

    def get_from_file(self, key):
        out_file = open(self.filename, "w+")
        line = out_file.readline()
        while line != '':
            pair = line.split(' ')
            if pair[0] == key:
                self.add(key, pair[1].strip())
                return pair[1].strip()
            line = out_file.readline()

        out_file.close()
        return ''
