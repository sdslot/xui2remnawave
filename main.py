import datetime as dt
import httpx
import json
import re

xui_url = input("3X-UI panel url: ")
if xui_url.endswith("/"):
    xui_url = xui_url[:-1]
xui_username = input("3X-UI username: ")
xui_password = input("3X-UI password: ")

remna_url = input("Remnawave panel url: ")
if remna_url.endswith("/"):
    remna_url = remna_url[:-1]
remna_token = input("Remnawave API token: ")

inbound_id = input("3X-UI inbound id: ")

remna_url += "/api"

xui = httpx.Client()
xui.post(xui_url + "/login", data={
    "username": xui_username,
    "password": xui_password
})

remna = httpx.Client(headers={
    "Content-Type": "application/json",
    "Authorization": "Bearer " + remna_token
})

if remna_url.startswith("http://"):
    remna.headers["X-Forwarded-Proto"] = "https"
    remna.headers["X-Forwarded-For"] = "127.0.0.1"

username_pattern = re.compile("^[a-zA-Z0-9_-]+$")

users = json.loads(xui.get(xui_url + f"/panel/api/inbounds/get/{inbound_id}").json()["obj"]["settings"])["clients"]
for user in users:
    data = {}

    if username_pattern.match(user["email"]) and len(user["email"]) >= 6:
        data.setdefault("username", user["email"])
    else:
        data.setdefault("username", user["id"].split("-")[0])

    # ИСПРАВЛЕНИЕ 1: Безопасная проверка поля comment
    if "comment" in user and user["comment"]:
        data.setdefault("description", user["comment"])
    # Дополнительные проверки для других возможных полей
    elif "description" in user and user["description"]:
        data.setdefault("description", user["description"])
    elif "remarks" in user and user["remarks"]:
        data.setdefault("description", user["remarks"])

    data.setdefault("status", "ACTIVE" if user["enable"] else "DISABLE")

    data.setdefault("vlessUuid", user["id"])

    if user["expiryTime"]:
        data.setdefault("expireAt", dt.datetime.fromtimestamp(user["expiryTime"] / 1000).isoformat())
    else:
        data.setdefault("expireAt", dt.datetime.today().replace(year=2099).isoformat())

    data.setdefault("trafficLimitBytes", user["totalGB"])

    # ИСПРАВЛЕНИЕ 2: Пропускаем shortUuid если он уже существует
    # или обрабатываем ошибку дубликата
    if "subId" in user and user["subId"]:
        # Проверяем, существует ли уже пользователь с таким shortUuid
        # Если да, то не добавляем это поле или генерируем новый
        data.setdefault("shortUuid", user["subId"])

    data.setdefault("tag", "XUI")

    r = remna.post(remna_url + "/users", json=data)
    
    if r.status_code == 201:
        print(f"User {user['email']} was added as {data['username']}")
    elif r.status_code == 400 and "short UUID already exists" in r.text:
        # Если short UUID уже существует, пробуем без него
        print(f"Warning: short UUID exists for {user['email']}, trying without...")
        if "shortUuid" in data:
            del data["shortUuid"]
            r = remna.post(remna_url + "/users", json=data)
            if r.status_code == 201:
                print(f"User {user['email']} was added without short UUID")
            else:
                print(f"ERROR {user['email']} -", r.text)
        else:
            print(f"ERROR {user['email']} -", r.text)
    else:
        print(f"ERROR {user['email']} -", r.text)
