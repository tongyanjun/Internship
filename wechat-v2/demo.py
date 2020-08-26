#coding:utf-8

from imp import reload
import sys
import webCache
import caiRq
reload(sys)


if __name__ == '__main__':
    cache = webCache.Cache("test", 10, "-")
    cache.add("hello", "world")
    res = caiRq.talk("8131")
    print("no")