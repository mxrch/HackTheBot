from os import path
import httpx
import trio
import re
import json
from time import localtime, gmtime, strftime
import discord
from copy import deepcopy
from scrapy.selector import Selector
import config as cfg
import resources.charts as charts
import urllib
import pdb

class HTBot():
    def __init__(self, email, password, api_token=""):
        self.email = email
        self.password = password
        self.api_token = api_token

        self.is_vip = False

        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.85 Safari/537.36"
        }
        self.session = httpx.AsyncClient(headers=self.headers, timeout=360.0)
        self.locks = {
                "notif": trio.Lock(),
                "write_users": trio.Lock(),
                "write_boxs": trio.Lock(),
                "write_progress": trio.Lock(),
                "ippsec": trio.Lock(),
                "write_challs": trio.Lock(),
                "refresh_challs": trio.Lock()
                }

        self.payload = {'api_token': self.api_token}
        self.last_checked = []
        self.regexs = {
            "box_pwn": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> owned (.*) on <a(?:.*)profile\/(?:\d+)\">(.*)<\/a> <a(?:.*)",
            "chall_pwn": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> solved challenge <(?:.*)>(.*)<(?:.*)><(?:.*)> from <(?:.*)>(.*)<(?:.*)><(?:.*)",
            "new_box_incoming": "(?:.*)Get ready to spill some (?:.* blood .*! <.*>)(.*)<(?:.* available in <.*>)(.*)<(?:.*)><(?:.*)",
            "new_box_out": "(?:.*)>(.*)<(?:.*) is mass-powering on! (?:.*)",
            "vip_upgrade": "(?:.*)profile\/(\d+)\">(?:.*)<\/a> became a <(?:.*)><(?:.*)><(?:.*)> V.I.P <(?:.*)",
            "writeup_links": "Submitted By: <a href=(?:.*?)>(.*?)<(?:.*?)Url: (?:.*?)href=\"(.*?)\"",
            "check_vip": "(?:.*)Plan\: <span class=\"c-white\">(\w*)<(?:.*)",
            "owns": "owned (challenge|user|root|) <(?:.*?)>(?: |)<(?:.*?)>(?: |)(.*?)(?: |)<",
            "chall": "panel-tools\"> (\d*\/\d*\/\d*) (?:.*?)\"text-(success|warning|danger)\">(?:.*?)(?:\[(\d*?) Points\]|) <\/span> (.*?) \[by <(?:.*?)>(.*?)<\/a>\](?:.*?)\[(\d*?) solvers\](?:.*?)challenge=\"(.*?)\" data-toggle=(?:.*?)Rate Pro\">(\d*?) <(?:.*?)Rate Sucks\">(\d*?) <(?:.*?)> First Blood: <(?:.*?)>(.*?)<(?:.*?)><\/span><br><br>(.*?)<br> <br> (?:<p|<\/div)",
            "chall_diff": "diffchart(\d*)\"\)\.sparkline\((\[.*?\])",
            "chall_status": "<h3>(Active|Retired) \((?:\d*?)\)<\/h3>"
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

        if path.exists("challenges.txt"):
            with open("challenges.txt", "r") as f:
                self.challs = json.loads(f.read())
        else:
            self.challs = []

        if path.exists("progress.txt"):
            with open("progress.txt", "r") as f:
                self.progress = json.loads(f.read())
        else:
            self.progress = []

        if path.exists("resources/ippsec.txt"):
            with open("resources/ippsec.txt", "r") as f:
                self.ippsec_db = json.loads(f.read())
        else:
            self.ippsec_db = []


    async def write_users(self, users):
        async with self.locks["write_users"]:
            self.users = users
            with open("users.txt", "w") as f:
                f.write(json.dumps(users))


    async def write_boxs(self, boxs):
        async with self.locks["write_boxs"]:
            self.boxs = boxs
            with open("boxs.txt", "w") as f:
                f.write(json.dumps(boxs))


    async def write_challs(self, challs):
        async with self.locks["write_challs"]:
            self.challs = challs
            with open("challenges.txt", "w") as f:
                f.write(json.dumps(challs))


    async def write_progress(self, progress):
        async with self.locks["write_progress"]:
            self.progress = progress
            with open("progress.txt", "w") as f:
                f.write(json.dumps(progress))


    async def login(self):
        req = await self.session.get("https://www.hackthebox.eu/login")

        html = req.text
        csrf_token = re.findall(r'type="hidden" name="_token" value="(.+?)"', html)

        if not csrf_token:
            return False

        data = {
            "_token": csrf_token[0],
            "email": self.email,
            "password": self.password
        }

        req = await self.session.post('https://www.hackthebox.eu/login', data=data)

        if req.status_code == 200:
            print("Connecté à HTB !")
            return True

        print("Connexion impossible.")
        return False


    async def refresh_boxs(self):
        print("Rafraichissement des boxs...")

        req = await self.session.get("https://www.hackthebox.eu/api/machines/get/all/", params=self.payload, headers=self.headers)

        if req.status_code == 200:
            new_boxs = json.loads(req.text)
            _req = await self.session.get("https://www.hackthebox.eu/api/machines/difficulty?api_token=" + self.api_token, headers=self.headers)

            # Get difficulty ratings
            if req.status_code == 200:
                difficulty = json.loads(_req.text)

                count = 0
                for box in new_boxs:
                    for diff in difficulty:
                        if box["id"] == diff["id"]:
                            new_boxs[count]["rates"] = {"difficulty": diff["difficulty_ratings"]}
                            break

                    count += 1

                await self.write_boxs(new_boxs)
                print("La liste des boxs a été mise à jour !")
                return True

        return False


    async def get_box(self, name="name", matrix=False, last=False):
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
            req = await self.session.get("https://www.hackthebox.eu/api/machines/get/matrix/" + str(box["id"]), params=self.payload, headers=self.headers)
            if req.status_code == 200:
                matrix_data = json.loads(req.text)
            else:
                return False

            matrix_url = urllib.parse.quote_plus(charts.templates["matrix"].format(matrix_data["aggregate"], matrix_data["maker"]), safe=';/?:@&=+$,').replace('+', '%20').replace('%0A', '\\n')


        embed = discord.Embed(title=box["name"], color=0x9acc14, url="https://www.hackthebox.eu/home/machines/profile/" + str(box["id"]))
        embed.set_thumbnail(url=box["avatar_thumb"])
        embed.add_field(name="IP", value=str(box["ip"]))
        if box["os"].lower() == "windows":
            emoji = cfg.emojis["windows"] + " "
        elif box["os"].lower() == "linux":
            emoji = cfg.emojis["linux"] + " "
        else:
            emoji = ""
        embed.add_field(name="OS", value=emoji + box["os"])
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

        embed.add_field(name="Difficulty", value="{} ({} points)".format(difficulty, box["points"]))
        embed.add_field(name="Rating", value="⭐ {}".format(box["rating"]))

        if sum(box["rates"]["difficulty"]) >= 1:
            count = 0
            score = 0.0
            diff_ratings = box["rates"]["difficulty"]
            for rating in diff_ratings:
                score += (rating * count)
                count += 1
            real_difficulty = round(score / sum(diff_ratings), 1)
            embed.add_field(name="Real difficulty", value="🛡️ {}/10".format(real_difficulty))
        else:
            embed.add_field(name="Real difficulty", value="🛡️ -")

        embed.add_field(name="Owns", value="👤 {} #️⃣󠁲󠁯󠁯󠁴󠁿 {}".format(box["user_owns"], box["root_owns"]))

        if box["retired"]:
            status = "Retired"
        else:
            status = "Active"
        embed.add_field(name="Status", value=status)
        embed.add_field(name="Release", value="/".join("{}".format(box["release"]).split("-")[::-1]))
        embed.add_field(name=" ឵឵", value=" ឵឵")

        if matrix:
            embed.set_image(url=matrix_url)

        if box["maker2"]:
            embed.set_footer(text="Makers : {} & {}".format(box["maker"]["name"], box["maker2"]["name"]), icon_url=box["avatar_thumb"])
        else:
            embed.set_footer(text="Maker : {}".format(box["maker"]["name"]), icon_url=box["avatar_thumb"])

        return {"embed": embed}


    async def verify_user(self, discord_id, htb_acc_id):
        req = await self.session.get("https://www.hackthebox.eu/api/users/identifier/" + htb_acc_id, headers=self.headers)

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

            await self.write_users(users)
            await self.refresh_user(user_info["user_id"], new=True) #On scrape son profil

            return user_info["rank"]

        else:
            return "wrong_id"


    def discord_htb_converter(self, id, discord_to_htb=False, htb_to_discord=False):
        users = self.users

        if discord_to_htb:
            for user in users:
                if user["discord_id"] == id:
                    return user["htb_id"]
            return False

        elif htb_to_discord:
            for user in users:
                if user["htb_id"] == id:
                    return user["discord_id"]
            return False


    async def htb_id_by_name(self, name):
        params = {
            'username': name,
            'api_token': self.api_token
        }

        req = await self.session.post("https://www.hackthebox.eu/api/user/id", params=params, headers=self.headers)

        try:
            user = json.loads(req.text)
            return user["id"]
        except json.decoder.JSONDecodeError:
            return False


    async def get_user(self, htb_id):
        results = await self.extract_user_info(htb_id)
        infos = results["infos"]

        if infos["vip"]:
            vip = "  💠"
        else:
            vip = ""

        if infos["team"]:
            team = " | 🏡 " + infos["team"]
        else:
            team = ""

        embed = discord.Embed(title=infos["username"] + vip, color=0x9acc14, description="🎯 {} • 🏆 {} • 👤 {} • ⭐ {}".format(infos["points"], infos["systems"], infos["users"], infos["respect"]))
        embed.set_thumbnail(url=infos["avatar"])
        embed.add_field(name="About", value="📍 {} | 🔰 {}{}\n\n**Ownership** : {} | **Rank** : {} | ⚙️ **Challenges** : {}".format(infos["country"], infos["level"], team, infos["ownership"], infos["rank"], infos["challs"]))

        return embed


    async def refresh_all_challs(self):
        print("Rafraichissement des challenges...")
        categories = ["Reversing", "Crypto", "Stego", "Pwn", "Web", "Misc", "Forensics", "Mobile", "OSINT"]

        async with trio.open_nursery() as nursery:
            for category in categories:
                nursery.start_soon(self.refresh_chall, category)

        print("Les challenges ont été mis à jour !")

    async def refresh_chall(self, category):
        new_challs = await self.extract_challs(category)
        if not new_challs:
            print("Erreur lors du refresh des challenges de la catégorie {}.".format(category))
            return False

        async with self.locks["refresh_challs"]:
            challs = self.challs

            if challs:
                # Check if a chall is removed (yes, it happens)
                old_chall_ids = [chall["id"] for chall in challs if chall["category"].lower() == category.lower()]
                for chall in new_challs:
                    if chall["id"] in old_chall_ids:
                        old_chall_ids.remove(chall["id"])

                if old_chall_ids: # If there's still one
                    for old_chall_id in old_chall_ids:
                        count = 0
                        for chall in challs:
                            if chall["id"] == old_chall_id:
                                print("Un chall a été retiré !")
                                del(challs[count])
                                break
                            count += 1

                count = 0
                for chall in challs:
                    new_count = 0
                    for new_chall in new_challs:
                        if chall["id"] == new_chall["id"]:
                            challs[count] = new_challs.pop(new_count)
                            break
                        new_count += 1
                    count += 1

                # If there's still a chall in the list, we can send a notif that a new chall got released
                if new_challs:
                    for chall in new_challs:
                        print("Nouveau chall détecté !")
                        self.challs.append(chall)

                challs = sorted(challs, key = lambda i: int(i['id']))

                await self.write_challs(challs)
                return True

            else:
                print("Rafraichissement initial des challenges !")
                await self.write_challs(new_challs)
                return True


    async def extract_challs(self, category):

        async def extract_challs_difficulty(html):
            challs = html.css('script').getall()[-1]
            results = re.compile(self.regexs["chall_diff"]).findall(challs)
            diff_list = []

            if results:
                for result in results:
                    diff_ratings = json.loads(result[1].replace(", ]", " ]"))
                    diff_list.append({"id": int(result[0]), "diff": diff_ratings})

                return diff_list

            return False

        req = await self.session.get("https://www.hackthebox.eu/home/challenges/" + category, headers=self.headers)
        if req.status_code == 200:
            body = req.text
            html = Selector(text=body)
            new_challs = []
            diff_list = await extract_challs_difficulty(html)
            if not diff_list:
                return False

            status_flag = None
            parts = html.css('section.content > div.container-fluid > *').getall()
            #infos = []
            for part in parts:
                status = re.compile(self.regexs["chall_status"]).findall(part)
                #print(status)
                if status:
                    status_flag = status[0]

                if status_flag:
                    part = part.replace("\n", "")
                    results = re.compile(self.regexs["chall"]).findall(part)
                    if results:
                        data = results[0]

                        id = int(data[6])
                        for chall in diff_list:
                            if chall["id"] == id:
                                diff_ratings = chall["diff"]

                        if data[1] == "success":
                            difficulty = "Easy"
                        elif data[1] == "warning":
                            difficulty = "Medium"
                        elif data[1] == "danger":
                            difficulty = "Hard"
                        else:
                            print("Erreur : difficulté inconnue.")
                            return False

                        if data[2]:
                            points = int(data[2])
                        else:
                            points = 0

                        description = data[10].replace("â€™", "'").replace("<br>", "\n").replace("</p><p>", "\n").replace("<p>", "").replace("</p>", "").strip()

                        new_chall = {
                            "id": id,
                            "name": data[3],
                            "category": category,
                            "difficulty": difficulty,
                            "points": points,
                            "owns": int(data[5]),
                            "rates": {
                                "pro": int(data[7]),
                                "sucks": int(data[8]),
                                "difficulty": diff_ratings
                            },
                            "release": data[0],
                            "status": status_flag,
                            "maker": data[4],
                            "blood": data[9],
                            "description": description
                        }

                        new_challs.append(new_chall)

            return new_challs

        return False


    async def refresh_all_users(self):
        print("Rafraichissement des users...")
        users = self.users

        async with trio.open_nursery() as nursery:
            for user in users:
                nursery.start_soon(self.refresh_user, user["htb_id"])

        print("Les users ont été mis à jour !")


    async def refresh_user(self, htb_id, new=False):
        users = self.users
        progress = self.progress

        count = 0
        for user in users:
            if user["htb_id"] == htb_id:
                results = await self.extract_user_info(htb_id)
                if results:
                    infos = results["infos"]
                    owns = results["owns"]

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
                    users[count]["vip"] = infos["vip"]
                    users[count]["team"] = infos["team"]

                    if new:
                        async with self.locks["notif"]: # We lock notif setting to 1 task to avoid overwriting notif values
                            print("New user détecté !")
                            self.notif["new_user"]["content"]["discord_id"] = user["discord_id"]
                            self.notif["new_user"]["content"]["htb_id"] = user["htb_id"]
                            self.notif["new_user"]["content"]["level"] = infos["level"]
                            self.notif["new_user"]["state"] = True
                            await trio.sleep(6) # As notifs are checked every 3 seconds, we wait 6 secs to be sure

                    else:
                        async with self.locks["notif"]: # We lock notif setting to 1 task to avoid overwriting notif values
                            if users[count]["level"] != infos["level"]:
                                self.notif["update_role"]["content"]["discord_id"] = users[count]["discord_id"]
                                self.notif["update_role"]["content"]["prev_rank"] = users[count]["level"]
                                self.notif["update_role"]["content"]["new_rank"] = infos["level"]
                                self.notif["update_role"]["state"] = True
                                await trio.sleep(6) # Since notifs are checked every 3 seconds, we wait 6 secs to be sure

                    users[count]["level"] = infos["level"]
                    users[count]["rank"] = infos["rank"]
                    users[count]["challs"] = infos["challs"]
                    users[count]["ownership"] = infos["ownership"]

                    await self.write_users(users)

                    discord_id = self.discord_htb_converter(htb_id, htb_to_discord=True)

                    progress_ids = [u["discord_id"] for u in progress]
                    if discord_id not in progress_ids:
                        progress.append({
                            "discord_id": discord_id,
                            "working_on": None,
                            "pwns": []
                        })

                    _count = 0
                    for _user in progress:
                        if _user["discord_id"] == discord_id:
                            is_present_flag = True
                            progress[_count]["pwns"] = owns

                            if _user["working_on"]: # We reset the working on state if user got user and root, or owned a chall
                                user_flag = False
                                root_flag = False
                                chall_flag = False
                                for pwn in _user["pwns"]:
                                    if pwn["type"].lower() == _user["working_on"]["type"].lower() and pwn["name"].lower() == _user["working_on"]["name"].lower():
                                        if pwn["type"].lower() == "box":
                                            if pwn["level"].lower() == "user":
                                                user_flag = True
                                            elif pwn["level"].lower() == "root":
                                                root_flag = True
                                        elif pwn["type"].lower() == "chall":
                                            chall_flag = True

                                if (user_flag and root_flag) or chall_flag:
                                    progress[_count]["working_on"] = None

                            break

                        _count += 1

                    await self.write_progress(progress)
                    break

            count += 1


    async def extract_user_info(self, htb_id):
        infos = {}
        req = await self.session.get("https://www.hackthebox.eu/home/users/profile/" + str(htb_id), headers=self.headers)

        if req.status_code == 200:
            body = req.text
            html = Selector(text=body)

            # User infos
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
            if html.css('div.header-title > h3 > i.fa-star'):
                infos["vip"] = True
            else:
                infos["vip"] = False

            if html.css('div.header-title > small > i.fa-users'):
                infos["team"] = html.css('div.header-title > small > a::text').get()
            else:
                infos["team"] = False

            # User owns
            owns = html.css('div.v-timeline').get()
            results = re.compile(self.regexs["owns"]).findall(owns)

            temp_owns = []

            if results:
                for own in results:
                    if own[0].lower() == "user" or own[0].lower() == "root":
                        temp_owns.append({"type": "box", "level": own[0], "name": own[1].capitalize()})
                    elif own[0].lower() == "challenge":
                        temp_owns.append({"type": "challenge", "level": None, "name": own[1].capitalize()})

            return {"infos": infos, "owns": temp_owns}

        return False


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

        return board


    async def shoutbox(self):

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

        req = await self.session.post("https://www.hackthebox.eu/api/shouts/get/initial/html/30?api_token=" + self.api_token, headers=self.headers)

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
                                await self.refresh_user(int(result[0])) #On met à jour les infos du user

                                return True

                    #Check les challenges pwns
                    result = re.compile(regexs["chall_pwn"]).findall(msg)
                    if result and len(result[0]) == 3:
                        result = result[0]
                        for user in users:
                            if str(user["htb_id"]) == result[0]:
                                notif_chall_pwn(result, user)
                                update_last_checked(msg, checked, last_checked)
                                await self.refresh_user(int(result[0])) #On met à jour les infos du user

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
                                await self.refresh_user(int(result[0])) #On met à jour les infos du user

                                return True

                    checked.append(msg)

            self.last_checked = deepcopy((checked[::-1] + last_checked)[:50])


    def list_boxes(self, type="", remaining=False, discord_id=None):

        if remaining:
            found_flag = False
            for user in self.users:
                if user["discord_id"] == discord_id:
                    username = user["username"]
                    found_flag = True
            if not found_flag:
                return {"status": "not_sync"}

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

        if remaining:
            progress = self.progress
            to_delete = []
            for diff in difficulty.keys():
                count = 0
                for box in difficulty[diff]["boxs"]:
                    for user in progress:
                        if user["discord_id"] == discord_id:
                            pwned_user_flag = False
                            pwned_root_flag = False
                            for pwn in user["pwns"]:
                                if pwn["type"].lower() == "box" and pwn["name"].lower() == box["name"].lower() and pwn["level"].lower() == "user":
                                    pwned_user_flag = True
                                elif pwn["type"].lower() == "box" and pwn["name"].lower() == box["name"].lower() and pwn["level"].lower() == "root":
                                    pwned_root_flag = True

                                if pwned_user_flag and pwned_root_flag:
                                    to_delete.append(difficulty[diff]["boxs"][count])
                                    break
                            break
                    count += 1

            for box_to_delete in to_delete:
                found_flag = False
                for diff in difficulty.keys():
                    count = 0
                    for box in difficulty[diff]["boxs"]:
                        if box["name"].lower() == box_to_delete["name"].lower():
                            found_flag = True
                            del(difficulty[diff]["boxs"][count])
                            break

                        count += 1

                    if found_flag:
                        break

        #If we have to list only boxs of a certain difficulty :
        if type:
            if difficulty[type]["boxs"]:
                count = 0
                for box in difficulty[type]["boxs"]:
                    count += 1
                    # Real difficulty
                    if sum(box["rates"]["difficulty"]) >= 1:
                        _count = 0
                        score = 0.0
                        diff_ratings = box["rates"]["difficulty"]
                        for rating in diff_ratings:
                            score += (rating * _count)
                            _count += 1
                        real_difficulty = "🛡️ {}/10".format(round(score / sum(diff_ratings), 1))
                    else:
                        real_difficulty = "🛡️ -"
                    # OS emoji
                    if box["os"].lower() == "windows":
                        emoji = cfg.emojis["windows"] + " "
                    elif box["os"].lower() == "linux":
                        emoji = cfg.emojis["linux"] + " "
                    else:
                        emoji = ""
                    difficulty[type]["output"] = "{}{}. {}**{}** (⭐ {}) ({})\n".format(difficulty[type]["output"], count, emoji, box["name"], box["rating"], real_difficulty)

            else:
                difficulty[type]["output"] = "*Empty*"

            if remaining:
                embed = discord.Embed(color=0x9acc14, title="Active boxes 💻 | {}".format(type.capitalize()), description="**Remaining for {}**".format(username))
            else:
                embed = discord.Embed(color=0x9acc14, title="Active boxes 💻 | {}".format(type.capitalize()))

            embed.add_field(name=type.capitalize(), value=difficulty[type]["output"], inline=False)

        else:
            if remaining:
                embed = discord.Embed(color=0x9acc14, title="Active boxes 💻", description="**Remaining for {}**".format(username))
            else:
                embed = discord.Embed(color=0x9acc14, title="Active boxes 💻")

            for diff in difficulty:
                if difficulty[diff]["boxs"]:
                    count = 0
                    for box in difficulty[diff]["boxs"]:
                        count += 1
                        # Real difficulty
                        if sum(box["rates"]["difficulty"]) >= 1:
                            _count = 0
                            score = 0.0
                            diff_ratings = box["rates"]["difficulty"]
                            for rating in diff_ratings:
                                score += (rating * _count)
                                _count += 1
                            real_difficulty = "🛡️ {}/10".format(round(score / sum(diff_ratings), 1))
                        else:
                            real_difficulty = "🛡️ -"
                        # OS emoji
                        if box["os"].lower() == "windows":
                            emoji = cfg.emojis["windows"] + " • "
                        elif box["os"].lower() == "linux":
                            emoji = cfg.emojis["linux"] + " • "
                        else:
                            emoji = ""
                        difficulty[diff]["output"] = "{}{}. {}**{}** (⭐ {}) ({})\n".format(difficulty[diff]["output"], count, emoji, box["name"], box["rating"], real_difficulty)

                else:
                    difficulty[diff]["output"] = "*Empty*"

                embed.add_field(name=diff.capitalize(), value=difficulty[diff]["output"], inline=False)

        return {"embed": embed, "status": "ok"}


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


    def check_chall(self, chall_name):
        """Check if a chall exists and return its status"""
        challs = self.challs

        for chall in challs:
            if chall["name"].lower() == chall_name.lower():
                if chall["status"].lower() == "active":
                    return "active"
                else:
                    return "retired"

        return False


    def account(self, discord_id, delete=False, shoutbox_onoff=False):
        pass
        # users = self.users
        # if action:
        #     if action.lower() == "-delete":
        #         for user in users:
        #             if user["discord_id"] == discord_id:
        #                 users.pop(user)
        #                 self.write_users(users)
        #
        #                 return "success"
        #
        #     elif action.lower() == "-shoutbox":
        #         pass
        #     else:
        #         return "wrong_arg"


    async def writeup(self, box_name, links=False, page=1):
        boxs = self.boxs
        regexs = self.regexs

        for box in boxs:
            if box["name"].lower() == box_name.lower():
                if links:
                    req = await self.session.get("https://www.hackthebox.eu/home/machines/profile/" + str(box["id"]), headers=self.headers)

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
                    req = await self.session.get("https://www.hackthebox.eu/home/machines/writeup/" + str(box["id"]), headers=self.headers)

                    if req.status_code == 200:
                        pathname = 'resources/writeups/' + box["name"].lower() + '.pdf'
                        if not path.exists(pathname):
                            open(pathname, 'wb').write(req.content)

                        file = discord.File(pathname, filename=box["name"].lower() + '.pdf')
                        return file

                    return False


    def ippsec(self, search, page):
        db = self.ippsec_db

        results = []

        for step in db:
            if all(s in (step["machine"] + step["line"]).lower() for s in search.lower().split()):

                seconds = step["timestamp"]["minutes"] * 60 + step["timestamp"]["seconds"]
                results.append({"title": step["machine"].strip(),
                                "description": step["line"].strip(),
                                "url": "https://youtube.com/watch?v={}&t={}".format(step["videoId"], seconds),
                                "timestamp": strftime("%H:%M:%S", gmtime(seconds))})

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


    async def check_if_host_is_vip(self):
        print("Détection du VIP...")
        req = await self.session.post("https://www.hackthebox.eu/api/subscriptions/snippet", params=self.payload, headers=self.headers)
        if req.status_code == 200:
            body = req.text
            status = re.compile(self.regexs["check_vip"]).findall(body)
            if status:
                if status[0] == "VIP":
                    print("Vous êtes VIP.")
                    self.is_vip = True
                    return True
                else:
                    print("Vous n'êtes pas VIP.")
                    self.is_vip = False
                    return True

        print("Erreur.")
        return False


    def check_member_vip(self, discord_id):
        users = self.users
        for user in users:
            if user["discord_id"] == discord_id:
                if user["vip"]:
                    return "vip"
                else:
                    return "free"

        return "not_sync"


    async def refresh_ippsec(self):
        print("Rafraichissement de la base de données d'Ippsec...")

        req = await self.session.get("https://raw.githubusercontent.com/IppSec/ippsec.github.io/master/dataset.json", headers=self.headers)
        if req.status_code == 200:
            async with self.locks["ippsec"]:
                self.ippsec_db = json.loads(req.text)
                with open("resources/ippsec.txt", "w") as f:
                    f.write(req.text)

                print("La base de données d'Ippsec a été mise à jour !")
                return True

        return False


    async def get_progress(self, target, box=False, chall=False):
        progress = self.progress

        working_on = []
        max = 15

        if box:
            boxs = self.boxs
            for _box in boxs:
                if _box["name"].lower() == target.lower():
                    thumbnail = _box["avatar_thumb"]
                    name = _box["name"]
                    break

            user_owns = []
            root_owns = []

            for user in progress:
                if user["working_on"] and user["working_on"]["type"].lower() == "box" and user["working_on"]["name"].lower() == target.lower():
                    working_on.append(user["discord_id"])
                if len(working_on) >= max:
                    break

            users = [user["discord_id"] for user in progress]
            count = 0
            while users:
                for user in progress:
                    if user["discord_id"] in users:
                        if len(user["pwns"]) == count or (user["discord_id"] in user_owns and user["discord_id"] in root_owns):
                            users.remove(user["discord_id"])
                        else:
                            if user["pwns"][count]["type"].lower() == "box" and user["pwns"][count]["name"].lower() == target.lower():
                                if user["pwns"][count]["level"].lower() == "user":
                                    user_owns.append(user["discord_id"])
                                elif user["pwns"][count]["level"].lower() == "root":
                                    root_owns.append(user["discord_id"])
                count += 1

            if len(working_on) < max:
                for own in user_owns:
                    if own not in root_owns and own not in working_on:
                        working_on.append(own)
                    if len(working_on) >= max:
                        break

            if len(user_owns) > max:
                user_owns = user_owns[:max]

            if len(root_owns) > max:
                root_owns = root_owns[:max]

            return {
                "name": name,
                "thumbnail": thumbnail,
                "working_on": working_on,
                "user_owns": user_owns,
                "root_owns": root_owns
            }

        elif chall:
            challs = self.challs
            for _chall in challs:
                if _chall["name"].lower() == target.lower():
                    category = _chall["category"]
                    name = _chall["name"]
                    break

            chall_owns = []

            for user in progress:
                if user["working_on"] and user["working_on"]["type"].lower() == "challenge" and user["working_on"]["name"].lower() == target.lower():
                    working_on.append(user["discord_id"])
                if len(working_on) >= max:
                    break

            users = [user["discord_id"] for user in progress]
            count = 0
            while users or len(chall_owns) >= max:
                for user in progress:
                    if user["discord_id"] in users:
                        if len(user["pwns"]) == count:
                            users.remove(user["discord_id"])
                        else:
                            if user["pwns"][count]["type"].lower() == "challenge" and user["pwns"][count]["name"].lower() == target.lower():
                                chall_owns.append(user["discord_id"])
                                users.remove(user["discord_id"])
                count += 1

            return {
                "name": name,
                "category": category,
                "working_on": working_on,
                "chall_owns": chall_owns
            }

    async def get_chall(self, chall_name):
        challs = self.challs

        for chall in challs:
            if chall["name"].lower() == chall_name.lower():
                embed = discord.Embed(title="{} ({})".format(chall["name"], chall["category"]), color=0x9acc14)

                embed.add_field(name="Rating", value="👍 {} 👎 {}".format(chall["rates"]["pro"], chall["rates"]["sucks"]), inline=True)
                embed.add_field(name="Solvers", value="#️⃣ {}".format(chall["owns"]), inline=True)
                embed.add_field(name="Difficulty", value="{} ({} points)".format(chall["difficulty"], chall["points"]), inline=True)

                embed.add_field(name="Release", value=chall["release"])
                embed.add_field(name="Status", value=chall["status"], inline=True)

                count = 0
                score = 0.0
                diff_ratings = chall["rates"]["difficulty"]
                for rating in diff_ratings:
                    score += (rating * count)
                    count += 1
                real_difficulty = round(score / sum(diff_ratings), 1)
                embed.add_field(name="Real difficulty", value="🛡️ {}/10".format(real_difficulty), inline=True)
                embed.add_field(name="Description", value=chall["description"])

                embed.set_footer(text="Maker : {}".format(chall["maker"]))

                return {"embed": embed}

    async def work_on(self, target, discord_id, box=False, chall=False, pwned=False):
        progress = self.progress

        count = 0
        for user in progress:
            if user["discord_id"] == discord_id:
                if box:
                    # We check if the user is already root
                    user_flag = False
                    root_flag = False
                    for pwn in user["pwns"]:
                        if pwn["type"] == "box" and pwn["name"].lower() == target.lower():
                            if pwn["level"] == "user":
                                user_flag = True
                            elif pwn["level"] == "root":
                                root_flag = True

                            if user_flag and root_flag:
                                return "already_owned"

                    boxs = self.boxs
                    for box in boxs:
                        if box["name"].lower() == target.lower():
                            progress[count]["working_on"] = {"type": "box", "name": box["name"]}
                            await self.write_progress(progress)
                            return "success"

                elif chall:
                    # We check if the user has already owned the challenge
                    for pwn in user["pwns"]:
                        if pwn["type"] == "challenge" and pwn["name"].lower() == target.lower():
                            return "already_owned"

                    challs = self.challs
                    for chall in challs:
                        if chall["name"].lower() == target.lower():
                            progress[count]["working_on"] = {"type": "challenge", "name": chall["name"]}
                            await self.write_progress(progress)
                            return "success"

                elif pwned:
                    progress[count]["working_on"] = None
                    await self.write_progress(progress)
                    return "success"

            count += 1

        return False
