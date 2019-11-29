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
        req = requests.get("https://www.hackthebox.eu/api/machines/get/all/", params=self.payload, headers=self.headers)

        if req.status_code == 200:
            with open("boxs.txt", "w") as f:
                f.write(req.text)
            return True
        else:
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
        embed.add_field(name="Owns", value="🤵 {} #️⃣󠁲󠁯󠁯󠁴󠁿 {}".format(box["user_owns"], box["root_owns"]))
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
                "htb_rank": user_info["rank"]
            })

            with open("users.txt", "w") as f:
                f.write(json.dumps(users))

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

    def get_user(self, id):
        req = self.session.get("https://www.hackthebox.eu/home/users/profile/" + id)
        body = req.text
        html = Selector(text=body)
        username = html.css('div.header-title > h3::text').get().strip()
        avatar = html.css('div.header-icon > img::attr(src)').get()
        points = html.css('div.header-title > small > span[title=Points]::text').get().strip()
        systems = html.css('div.header-title > small > span[title="Owned Systems"]::text').get().strip()
        users = html.css('div.header-title > small > span[title="Owned Users"]::text').get().strip()
        respect = html.css('div.header-title > small > span[title=Respect]::text').get().strip()
        country = Selector(text=html.css('div.header-title > small > span').getall()[4]).css('span::attr(title)').get().strip()
        level = html.css('div.header-title > small > span::text').extract()[-1].strip()
        rank = re.search(r'position (\d+) of the Hall of Fame', body).group(1)
        challs = re.search(r'has solved (\d+) challenges', body).group(1)
        ownership = html.css('div.progress-bar-success > span::text').get()

        embed = discord.Embed(title=username, color=0x9acc14, description="🎯 {} • 🏆 {} • 👤 {} • ⭐ {}".format(points, systems, users, respect))
        embed.set_thumbnail(url=avatar)
        embed.add_field(name="About", value="📍 {} | 🔰 {}\n\n**Ownership** : {} | **Rank** : {} | ⚙️ **Challenges** : {}".format(country, level, ownership, rank, challs))

        return embed
