"""
format:
_id: Vars.DB_NAME
user_id: {
     "subs": {
        "ck": [],
        "as": [],
        ................
        ................
     },
     setting: {
        "file_name": "",
        "caption": "",
        ................
        .................
     }
}
.................
.................
.................
.................
"""

import asyncio
from loguru import logger
from pymongo import MongoClient
from bot import Vars, remove_site_sf
import time
import re

client = MongoClient(Vars.DB_URL)
db = client[Vars.DB_NAME]
users = db["users"]
acollection = db['premium']

uts = users.find_one({"_id": Vars.DB_NAME})

if not uts:
    uts = {'_id': Vars.DB_NAME}
    users.insert_one(uts)



pts = acollection.find_one({"_id": Vars.DB_NAME})
if not pts:
    pts = {'_id': Vars.DB_NAME}
    acollection.insert_one(pts)


def sync(name=None, type=None):
    users.replace_one({'_id': Vars.DB_NAME}, uts)



def premuim_sync():
    acollection.replace_one({'_id': Vars.DB_NAME}, pts)


def get_episode_number(text):
    """Extract episode/chapter number from text"""
    patterns = [
        r"Chapter\s+(\d+(?:\.\d+)?)",
        r"Volume\s+(\d+) Chapter\s+(\d+(?:\.\d+)?)", 
        r"Chapter\s+(\d+)\s+-\s+(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)"
    ]

    text = str(text)
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.lastindex == 1 else match.group(2)
    return None

def ensure_user(user_id):
    user_id = str(user_id)
    if user_id not in uts:
        uts[user_id] = {"subs": {}, "setting": {}}
        sync()
    
    if "subs" not in uts[user_id]:
        uts[user_id]["subs"] = {}
        sync()
    
    if "setting" not in uts[user_id]:
        uts[user_id]["setting"] = {}
        sync()
    

        
async def add_premium(user_id, time_limit_days):
    user_id = str(user_id)
    expiration_timestamp = int(time.time()) + time_limit_days * 24 * 60 * 60
    premium_data = { "expiration_timestamp": expiration_timestamp }
    pts[user_id] = premium_data
    premuim_sync()


async def remove_premium(user_id):
    user_id = str(user_id)
    if user_id in pts:
        del pts[user_id]
        premuim_sync()


async def remove_expired_users():
    current_timestamp = int(time.time())
    expired_users = [user for user, data in pts.items() if data.get("expiration_timestamp", 0) < current_timestamp]
    for expired_user in expired_users:
        try:
            user_id = int(expired_user)
            await remove_premium(user_id)
        except:
            pass


async def get_all_premuim():
    for user_id, data in pts.items():
        yield pts[user_id]


async def premium_user(user_id):
    user_id = str(user_id)
    return pts[user_id] if user_id in pts else None


def get_users(user_id=None):
    users_id_list = []
    for i in users.find():
        for j in i:
            try:
                if user_id and int(j) == int(user_id):
                    try:
                        if str(user_id) in uts:
                            return uts[str(user_id)]
                        else:
                            return None
                    except:
                        pass
                else:
                    users_id_list.append(int(j))
            except:
                continue

    return users_id_list


async def add_sub(user_id, rdata, web: str, chapter=None):
    user_id = str(user_id)
    ensure_user(user_id)
    
    if web not in uts[user_id]["subs"]:
        uts[user_id]["subs"][web] = []
        sync()
    
    data = rdata.load_to_dict()
    if data not in uts[user_id]["subs"][web]:
        uts[user_id]["subs"][web].append(data)
        sync()



def get_subs(user_id, manga_url=None, web=None):
    user_id = str(user_id)
    subsList = []
    ensure_user(user_id)

    user_info = get_users(user_id)
    if user_info:
        if web and web in user_info["subs"]:
            if manga_url:
                return True if any(data['url'] == manga_url for data in user_info["subs"][web]) else None

            else:
                subsList.extend(user_info['subs'][web])
        else:
            for j in user_info["subs"].values():
                if manga_url:
                    return True if any(url['url'] == manga_url for url in j) else None
                else:
                    subsList.extend(j)

    return subsList


async def delete_sub(user_id, manga_url=None, web=None):
    """
    This function Use to Delete Subscried Manga From User..
    params:
     user_id : required 
     manga_url : optional => If manga_url is not given then it will delete all subscried manga from user, if web given then it will delete all subscried manga from user in that web
     web : optional => If web is not given then it will delete all subscried manga from user
    extra:
       if the len of subscried manga is 0 then it will delete it from database
    """
    user_id = str(user_id)
    user_info = get_users(user_id)

    if "subs" not in user_info:
        return

    if user_info:
        if web and web in user_info['subs']:
            web_subs = user_info['subs'][web]

            if not manga_url:
                del uts[user_id]['subs'][web]
                sync()

            for data in user_info['subs'][web]:
                if manga_url and data.get('url') == manga_url:
                    if len(uts[user_id]['subs'][web]) == 0:
                        del uts[user_id]['subs'][web]
                        sync()
                    else:
                        uts[user_id]['subs'][web].remove(data)
                        sync()

        else:
            for website, web_subs in user_info['subs'].items():
                for data in web_subs:
                    if data.get('url') == manga_url:
                        if len(uts[user_id]['subs'][website]) == 0:
                            del uts[user_id]['subs'][website]
                            sync()
                        else:
                            uts[user_id]['subs'][website].remove(data)
                            sync()


async def get_all_subs():
    """
    Yields each URL entry in format:
    return website_sf, url, data
    """
    users_list = [
        user_id
        for user_id, data in pts.items()
    ]
    users_list += [
        user_id
        for user_id, data in uts.items()
        if user_id not in users_list
    ]
    for user_id in users_list:
        if (user_id in uts) and (data := uts[user_id]):
            if "subs" in data:
                for website_sf, subs in data['subs'].items():
                    if website_sf in remove_site_sf:
                        await delete_sub(user_id, web=website_sf)
                    else:
                        for sub in subs:
                            yield user_id, website_sf, sub

    


async def save_lastest_chapter(data: dict, user_id: str, web_sf: str):
    """
    Update the latest chapter for subscribed manga
    """
    try:
        main_keys = ["title", "url", "lastest_chapter"]
        user_data = uts.get(user_id, {})
        user_subs = user_data.get('subs', {})
        subscribed_manga = user_subs.get(web_sf, [])

        if not subscribed_manga:
            return
        
        for keys in data.keys():
            if keys not in main_keys:
                del data[keys]
        
        for index, manga_data in enumerate(subscribed_manga):
            if (data.get("url") == manga_data.get('url')) or (manga_data.get("title") == data.get("title")):
                uts[user_id]['subs'][web_sf][index] = data
                sync()
                await asyncio.sleep(3)
                break

    except Exception as err:
        logger.exception(f"Error at Save Lastest Chapter: {err}")
