import asyncio

import random
import requests

from threading import Thread

asyncio.get_child_watcher()


class Proxy_Rotator:
    def check_proxy(self, proxy, timeout):
        try:
            r = requests.get("https://store.steampowered.com/join/", proxies=proxy, timeout=timeout)
        except requests.exceptions.ProxyError:
            return False
        except Exception as e:
            # print(e)
            return False

        return True

    def check_proxy_list(self, proxy_list):
        for proxy in proxy_list:
            prox = {"http": proxy, "https": proxy}
            if not self.check_proxy(prox, 0.1):
                # proxies_list.remove(proxy)
                continue
            else:
                self.final_list.append(proxy)

    def check(self):
        proxy_threads = []
        proxy_thread_amount = len(self.list)
        amount = 4096
        last = proxy_thread_amount % amount
        # print(last)
        amt = int(proxy_thread_amount / amount)
        if last != 0 or amt < 1:
            amt += 1
        # print(amt)
        for x in range(1, amt + 1, 1):
            for i in range(0, amount, 1):
                if x < amt or i < last:
                    lst = [list(self.list)[i * x:(i + 1) * x]]
                elif i >= last:
                    # print("last iteration {}".format(i))
                    break

                t = Thread(target=self.check_proxy_list, args=lst)

                proxy_threads.append(t)

                t.start()

            for p in proxy_threads:
                p.join()
        # print("{} valid proxies.".format(len(self.final_list)))


    def blacklist(self, proxy):
        # print(proxy)
        if proxy in self.final_list:
            self.final_list.remove(proxy)

    def get(self):
        return random.choice(self.final_list)

    def __init__(self, interval=600, amount=500):
        self.list = set()
        self.final_list = []
        with open("./proxies") as f:
            tmp = f.readlines()
        for proxy in tmp:
            # print(proxy)
            if proxy in self.list:
                continue
            proxy = proxy.strip()
            self.list.add(proxy)
        self.check()
