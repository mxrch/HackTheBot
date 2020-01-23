from os import path
import requests
import re
import json
import time
import discord
from copy import deepcopy
from scrapy.selector import Selector
import plotly.graph_objects as go
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
            "new_box_incoming": "(?:.*)Get ready to spill some (?:.* blood .*! <.*>)(.*)<(?:.* available in <.*>)(.*)<(?:.*)><(?:.*)",
            "new_box_out": "(?:.*)>(.*)<(?:.*) is mass-powering on! (?:.*)",
            "vip_upgrade": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> became a <(?:.*)><(?:.*)><(?:.*)> V.I.P <(?:.*)",
            "writeup_links" : "Submitted By: <a href=(?:.*?)>(.*?)<(?:.*?)Url: (?:.*?)href=\"(.*?)\""

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
        if path.exists("users.txt"):
            with open("users.txt", "r") as f:
                self.users = json.loads(f.read())
        else:
            self.users = []

        if path.exists("boxs.txt"):
            with open("boxs.txt", "r") as f:
                self.boxs = json.loads(f.read())
        else:
            self.boxs = []


    def write_users(self, users):
        self.users = users
        with open("users.txt", "w") as f:
            f.write(json.dumps(users))


    def write_boxs(self, boxs):
        self.boxs = boxs
        with open("boxs.txt", "w") as f:
            f.write(json.dumps(boxs))


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

        req = self.session.get("https://www.hackthebox.eu/api/machines/get/all/", params=self.payload, headers=self.headers)

        if req.status_code == 200:
            new_boxs = json.loads(req.text)
            old_boxs = self.boxs
            old_boxs_ids = [d['id'] for d in old_boxs]
            boxs = []

            for box in new_boxs:
                #If there is a new box
                if box["id"] not in old_boxs_ids:
                    old_boxs.append(box)

            for o_box, n_box in zip(old_boxs, new_boxs):
                o_box["name"] = n_box["name"]
                o_box["avatar_thumb"] = n_box["avatar_thumb"]
                o_box["ip"] = n_box["ip"]
                o_box["os"] = n_box["os"]
                o_box["points"] = n_box["points"]
                o_box["rating"] = n_box["rating"]
                o_box["retired"] = n_box["retired"]
                o_box["retired_date"] = n_box["retired_date"]
                o_box["user_owns"] = n_box["user_owns"]
                o_box["root_owns"] = n_box["root_owns"]
                o_box["release"] = n_box["release"]
                o_box["maker"] = n_box["maker"]
                o_box["maker2"] = n_box["maker2"]
                o_box["free"] = n_box["free"]

                boxs.append(o_box)

            self.write_boxs(boxs)
            print("La liste des boxs a été mise à jour !")
            return True

        return False


    def get_box(self, name="name", matrix=False, last=False):
        boxs = self.boxs

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

        if matrix:
            req = requests.get("https://www.hackthebox.eu/api/machines/get/matrix/" + str(box["id"]), params=self.payload, headers=self.headers)
            if req.status_code == 200:
                matrix_data = json.loads(req.text)

            with open("resources/template_matrix.txt", "r") as f:
                template = json.loads(f.read())

            template["data"][0]["r"] = matrix_data["aggregate"]
            template["data"][1]["r"] = matrix_data["maker"]

            fig = go.Figure(template)

            fig.write_image("resources/matrix.png")


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

        if matrix:
            file = discord.File("resources/matrix.png", filename="matrix.png")
            embed.set_image(url="attachment://matrix.png")
        else:
            file = ""

        if box["maker2"]:
            embed.set_footer(text="Makers : {} & {}".format(box["maker"]["name"], box["maker2"]["name"]), icon_url=box["avatar_thumb"])
        else:
            embed.set_footer(text="Maker : {}".format(box["maker"]["name"]), icon_url=box["avatar_thumb"])

        return {"embed": embed, "file": file}


    def verify_user(self, discord_id, htb_acc_id):
        req = requests.get("https://www.hackthebox.eu/api/users/identifier/" + htb_acc_id, headers=self.headers)

        if req.status_code == 200:
            users = self.users

            user_info = json.loads(req.text)

            for user in users:
                if user["discord_id"] == discord_id:
                    return "already_in"

            users.append({
                "discord_id": discord_id,
                "htb_id": user_info["user_id"],
            })

            self.write_users(users)

            self.refresh_user(user_info["user_id"], new=True) #On scrape son profil

            return user_info["rank"]
        else:
            return "wrong_id"


    def discord_to_htb_id(self, discord_id):
        users = self.users

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


    def extract_user_info(self, htb_id):
        infos = {}
        req = self.session.get("https://www.hackthebox.eu/home/users/profile/" + str(htb_id), headers=self.headers)

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


    def get_user(self, htb_id):
        infos = self.extract_user_info(htb_id)

        embed = discord.Embed(title=infos["username"], color=0x9acc14, description="🎯 {} • 🏆 {} • 👤 {} • ⭐ {}".format(infos["points"], infos["systems"], infos["users"], infos["respect"]))
        embed.set_thumbnail(url=infos["avatar"])
        embed.add_field(name="About", value="📍 {} | 🔰 {}\n\n**Ownership** : {} | **Rank** : {} | ⚙️ **Challenges** : {}".format(infos["country"], infos["level"], infos["ownership"], infos["rank"], infos["challs"]))

        return embed


    def refresh_user(self, htb_id, new=False):
        users = self.users

        count = 0
        for user in users:
            if user["htb_id"] == htb_id:
                infos = self.extract_user_info(htb_id)

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
                    self.notif["new_user"]["content"]["htb_id"] = users[count]["htb_id"]
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

        self.write_users(users)


    def refresh_all_users(self):
        users = self.users

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

        def update_last_checked(msg, checked, last_checked):
            checked.append(msg)
            self.last_checked = deepcopy((checked[::-1] + last_checked)[:40])

        def notif_box_pwn(result, user):
            self.notif["box_pwn"]["content"]["discord_id"] = user["discord_id"]

            if result[1] == "system":
                self.notif["box_pwn"]["content"]["pwn"] = "root"
            else:
                self.notif["box_pwn"]["content"]["pwn"] = result[1]

            self.notif["box_pwn"]["content"]["box_name"] = result[2]
            self.notif["box_pwn"]["state"] = True

        def notif_chall_pwn(result, user):
            self.notif["chall_pwn"]["content"]["discord_id"] = user["discord_id"]
            self.notif["chall_pwn"]["content"]["chall_name"] = result[1]
            self.notif["chall_pwn"]["content"]["chall_type"] = result[2]
            self.notif["chall_pwn"]["state"] = True

        def notif_box_incoming(result):
            self.notif["new_box"]["content"]["box_name"] = result[0]
            self.notif["new_box"]["content"]["time"] = result[1]
            self.notif["new_box"]["content"]["incoming"] = True
            self.notif["new_box"]["state"] = True

        def notif_new_box(result):
            self.notif["new_box"]["content"]["box_name"] = result[0]
            self.notif["new_box"]["content"]["time"] = ""
            self.notif["new_box"]["content"]["incoming"] = False
            self.notif["new_box"]["state"] = True

        def notif_vip_upgrade(user):
            self.notif["vip_upgrade"]["content"]["discord_id"] = user["discord_id"]
            self.notif["vip_upgrade"]["state"] = True

        req = self.session.post("https://www.hackthebox.eu/api/shouts/get/initial/html/20?api_token=" + self.api_token, headers=self.headers)

        if req.status_code == 200:
            history = deepcopy(json.loads(req.text)["html"])
            last_checked = deepcopy(self.last_checked)
            users = deepcopy(self.users)

            checked = deepcopy([])
            regexs = self.regexs

            for msg in history:
                if msg not in last_checked:

                    #Check les box pwns
                    result = re.compile(regexs["box_pwn"]).findall(msg)
                    if result and len(result[0]) == 3:
                        result = result[0]
                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                notif_box_pwn(result, user)
                                update_last_checked(msg, checked, last_checked)
                                self.refresh_user(int(result[0])) #On met à jour les infos du user

                                return True

                    #Check les challenges pwns
                    result = re.compile(regexs["chall_pwn"]).findall(msg)
                    if result and len(result[0]) == 3:
                        result = result[0]
                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                notif_chall_pwn(result, user)
                                update_last_checked(msg, checked, last_checked)
                                self.refresh_user(int(result[0])) #On met à jour les infos du user

                                return True

                    #Check box incoming
                    result = re.compile(regexs["new_box_incoming"]).findall(msg)
                    if result and len(result[0]) == 2:
                        result = result[0]
                        old_time = self.notif["new_box"]["content"]["time"]
                        new_time = result[1]
                        if not old_time or (new_time.split(":")[0] == "15" and old_time.split(":")[0] != "15") or (new_time.split(":")[0] == "10" and old_time.split(":")[0] != "10") or (new_time.split(":")[0] == "05" and old_time.split(":")[0] != "05") or new_time.split(":")[0] == "01" or new_time.split(":")[0] == "00":
                            notif_box_incoming(result)
                            update_last_checked(msg, checked, last_checked)

                            return True

                    #Check new box
                    result = re.compile(regexs["new_box_out"]).findall(msg)
                    if type(result) is list and result and len(result) == 1:
                        notif_new_box(result)
                        update_last_checked(msg, checked, last_checked)

                        return True

                    #Check VIP upgrade
                    result = re.compile(regexs["vip_upgrade"]).findall(msg)
                    if type(result) is list and result and len(result) == 1:
                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                notif_vip_upgrade(user)
                                update_last_checked(msg, checked, last_checked)
                                self.refresh_user(int(result[0])) #On met à jour les infos du user

                                return True

                    checked.append(msg)

            self.last_checked = deepcopy((checked[::-1] + last_checked)[:40])


    def list_boxs(self, type=""):
        boxs = self.boxs

        difficulty = {
            "easy": {
                "boxs": [],
                "output": ""
            },
            "medium": {
                "boxs": [],
                "output": ""
            },
            "hard": {
                "boxs": [],
                "output": ""
            },
            "insane": {
                "boxs": [],
                "output": ""
            }
        }

        for box in boxs:
            if not box["retired"]:
                if box["points"] == 20:
                    difficulty["easy"]["boxs"].append(box)
                elif box["points"] == 30:
                    difficulty["medium"]["boxs"].append(box)
                elif box["points"] == 40:
                    difficulty["hard"]["boxs"].append(box)
                elif box["points"] == 50:
                    difficulty["insane"]["boxs"].append(box)

        #If we have to list only boxs of a certain difficulty :
        if type:
            count = 0
            for box in difficulty[type]["boxs"]:
                count += 1
                difficulty[type]["output"] = "{}{}. **{}** ({} ⭐)\n".format(difficulty[type]["output"], count, box["name"], box["rating"])

            embed = discord.Embed(color=0x9acc14, title="Active boxs 💻 | {}".format(type.capitalize()))
            embed.add_field(name=type.capitalize(), value=difficulty[type]["output"], inline=False)

        else:
            embed = discord.Embed(color=0x9acc14, title="Active boxs 💻")
            for diff in difficulty:
                count = 0
                for box in difficulty[diff]["boxs"]:
                    count += 1
                    difficulty[diff]["output"] = "{}{}. **{}** ({} ⭐)\n".format(difficulty[diff]["output"], count, box["name"], box["rating"])

                embed.add_field(name=diff.capitalize(), value=difficulty[diff]["output"], inline=False)

        return embed


    def check_box(self, box_name):
        """Check if a box exists and return its status"""
        boxs = self.boxs

        for box in boxs:
            if box["name"].lower() == box_name.lower():
                if box["retired"]:
                    return "retired"
                else:
                    return "active"

        return False

    def account(self, discord_id, delete=False, shoutbox_onoff=False):
        users = self.users
        if action:
            if action.lower() == "-delete":
                for user in users:
                    if user["discord_id"] == discord_id:
                        users.pop(user)
                        self.write_users(users)

                        return "success"

            elif action.lower() == "-shoutbox":
                pass
            else:
                return "wrong_arg"

    def writeup(self, box_name, links=False, page=1):
        boxs = self.boxs
        regexs = self.regexs

        for box in boxs:
            if box["name"].lower() == box_name.lower():
                if links:
                    req = self.session.get("https://www.hackthebox.eu/home/machines/profile/" + str(box["id"]), headers=self.headers)

                    if req.status_code == 200:
                        body = req.text
                        html = Selector(text=body)

                        wpsection = html.css('div.panel.panel-filled').getall()[-1]
                        result = re.compile(regexs["writeup_links"]).findall(wpsection)

                        #If there are writeup links
                        if result and len(result[0]) == 2:
                            nb = len(result)
                            limit = 5 # Pagination
                            if nb/limit - nb//limit == 0.0:
                                total = nb//limit
                            else:
                                total = nb//limit + 1
                            if page > total:
                                return {"status": "too_high"}

                            else:
                                writeups = result[(limit*page-limit):(limit*page)]

                                text = ""
                                for wp in writeups:
                                    text += "**Auteur : {}**\n**Lien :** {}\n\n".format(wp[0], wp[1])

                                embed = discord.Embed(title="📚 Writeups submitted | {}".format(box["name"].capitalize()), color=0x9acc14, description=text)
                                embed.set_footer(text="📖 Page : {} / {}".format(page, total))

                                return {"status" : "found", "embed": embed}

                        else:
                            return {"status": "empty"}

                    return False

                else:
                    req = self.session.get("https://www.hackthebox.eu/home/machines/writeup/" + str(box["id"]), headers=self.headers)

                    if req.status_code == 200:
                        pathname = 'resources/writeups/' + box["name"].lower() + '.pdf'
                        if not path.exists(pathname):
                            open(pathname, 'wb').write(req.content)

                        file = discord.File(pathname, filename=box["name"].lower() + '.pdf')
                        return file

                    return False


    def ippsec(self, search, page):
        f = open('resources/ippsec.txt', 'r')
        db = json.loads(f.read())

        results = []

        for step in db:
            if all(s in (step["machine"] + step["line"]).lower() for s in search.lower().split()):

                seconds = step["timestamp"]["minutes"] * 60 + step["timestamp"]["seconds"]
                results.append({"title": step["machine"].strip(),
                                "description": step["line"].strip(),
                                "url": "https://youtube.com/watch?v={}&t={}".format(step["videoId"], seconds),
                                "timestamp": time.strftime("%H:%M:%S", time.gmtime(seconds))})

        if len(search) > 22:
            search = search[:22] + "..."

        if results:
            nb = len(results)
            limit = 6 # Pagination
            if nb/limit - nb//limit == 0.0:
                total = nb//limit
            else:
                total = nb//limit + 1
            if page > total:
                return {"status": "too_high"}

            else:
                results = results[(limit*page-limit):(limit*page)]
        else:
            return {"status": "not_found"}

        text = ""
        for a in results:
            text += "**{}** *({})*\n{}\n{}\n\n".format(a["title"], a["timestamp"], a["description"], a["url"])

        embed = discord.Embed(title="📚  Ippsec search | {}".format(search.capitalize()), color=0x9acc14, description=text)
        embed.set_footer(text="📖 Page : {} / {}".format(page, total))

        return {"status": "found", "embed": embed}
