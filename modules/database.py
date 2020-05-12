import logging
import json
import time
import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from modules import config
from modules.download import download, FileType

FORCE_CARD = '?'
FORCE_SKILL = '!'

client = AsyncIOMotorClient(config.DB_CONNECTION_URL)
db = client.zanebot
db.data.create_index([("name", pymongo.TEXT)])


async def retrieve_md5s():
    result = {}
    for file_type in FileType:
        retrieved = await db.md5.find_one({"name": file_type.name})
        result[file_type.name] = retrieved['md5'] if retrieved and 'md5' in retrieved else None
    return result


async def insert_md5(file_type, md5):
    await db.md5.update_one({"name": file_type.name}, {"$set": {"name": file_type.name, 'md5': md5}}, upsert=True)


async def load_json_file(file_type, file_path):
    with open(file_path, 'r') as data_file:
        data_json = json.load(data_file)

    if file_type is FileType.TCG:
        await db.data.delete_many({"exclusive": {"$exists": False}})
        await db.data.insert_many(data_json['data'])
        await db.data.delete_many({"type": "Skill Card"})

    elif file_type is FileType.DL:
        requests = []
        for dl_card in data_json:
            card_name = dl_card['name']
            requests.append(UpdateOne({"name": card_name, "exclusive": {"$exists": False}}, {"$set": dl_card}))
        await db.data.bulk_write(requests)

    elif file_type is FileType.SKILLS:
        await db.data.delete_many({"exclusive": {"$exists": True}})
        await db.data.insert_many(data_json)


async def check_updates():
    stored_md5 = await retrieve_md5s()
    for file_type in FileType:
        logging.info(f'')
        logging.info(f'Checking {file_type.name} updates...')
        start_time = time.time()
        file_download = download(file_type)
        new_md5 = file_download['md5']
        if new_md5 != stored_md5[file_type.name]:
            logging.info(f'New md5 found for {file_type.name}: {new_md5}')
            await load_json_file(file_type, file_download['path'])
            logging.info(f'Loaded new version of {file_type.name}')
            await insert_md5(file_type, new_md5)
            if file_type == FileType.TCG:
                await insert_md5(FileType.DL, '')
        else:
            logging.info(
                f'File {file_type.name} is still at the newest version')
        elapsed_time = int(time.time() - start_time)
        elapsed_minutes = elapsed_time // 60
        elapsed_seconds = elapsed_time % 60
        logging.info(
            f'Update took {elapsed_minutes} minutes and {elapsed_seconds} seconds')


async def search(query, how_many):
    enforce_token = None
    if query[0] in [FORCE_CARD, FORCE_SKILL]:
        # extract enforce token
        enforce_token = query[0]
        query = query[1:]

    # base text search
    search_filter = {
        "$text": {
            "$search": query
        }
    }

    if enforce_token:
        # enforcing something, wrap the base query into an AND
        search_filter = {
            "$and": [search_filter, {"exclusive": {"$exists": enforce_token == FORCE_SKILL}}]
        }

    projection = {'score': {'$meta': "textScore"}}
    sorting = [('score', {'$meta': 'textScore'})]
    return await db.data.find(search_filter, projection).sort(sorting).to_list(length=how_many)
