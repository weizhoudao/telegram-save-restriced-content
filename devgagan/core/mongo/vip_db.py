import datetime
from motor.motor_asyncio import AsyncIOMotorClient as MongoCli
from config import MONGO_DB
from devgagan.core.snowid import SnowflakeGenerator
 
mongo = MongoCli(MONGO_DB)
db = mongo.premium
db = db.vip_db

id_generator = SnowflakeGenerator(machine_id=1)
 
async def add_vip(user_id, expire_date):
    data = await check_vip(user_id)
    if data and data.get("user_id"):
        await db.update_one({"user_id": user_id}, {"$set": {"expire_date": expire_date}})
    else:
        newid = id_generator.generate_id()
        await db.insert_one({"_id": newid, "user_id":user_id, "expire_date": expire_date})
 
async def delete_vip(user_id):
    await db.delete_one({"user_id": user_id})
 
async def check_vip(user_id):
    return await db.find_one({"user_id": user_id})

async def update_user_id(old_id, old_user_id, new_user_id):
    return await db.update_one({"_id":old_id}, {"$set":{"user_id":new_user_id,"transfer_from_user_id":old_user_id}})
 
async def vips():
    id_list = []
    async for data in db.find():
        id_list.append(data["user_id"])
    return id_list
 
async def check_and_remove_expired_users():
    current_time = datetime.datetime.utcnow()
    async for data in db.find():
        expire_date = data.get("expire_date")
        if expire_date and expire_date < current_time:
            await remove_premium(data["user_id"])
            print(f"Removed user {data['user_id']} due to expired plan.")
