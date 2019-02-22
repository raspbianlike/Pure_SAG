import imaplib
import json
import os
import random
import shutil
import signal
import string
import time
from threading import Thread

import requests
import tornado.ioloop
import tornado.web

with open("config.json") as f:
    config = json.load(f)

api_key = config["captcha_solver"][0]["key"]
api_secret = config["captcha_solver"][0]["secret"]
api_service = config["captcha_solver"][0]["service"]

with open("config.json") as f:
    config = json.load(f)


def save_account_wrapper():
    output = ""
    for account in session_accounts:
        output += account + "\n"
    open("./accounts.txt", "a+").write(output)


def on_exit():
    with open("./database.json", "w") as d:
        json.dump(database, d, indent=4)
    save_account_wrapper()
    print("Saved database! Exiting...")
    os.system("pkill -f whats_my_name???.exe")  # not proper


class Exit_Watchdog:

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, meme, lol):
        on_exit()


def random_string(len):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(len))


def get_captcha_result(captcha_url, proxy):
    fname = "./captchas/" + random_string(15) + '.png'
    try:
        r = requests.get(captcha_url, proxies=proxy, stream=True, timeout=30)
    except Exception as e:
        return "steam_error"

    if r.status_code == 200:  # This is bad, you dont want to write to disk, figure this out by yourself
        with open(fname, 'wb') as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
    else:
        return "error"
    if api_service == "pure_solver":
        fields = {"type": "image", "method": "base64", "key": api_key, "out": "json"}
        result = requests.post("http://localhost:1337", data=fields)
        return result.json()["result"]

    elif api_service == "capsol":
        fields = {"p": "upload", "key": api_key, "secret": api_secret, "out": "json"}

        files = {'captcha': open(fname, 'rb')}  # whats performance
        try:
            result = requests.post("http://api.captchasolutions.com/solve", data=fields, files=files, timeout=60)
        except:
            os.remove(fname)
            return "error"

        if result.status_code != 200:
            os.remove(fname)
            return "error"

        if "cannot solve" in result.text or "0 balance" in result.text or "invalid":
            os.remove(fname)
            return "solve_error"

        captcha_result = result.json()['captchasolutions']

    elif api_service == "2captcha":
        # Not implemented yet, feel free to do so
        fields = {"key": api_key, "method": "base64", "json": 1}

        files = {"file": open(fname, "rb")}
        try:
            result = requests.post("https://2captcha.com/in.php", data=fields, files=files, timeout=60)
        except Exception as e:
            os.remove(fname)
            return "error"

        if result.status_code != 200:
            os.remove(fname)
            return "error"

        print(result.json())
        print(result.json()["request"])

    os.remove(fname)
    return captcha_result


def confirm_email(user, proxy):
    counter = 0
    while not counter < 60:
        try:

            mail = imaplib.IMAP4("SERVER")

            mail.login("USER", "PASS")
            mail.select("INBOX")
            mail.list()

            result, data_mail = mail.search(None, '(TO {})'.format(user))

            ids = data_mail[0]
            id_list = ids.split()

            latest_email_id = id_list[-1]

            result, data_mail = mail.fetch(latest_email_id, "RFC822")
            raw_email = data_mail[0][1]
            raw_email = str(raw_email)
            url = raw_email[raw_email.find("Create My Account:") + 22: raw_email.find("Create My Account:") + 218]

            if not url.startswith("http"):
                continue
            try:
                requests.post(url, proxies=proxy, timeout=30)
            except Exception as e:
                print(e)
                mail.store(latest_email_id, '+FLAGS', '(\Deleted)')
                mail.expunge()
                mail.logout()
                return

            session_id = url[-19:]

            session_id = session_id.replace("\\", "")
            mail.store(latest_email_id, '+FLAGS', '(\Deleted)')
            mail.expunge()
            mail.logout()
            return session_id
        except Exception:
            counter += 1
            time.sleep(1)


''' GLOBAL VARIABLES'''
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

active_tokens = {}

session_accounts = []

thread_accounts = []

database = json.load(open("./database.json"))


# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #

class Pure_Handler(tornado.web.RequestHandler):
    executor = tornado.concurrent.futures.ThreadPoolExecutor(50)

    def gen_account(self, proxy, token):
        proxy = proxy[0]

        user = random_string(12)
        passw = random_string(12)
        email = user + "@mailbox.cc"

        with requests.Session() as session:
            session.headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36'}
            session.proxies = proxy
            session.timeout = 30

        try:
            join_get = session.post("https://store.steampowered.com/join/", timeout=30)
        except Exception as e:
            print(e)
            rotator.blacklist(proxy["http"])
            return

        captcha_url = join_get.text[
                      join_get.text.find("https://store.steampowered.com/login/rendercaptcha?gid="): join_get.text.find(
                          "https://store.steampowered.com/login/rendercaptcha?gid=") + 74]

        gid = captcha_url[55:]
        equal = False
        while not equal:
            captcha_result = get_captcha_result(captcha_url, proxy)

            if captcha_result == "steam_error":
                return
            elif captcha_result == "solve_error":
                continue

            data = {"email": email, "captchagid": gid, "captcha_text": captcha_result}
            try:

                verify_captcha_post = session.post("https://store.steampowered.com/join/verifycaptcha/", data=data,
                                                   timeout=30)
                if verify_captcha_post.json()["bCaptchaMatches"]:
                    equal = True
            except:
                return

        data = {"email": email, "captchagid": gid, "captcha_text": captcha_result}
        try:
            verify_email_post = session.post("https://store.steampowered.com/join/ajaxverifyemail", data=data,
                                             timeout=30)
        except:
            print("no valid verify email")
            return
        if verify_email_post.status_code != 200:
            return

        stat = verify_email_post.json()["success"]

        if stat != 1:
            return

        session_id = confirm_email(email, proxy)

        data = {"accountname": user, "password": passw, "creation_sessionid": session_id}
        try:
            create_account_post = session.post("https://store.steampowered.com/join/createaccount/", data=data,
                                               timeout=30)
        except:
            return

        if create_account_post.status_code != 200:
            return
        try:
            if not create_account_post.json()["bSuccess"]:
                return
        except:
            print(create_account_post.text)

        database["users"][0][token]["generated_accounts"] += 1

        active_tokens[token]["amount"] += 1
        active_tokens[token]["list"].append("{}:{}".format(user, passw))

        global session_accounts
        session_accounts.append("{}:{}".format(user, passw))

    def do_create(self, num, token):
        am = num
        threads = []
        prx = rotator.get()
        print(prx)
        for i in range(0, am, 1):
            # if not i % 10:
            prx = rotator.get()
            cur = [{"https": prx, "http": prx}]

            t = Thread(target=self.gen_account, args=(cur, token))
            threads.append(t)
            t.start()

        for c in threads:
            c.join()

    @tornado.concurrent.run_on_executor
    def get(self):
        try:
            get_cfg = self.get_body_argument("cfg", default=None, strip=False)
            version_client = self.get_body_argument("version", default=None, strip=False)
            if not get_cfg and not version_client:
                self.write("No.")
                return

            if get_cfg:
                data = {
                    "api_key": "",
                    "gen_amount": 10,
                    "save_to_file": True,
                    "file_target": "accounts.txt",
                    "server": "",
                    "update_client_on_start": True
                }
                self.write(json.dumps(data, indent=4))
                return

            if version_client:
                versions_server = config["versions"]
                latest_version = versions_server[-1:][0]

                if version_client not in versions_server:
                    self.write(json.dumps({"response_code": 0, "response": "Invalid version!"}, indent=4))
                    return
                if version_client == latest_version:
                    self.write(json.dumps({"response_code": 1, "response": "Already latest version"}, indent=4))
                    return
                self.write(json.dumps({"response_code": 200, "response": open("").read()},
                                      indent=4))

        finally:
            self.finish("kek")

    @tornado.concurrent.run_on_executor
    def post(self):
        global active_tokens
        global database

        self.created_accounts = []
        self.created_accounts_amount = 0

        token = self.get_body_argument("token", default=None, strip=False)
        token = str(token)
        # self.token = token

        with open("status.txt") as st:
            stat = st.read()
        stat = int(stat)
        if stat != 200:
            self.write(json.dumps({"response_code": 4,
                                   "response": "The account generator is currently under maintenance!"
                                   }))
            return

        generation_amount = self.get_body_argument("amount", default=0, strip=False)

        generation_amount = int(generation_amount)

        if token not in database["users"][0]:
            self.write(json.dumps({"response_code": -1,
                                   "response": "Invalid token!"
                                   }))
            return
        if database["users"][0][token]["account_state"] == -2:
            self.write(json.dumps({"response_code": 0,
                                   "response": "Your account does not have a valid subscription!"
                                   }))
            return

        if database["users"][0][token]["generated_accounts"] >= 100 and database["users"][0][token][
            "account_state"] == 0:
            database["users"][0][token]["account_state"] = -1

        if database["users"][0][token]["account_state"] == -1:
            self.write(json.dumps({"response_code": 1,
                                   "response": "Your trial has ran out!"
                                   }))
            return

        if generation_amount > config["server"][0]["limit"]:
            self.write(json.dumps({"response_code": 2,
                                   "response": "There is currently a limit of {} accounts per API call.".format(
                                       config["server"][0]["limit"])
                                   }))
            return

        if token in active_tokens:
            self.write(json.dumps({"response_code": 3,
                                   "response": "Your API key is already being used in a different session!"
                                   }))
            return

        active_tokens.update({token: {"amount": 0, "list": []}})

        while active_tokens[token]["amount"] < 1:
            self.do_create(generation_amount, token)

        if active_tokens[token]["amount"] > generation_amount:
            final_accounts = active_tokens[token]["list"][-generation_amount:]
        else:
            final_accounts = active_tokens[token]["list"]

        to_return = ""
        for account in final_accounts:
            to_return += account + "\n"

        data = {"response_code": 200,
                "accounts": to_return,
                "response": "Finished creating accounts, depending on the proxy state on the backend, there might "
                            "not have been created as many accounts as you wanted. This will be fixed soon.\n"}

        self.write(json.dumps(data, indent=4))

        print("Created {} accounts for {}".format(active_tokens[token]["amount"], database["users"][0][token]["username"]))
        self.created_accounts = []
        self.created_accounts_amount = 0

        del active_tokens[token]


def make_app():
    return tornado.web.Application([
        (r"/", Pure_Handler)
    ])


def account_watchdog():
    global session_accounts
    start = 0
    while True:
        if time.time() - start > 60:
            start = time.time()
            if len(session_accounts) > 0:
                print("[ACCOUNT WATCHDOG]: Currently {} accounts in queue. Writing.".format(len(session_accounts)))
                save_account_wrapper()
                session_accounts = []
            else:
                print("[ACCOUNT WATCHDOG]: Currently no accounts in queue.")


import proxy_rotator

rotator = proxy_rotator.Proxy_Rotator()
if __name__ == "__main__":
    exit_watchdog_d = Exit_Watchdog()

    account_watchdog_t = Thread(target=account_watchdog)
    account_watchdog_t.start()

    app = make_app()
    app.listen(6969)

    tornado.ioloop.IOLoop.current().start()
