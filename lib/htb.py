import os.path
from os import path
import sys
import requests
import re
import json
import time
import random
import discord
from scrapy.selector import Selector
import config as cfg

class HTBot():
    def __init__(self, email, password, api_token=""):
        self.email = email
        self.password = password
        self.api_token = api_token

        self.session = requests.Session()
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.85 Safari/537.36"
        }
        self.payload = {'api_token': self.api_token}
        self.last_checked = []
        self.regexs = {
            "box_pwn": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> owned (.*) on <a(?:.*)profile\/(?:\d+)\">(.*)<\/a> <a(?:.*)",
            "chall_pwn": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> solved challenge <(?:.*)>(.*)<(?:.*)><(?:.*)> from <(?:.*)>(.*)<(?:.*)><(?:.*)",
            "new_box_incoming": "(?:.*)Get ready to spill some (?:.* blood .*! <.*>)(.*)<(?:.* available in <.*>)(.*)<(?:.*)",
            "new_box_out": "(?:.*)>(.*)<(?:.*) is mass-powering on! (?:.*)",
            "vip_upgrade": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> became a <(?:.*)><(?:.*)><(?:.*)> V.I.P <(?:.*)"

        }
        self.notif = {
            "update_role": {
                "state": False,
                "content": {
                    "discord_id": "",
                    "prev_rank": "",
                    "new_rank": ""
                }
            },
            "new_user": {
                "state": False,
                "content": {
                    "discord_id": "",
                    "level": ""
                }
            },
            "new_box": {
                "state": False,
                "content": {
                    "incoming": False,
                    "box_name": "",
                    "time": ""
                }
            },
            "box_pwn": {
                "state": False,
                "content": {
                    "discord_id": "",
                    "pwn": "",
                    "box_name": "",
                }
            },
            "chall_pwn": {
                "state": False,
                "content": {
                    "discord_id": "",
                    "chall_name": "",
                    "chall_type": ""
                }
            },
            "vip_upgrade": {
                "state": False,
                "content": {
                    "discord_id": ""
                }
            }
        }


    def login(self):
        req = self.session.get("https://www.hackthebox.eu/login", headers=self.headers)

        html = req.text
        csrf_token = re.findall(r'type="hidden" name="_token" value="(.+?)"', html)

        if not csrf_token:
            return False

        data = {
            "_token": csrf_token[0],
            "email": self.email,
            "password": self.password
        }

        req = self.session.post("https://www.hackthebox.eu/login", data=data, headers=self.headers)

        if req.status_code == 200:
            print("Connecté à HTB !")
            self.session.headers.update(self.headers)
            return True

        print("Connexion impossible.")
        return False

    def refresh_boxs(self):
        print("Rafraichissement des boxs...")

        req = requests.get("https://www.hackthebox.eu/api/machines/get/all/", params=self.payload, headers=self.headers)

        if req.status_code == 200:
            with open("boxs.txt", "w") as f:
                f.write(req.text)

            print("La liste des boxs a été mise à jour !")
            return True

        return False

    def get_box(self, name="name", last=False):
        with open("boxs.txt", "r") as f:
            boxs = json.loads(f.read())

        box = ""
        if last:
            box = boxs[-1]
        else:
            for b in boxs :
                if b["name"].lower() == name.lower():
                    box = b
                    break
            if not box:
                return False

        embed = discord.Embed(title=box["name"], color=0x9acc14)
        embed.set_thumbnail(url=box["avatar_thumb"])
        embed.add_field(name="IP", value=str(box["ip"]), inline=True)
        if box["os"] == "Windows":
            emoji = "<:windows:649003886828322827> "
        elif box["os"] == "Linux":
            emoji = "<:linux:649003931590066176> "
        else:
            emoji = ""
        embed.add_field(name="OS", value=emoji + box["os"], inline=True)
        if box["points"] == 20:
            difficulty = "Easy"
        elif box["points"] == 30:
            difficulty = "Medium"
        elif box["points"] == 40:
            difficulty = "Hard"
        elif box["points"] == 50:
            difficulty = "Insane"
        else:
            difficulty = "?"

        embed.add_field(name="Difficulty", value="{} ({} points)".format(difficulty, box["points"]), inline=True)
        embed.add_field(name="Rating", value="⭐ {}".format(box["rating"]), inline=True)

        if box["retired"]:
            status = "Retired"
        else:
            status = "Active"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Owns", value="👤 {} #️⃣󠁲󠁯󠁯󠁴󠁿 {}".format(box["user_owns"], box["root_owns"]))
        embed.add_field(name="Release", value="/".join("{}".format(box["release"]).split("-")[::-1]), inline=True)
        if box["maker2"]:
            embed.set_footer(text="Makers : {} & {}".format(box["maker"]["name"], box["maker2"]["name"]), icon_url=box["avatar_thumb"])
        else:
            embed.set_footer(text="Maker : {}".format(box["maker"]["name"]), icon_url=box["avatar_thumb"])

        return embed

    def verify_user(self, discord_id, htb_acc_id):
        req = requests.get("https://www.hackthebox.eu/api/users/identifier/" + htb_acc_id, headers=self.headers)

        if req.status_code == 200:
            if path.exists("users.txt"):
                with open("users.txt", "r") as f:
                    users = json.loads(f.read())
            else:
                users = []

            user_info = json.loads(req.text)

            for user in users:
                if user["discord_id"] == discord_id:
                    return "already_in"

            users.append({
                "discord_id": discord_id,
                "htb_id": user_info["user_id"],
            })

            with open("users.txt", "w") as f:
                f.write(json.dumps(users))

            self.refresh_user(user_info["user_id"], new=True) #On scrape son profil

            return user_info["rank"]
        else:
            return "wrong_id"

    def discord_to_htb_id(self, discord_id):
        if path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = json.loads(f.read())
        else:
            users = []

        for user in users:
            if user["discord_id"] == discord_id:
                return user["htb_id"]
        return False

    def htb_id_by_name(self, name):

        params = {
            'username': name,
            'api_token': self.api_token
        }

        req = requests.post("https://www.hackthebox.eu/api/user/id", params=params, headers=self.headers)

        try:
            user = json.loads(req.text)
            return user["id"]
        except json.decoder.JSONDecodeError:
            return False

    def extract_user_info(self, id):
        infos = {}
        req = self.session.get("https://www.hackthebox.eu/home/users/profile/" + str(id))

        if req.status_code == 200:
            body = req.text
            html = Selector(text=body)

            infos["username"] = html.css('div.header-title > h3::text').get().strip()
            infos["avatar"] = html.css('div.header-icon > img::attr(src)').get()
            infos["points"] = html.css('div.header-title > small > span[title=Points]::text').get().strip()
            infos["systems"] = html.css('div.header-title > small > span[title="Owned Systems"]::text').get().strip()
            infos["users"] = html.css('div.header-title > small > span[title="Owned Users"]::text').get().strip()
            infos["respect"] = html.css('div.header-title > small > span[title=Respect]::text').get().strip()
            infos["country"] = Selector(text=html.css('div.header-title > small > span').getall()[4]).css('span::attr(title)').get().strip()
            infos["level"] = html.css('div.header-title > small > span::text').extract()[-1].strip()
            infos["rank"] = re.search(r'position (\d+) of the Hall of Fame', body).group(1)
            infos["challs"] = re.search(r'has solved (\d+) challenges', body).group(1)
            infos["ownership"] = html.css('div.progress-bar-success > span::text').get()

            return infos

        return False

    def get_user(self, id):
        infos = self.extract_user_info(id)

        embed = discord.Embed(title=infos["username"], color=0x9acc14, description="🎯 {} • 🏆 {} • 👤 {} • ⭐ {}".format(infos["points"], infos["systems"], infos["users"], infos["respect"]))
        embed.set_thumbnail(url=infos["avatar"])
        embed.add_field(name="About", value="📍 {} | 🔰 {}\n\n**Ownership** : {} | **Rank** : {} | ⚙️ **Challenges** : {}".format(infos["country"], infos["level"], infos["ownership"], infos["rank"], infos["challs"]))

        return embed

    def refresh_user(self, id, new=False):
        if path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = json.loads(f.read())
        else:
            users = []

        count = 0
        for user in users:
            if user["htb_id"] == id:
                infos = self.extract_user_info(id)

                try:
                    users[count]["username"]
                except KeyError:
                    new = True

                users[count]["username"] = infos["username"]
                users[count]["avatar"] = infos["avatar"]
                users[count]["points"] = infos["points"]
                users[count]["systems"] = infos["systems"]
                users[count]["users"] = infos["users"]
                users[count]["respect"] = infos["respect"]
                users[count]["country"] = infos["country"]

                if new:
                    print("New user détecté !")
                    self.notif["new_user"]["content"]["discord_id"] = users[count]["discord_id"]
                    self.notif["new_user"]["content"]["level"] = infos["level"]
                    self.notif["new_user"]["state"] = True
                else:
                    if users[count]["level"] != infos["level"]:
                        self.notif["update_role"]["content"]["discord_id"] = users[count]["discord_id"]
                        self.notif["update_role"]["content"]["prev_rank"] = users[count]["level"]
                        self.notif["update_role"]["content"]["new_rank"] = infos["level"]
                        self.notif["update_role"]["state"] = True

                users[count]["level"] = infos["level"]
                users[count]["rank"] = infos["rank"]
                users[count]["challs"] = infos["challs"]
                users[count]["ownership"] = infos["ownership"]
            count += 1
        with open("users.txt", "w") as f:
            f.write(json.dumps(users))

    def refresh_all_users(self):
        print("Rafraichissement des users...")
        if path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = json.loads(f.read())
        else:
            users = []

        for user in users:
            self.refresh_user(user["htb_id"])
        print("Les users ont été mis à jour !")

    def leaderboard(self):
        if path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = json.loads(f.read())
        else:
            users = []
            return False

        board = sorted(users, key = lambda i: int(i['points']),reverse=True)
        if len(board) > 15:
            board = board[:15]
        text = ""
        count = 0
        for user in board:
            count += 1
            if count == 1:
                text += "👑 **{}. {}** (Points : {}, Ownership : {})\n".format(count, user["username"], user["points"], user["ownership"])
            elif count == 2:
                text += "💠 **{}. {}** (Points : {}, Ownership : {})\n".format(count, user["username"], user["points"], user["ownership"])
            elif count == 3:
                text += "🔶 **{}. {}** (Points : {}, Ownership : {})\n".format(count, user["username"], user["points"], user["ownership"])
            else:
                text += "➡ **{}. {}** (Points : {}, Ownership : {})\n".format(count, user["username"], user["points"], user["ownership"])

        embed = discord.Embed(title="🏆 Leaderboard 🏆 | {}".format(cfg.discord["guild_name"]), color=0x9acc14, description=text)

        return embed

    def shoutbox(self):
        req = self.session.post("https://www.hackthebox.eu/api/shouts/get/initial/html/20?api_token=" + self.api_token, headers=self.headers)

        if req.status_code == 200:
            history = json.loads(req.text)["html"]
            last_checked = self.last_checked
            checked = []
            regexs = self.regexs

            for msg in history:
                if msg not in last_checked:

                    #Check les box pwns
                    result = re.compile(regexs["box_pwn"]).findall(msg)
                    if result and len(result[0]) == 3:
                        result = result[0]

                        if path.exists("users.txt"):
                            with open("users.txt", "r") as f:
                                users = json.loads(f.read())
                        else:
                            users = []

                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                self.notif["box_pwn"]["content"]["discord_id"] = user["discord_id"]

                                if result[1] == "system":
                                    self.notif["box_pwn"]["content"]["pwn"] = "root"
                                else:
                                    self.notif["box_pwn"]["content"]["pwn"] = result[1]

                                self.notif["box_pwn"]["content"]["box_name"] = result[2]
                                self.notif["box_pwn"]["state"] = True

                                checked.append(msg)
                                self.last_checked = (checked[::-1] + last_checked)[:20]

                                self.refresh_user(int(result[0])) #On met à jour les infos du user
                                return True

                    #Check les challenges pwns
                    result = re.compile(regexs["chall_pwn"]).findall(msg)
                    if result and len(result[0]) == 3:
                        result = result[0]

                        if path.exists("users.txt"):
                            with open("users.txt", "r") as f:
                                users = json.loads(f.read())
                        else:
                            users = []

                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                self.notif["chall_pwn"]["content"]["discord_id"] = user["discord_id"]
                                self.notif["chall_pwn"]["content"]["chall_name"] = result[1]
                                self.notif["chall_pwn"]["content"]["chall_type"] = result[2]
                                self.notif["chall_pwn"]["state"] = True

                                checked.append(msg)
                                self.last_checked = (checked[::-1] + last_checked)[:20]

                                self.refresh_user(int(result[0])) #On met à jour les infos du user
                                return True

                    #Check box incoming
                    result = re.compile(regexs["new_box_incoming"]).findall(msg)
                    if result and len(result[0]) == 2:
                        result = result[0]

                        self.notif["new_box"]["content"]["box_name"] = result[0]
                        self.notif["new_box"]["content"]["time"] = result[1]
                        self.notif["new_box"]["content"]["incoming"] = True
                        self.notif["new_box"]["state"] = True

                        checked.append(msg)
                        self.last_checked = (checked[::-1] + last_checked)[:20]

                        return True

                    #Check new box
                    result = re.compile(regexs["new_box_out"]).findall(msg)
                    if result and len(result[0]) == 1:
                        result = result[0]

                        self.notif["new_box"]["content"]["box_name"] = result[0]
                        self.notif["new_box"]["content"]["time"] = ""
                        self.notif["new_box"]["content"]["incoming"] = False
                        self.notif["new_box"]["state"] = True

                        checked.append(msg)
                        self.last_checked = (checked[::-1] + last_checked)[:20]

                        return True

                    checked.append(msg)

                    #Check VIP upgrade
                    result = re.compile(regexs["vip_upgrade"]).findall(msg)
                    if result and len(result[0]) == 1:
                        result = result[0]

                        if path.exists("users.txt"):
                            with open("users.txt", "r") as f:
                                users = json.loads(f.read())
                        else:
                            users = []

                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                self.notif["vip_upgrade"]["content"]["discord_id"] = user["discord_id"]
                                self.notif["vip_upgrade"]["state"] = True

                                checked.append(msg)
                                self.last_checked = (checked[::-1] + last_checked)[:20]

                                self.refresh_user(int(result[0])) #On met à jour les infos du user
                                return True

            self.last_checked = (checked[::-1] + last_checked)[:20]
