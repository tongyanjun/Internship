from webCache import Cache


def main():
    cache = Cache("phone", 2, '-')
    cache.add("12-1", "hello")
    cache.add("11-1", "good")
    cache.add("12-2", "see0you")
    cache.add("13-1", "yell")
    print cache.find("12-1")


if __name__ == "__main__":
    main()