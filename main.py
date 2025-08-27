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

print(f"Found {len(users)} users to migrate")

for index, user in enumerate(users, 1):
    print(f"\nProcessing user {index}/{len(users)}: {user.get('email', 'no-email')}")
    
    data = {}

    # Отладочная информация
    print(f"User keys: {list(user.keys())}")
    
    if username_pattern.match(user["email"]) and len(user["email"]) >= 6:
        data.setdefault("username", user["email"])
    else:
        data.setdefault("username", user["id"].split("-")[0])

    # БЕЗОПАСНАЯ проверка поля comment
    if "comment" in user and user["comment"]:
        data.setdefault("description", user["comment"])
        print(f"Using comment: {user['comment']}")
    elif "description" in user and user["description"]:
        data.setdefault("description", user["description"])
        print(f"Using description: {user['description']}")
    elif "remarks" in user and user["remarks"]:
        data.setdefault("description", user["remarks"])
        print(f"Using remarks: {user['remarks']}")
    else:
        print("No comment/description/remarks field found")

    data.setdefault("status", "ACTIVE" if user["enable"] else "DISABLE")

    data.setdefault("vlessUuid", user["id"])

    if user["expiryTime"]:
        data.setdefault("expireAt", dt.datetime.fromtimestamp(user["expiryTime"] / 1000).isoformat())
    else:
        data.setdefault("expireAt", dt.datetime.today().replace(year=2099).isoformat())

    # БЕЗОПАСНАЯ проверка поля totalGB - ИСПРАВЛЕНИЕ!
    if "totalGB" in user:
        data.setdefault("trafficLimitBytes", user["totalGB"])
        print(f"Using totalGB: {user['totalGB']}")
    elif "total" in user:
        data.setdefault("trafficLimitBytes", user["total"])
        print(f"Using total: {user['total']}")
    else:
        data.setdefault("trafficLimitBytes", 0)
        print("No totalGB/total field found, setting trafficLimitBytes to 0")

    # Временно убираем shortUuid чтобы избежать конфликтов
    if "subId" in user and user["subId"]:
        print(f"Found subId: {user['subId']} (but skipping to avoid conflicts)")

    data.setdefault("tag", "XUI")

    print(f"Sending data: {json.dumps(data, indent=2)}")
    
    try:
        r = remna.post(remna_url + "/users", json=data)
        
        if r.status_code == 201:
            print(f"✅ User {user['email']} was added as {data['username']}")
        elif r.status_code == 400 and "already exists" in r.text:
            if "username already exists" in r.text:
                print(f"⚠️  Username {data['username']} already exists, skipping...")
            elif "short UUID already exists" in r.text:
                print(f"⚠️  short UUID exists for {user['email']}, skipping...")
            else:
                print(f"⚠️  User already exists: {user['email']}, skipping...")
        else:
            print(f"❌ ERROR {user['email']} - Status: {r.status_code}", r.text)
            
    except Exception as e:
        print(f"❌ Exception for {user['email']}: {str(e)}")

print("\nMigration completed!")
