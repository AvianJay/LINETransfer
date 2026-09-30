import os
import sqlite3
import time
import argparse
from contextlib import closing

IOS_UNIX_OFFSET = 978307200  # seconds

# 轉換需要的 iOS 資料庫檔案
IOS_DATABASE_FILES = ("Line.sqlite", "MessageExt.sqlite")

# iOS ZCONTENTTYPE ➜ Android (type, attachement_type)
# 由同一帳號的 iOS / Android 備份用 server_id 對照得出，沒列到的類型當成文字
IOS_TO_ANDROID_CONTENT_TYPE = {
    0: (1, 0),    # 文字
    1: (1, 1),    # 圖片
    2: (1, 2),    # 影片
    5: (1, 22),
    7: (5, 7),    # 貼圖
    13: (1, 13),
    17: (1, 17),
    18: (13, 18),
    96: (1, 1),
    112: (1, 1),
}
# Android attachement_type ➜ iOS ZCONTENTTYPE，沒列到的類型當成文字
ANDROID_TO_IOS_CONTENT_TYPE = {0: 0, 1: 1, 2: 2, 7: 7, 13: 13, 17: 17, 18: 18, 22: 5}
ATTACH_TYPE_IMAGE = 1

REACTION_TYPE_MAP = {
    2: "nice",
    3: "love",
    4: "fun",
    5: "amazing",
    6: "sad",
    7: "omg",
}
REACTION_TYPE_MAP_REVERSE = {v: k for k, v in REACTION_TYPE_MAP.items()}


def ts_android_to_ios(android_ts_ms):
    """
    Convert Android LINE timestamp (milliseconds) to iOS LINE timestamp (seconds since 2001-01-01)
    """
    return (android_ts_ms / 1000) - IOS_UNIX_OFFSET

def ts_ios_to_android(ios_ts):
    """
    Convert iOS LINE timestamp (seconds since 2001-01-01) to Android LINE timestamp (milliseconds since 1970-01-01)
    """
    return int((ios_ts + IOS_UNIX_OFFSET) * 1000)


def clean(val):
    if val is None:
        return None
    val = str(val).strip()
    return val if val else None

def message_key(server_id, timestamp, text, sender):
    """判斷重複訊息用的 key：優先用 server id，沒有才用 (時間, 內容, 發送者)"""
    if server_id:
        return str(server_id)
    return (int(timestamp or 0), clean(text), sender)

def insert_rows(cursor, table, rows):
    """一次插入多筆欄位相同的 dict"""
    if not rows:
        return
    columns = ', '.join(rows[0].keys())
    placeholders = ', '.join(['?'] * len(rows[0]))
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    cursor.executemany(sql, [list(r.values()) for r in rows])

def get_z_ent(cursor, name):
    row = cursor.execute("SELECT Z_ENT FROM Z_PRIMARYKEY WHERE Z_NAME = ?", (name,)).fetchone()
    return row[0] if row else 0

def update_z_max(cursor, table, name):
    """插入資料後更新 Z_PRIMARYKEY 的 Z_MAX"""
    max_zpk = cursor.execute(f"SELECT MAX(Z_PK) FROM {table}").fetchone()[0]
    if max_zpk is not None:
        cursor.execute("UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = ?", (max_zpk, name))

def gdrive_database_init(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)  # 確保是全新建立

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    schema = [
        '''CREATE TABLE android_metadata (locale TEXT);''',
        '''CREATE TABLE chat (
            chat_id TEXT PRIMARY KEY,
            chat_name TEXT,
            owner_mid TEXT,
            last_from_mid TEXT,
            last_message TEXT,
            last_created_time TEXT,
            message_count INTEGER,
            read_message_count INTEGER,
            latest_mentioned_position INTEGER,
            type INTEGER,
            is_notification INTEGER,
            skin_key TEXT,
            input_text TEXT,
            input_text_metadata TEXT,
            hide_member INTEGER,
            p_timer INTEGER,
            last_message_display_time TEXT,
            mid_p TEXT,
            is_archived INTEGER,
            read_up TEXT,
            is_groupcalling INTEGER,
            latest_announcement_seq INTEGER,
            announcement_view_status INTEGER,
            last_message_meta_data TEXT,
            chat_room_bgm_data TEXT,
            chat_room_bgm_checked INTEGER,
            chat_room_should_show_bgm_badge INTEGER,
            unread_type_and_count TEXT
        );''',
        '''CREATE TABLE chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_id TEXT,
            type INTEGER,
            chat_id TEXT,
            from_mid TEXT,
            content TEXT,
            created_time TEXT,
            delivered_time TEXT,
            status INTEGER,
            sent_count INTEGER,
            read_count INTEGER,
            location_name TEXT,
            location_address TEXT,
            location_phone TEXT,
            location_latitude INTEGER,
            location_longitude INTEGER,
            attachement_image INTEGER,
            attachement_image_height INTEGER,
            attachement_image_width INTEGER,
            attachement_image_size INTEGER,
            attachement_type INTEGER,
            attachement_local_uri TEXT,
            parameter TEXT,
            chunks BLOB
        );''',
        '''CREATE TABLE reactions (
            server_message_id    INTEGER NOT NULL,
            member_id            TEXT    NOT NULL,
            chat_id              TEXT    NOT NULL,
            reaction_time_millis INTEGER NOT NULL,
            reaction_type        TEXT    NOT NULL,
            custom_reaction      TEXT,
            PRIMARY KEY (server_message_id, member_id)
        );''',
        '''INSERT INTO android_metadata (locale) VALUES ("en_US");'''
    ]

    for stmt in schema:
        cursor.execute(stmt)

    conn.commit()
    conn.close()


def convert_zchat_to_chat(row, user_names):
    mt = {0: 1, 1: 1, 2: 3}.get(row["ZTYPE"] or 0, 1)
    zmid = clean(row["ZMID"])

    return {
        "chat_id": zmid,
        # 群組名稱 Android 會自己同步，只填個人聊天的名稱
        "chat_name": clean(user_names.get(zmid)) if mt == 1 else None,
        # "owner_mid": "",
        # "last_from_mid": "",
        "last_message": clean(row["ZLASTMESSAGE"]),
        "last_created_time": str(ts_ios_to_android(int(row["ZLASTUPDATED"]))) if row["ZLASTUPDATED"] else "0",
        "message_count": row["ZUNREAD"] or 0,
        "read_message_count": 0,
        "latest_mentioned_position": 0,
        "type": mt,
        "is_notification": 1,
        # "skin_key": clean(row["ZSKIN"]),
        "input_text": clean(row["ZINPUTTEXT"]),
        "input_text_metadata": "",
        "last_message_display_time": str(int(time.time() * 1000)),
        "is_archived": 0,
        "read_up": str(row["ZREADUPTOMESSAGEID"] or ""),
        "last_message_meta_data": "{}",
        "chat_room_bgm_data": "",
        "chat_room_should_show_bgm_badge": 0,
    }

def migrate_zchat_to_chat(ios_conn, android_conn):
    ios_cursor = ios_conn.cursor()
    android_cursor = android_conn.cursor()

    user_names = {row["ZMID"]: row["ZNAME"] for row in ios_cursor.execute("SELECT ZMID, ZNAME FROM ZUSER")}
    # 先建立一個已存在 chat_id 的集合
    existing_chat_ids = {row[0] for row in android_cursor.execute("SELECT chat_id FROM chat")}

    chats_to_insert = []
    for row in ios_cursor.execute("SELECT * FROM ZCHAT"):
        chat_row = convert_zchat_to_chat(row, user_names)
        # 檢查 chat_id 是否已存在
        if not chat_row["chat_id"] or chat_row["chat_id"] in existing_chat_ids:
            continue
        chats_to_insert.append(chat_row)
        existing_chat_ids.add(chat_row["chat_id"])

    insert_rows(android_cursor, "chat", chats_to_insert)
    print(f"✅ ZCHAT ➜ chat 匯入完成，共 {len(chats_to_insert)} 筆")
    return len(chats_to_insert)

def convert_zmessage_to_chathistory(msg_row, chat_lookup, zuser_lookup):
    chat_id = chat_lookup.get(msg_row["ZCHAT"])
    if not chat_id:
        return None

    ts = int(msg_row["ZTIMESTAMP"]) if msg_row["ZTIMESTAMP"] else 0
    msg_type, attach_type = IOS_TO_ANDROID_CONTENT_TYPE.get(msg_row["ZCONTENTTYPE"] or 0, (1, 0))

    return {
        "server_id": clean(msg_row["ZID"]),
        "type": msg_type,
        "chat_id": chat_id,
        "from_mid": zuser_lookup.get(msg_row["ZSENDER"]),
        "content": clean(msg_row["ZTEXT"]),
        "created_time": str(ts),
        "delivered_time": str(ts),
        "status": 3,
        "sent_count": 1,
        "read_count": 1,
        "location_name": None,
        "location_address": None,
        "location_phone": None,
        "location_latitude": None,
        "location_longitude": None,
        "attachement_image": 1 if attach_type == ATTACH_TYPE_IMAGE else 0,
        "attachement_image_height": None,
        "attachement_image_width": None,
        "attachement_image_size": None,
        "attachement_type": attach_type,
        "attachement_local_uri": None,
        "parameter": "restored\ttrue",
        "chunks": None
    }

def migrate_zmessage_to_chathistory(ios_conn, android_conn):
    ios_cursor = ios_conn.cursor()
    android_cursor = android_conn.cursor()

    chat_lookup = {row["Z_PK"]: row["ZMID"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZCHAT")}
    zuser_lookup = {row["Z_PK"]: row["ZMID"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZUSER")}

    existing_messages = {
        message_key(*row)
        for row in android_cursor.execute("SELECT server_id, created_time, content, from_mid FROM chat_history")
    }

    messages_to_insert = []
    for row in ios_cursor.execute("SELECT * FROM ZMESSAGE"):
        msg = convert_zmessage_to_chathistory(row, chat_lookup, zuser_lookup)
        if not msg:
            continue
        key = message_key(msg["server_id"], msg["created_time"], msg["content"], msg["from_mid"])
        if key in existing_messages:
            continue
        messages_to_insert.append(msg)
        existing_messages.add(key)

    insert_rows(android_cursor, "chat_history", messages_to_insert)
    print(f"✅ ZMESSAGE ➜ chat_history 匯入完成，共 {len(messages_to_insert)} 筆")
    return len(messages_to_insert)

def convert_zreaction_to_reaction(row):
    if clean(row["ZCUSTOMREACTION"]):
        return None

    return {
        "server_message_id": int(row["ZMESSAGEID"]),
        "member_id": clean(row["ZREACTORMID"]),
        "chat_id": clean(row["ZCHATMID"]),
        "reaction_time_millis": ts_ios_to_android(float(row["ZCREATEDAT"])),
        "reaction_type": REACTION_TYPE_MAP.get(row["ZREACTIONTYPE"], "unknown"),
        "custom_reaction": None,
    }

def migrate_zreaction_to_reactions(message_ext_conn, android_conn):
    cursor = message_ext_conn.cursor()
    dest = android_conn.cursor()

    # 先建立一個已存在的 (server_message_id, member_id) 組合集合
    existing_pairs = {(row[0], row[1]) for row in dest.execute("SELECT server_message_id, member_id FROM reactions")}

    reactions_to_insert = []
    for row in cursor.execute("SELECT * FROM ZMESSAGEREACTION"):
        data = convert_zreaction_to_reaction(row)
        if data is None:
            continue
        key = (data["server_message_id"], data["member_id"])
        if key in existing_pairs:
            continue  # 已存在則跳過
        reactions_to_insert.append(data)
        existing_pairs.add(key)

    insert_rows(dest, "reactions", reactions_to_insert)
    print(f"✅ 已成功轉換 {len(reactions_to_insert)} 筆 reaction 資料")
    return len(reactions_to_insert)

def migrate_ios_to_android(ios_folder, android_db_path):
    """
    ios_folder: 包含 Line.sqlite, MessageExt.sqlite 的資料夾路徑
    android_db_path: 目標 Android 資料庫檔案路徑
    """
    if not os.path.exists(android_db_path):
        gdrive_database_init(android_db_path)
        print("✅ 已成功創建 Google Drive 備份範本")

    with closing(sqlite3.connect(os.path.join(ios_folder, "Line.sqlite"))) as ios_conn, \
         closing(sqlite3.connect(os.path.join(ios_folder, "MessageExt.sqlite"))) as message_ext_conn, \
         closing(sqlite3.connect(android_db_path)) as android_conn:
        ios_conn.row_factory = sqlite3.Row
        message_ext_conn.row_factory = sqlite3.Row

        chatcount = migrate_zchat_to_chat(ios_conn, android_conn)
        messagecount = migrate_zmessage_to_chathistory(ios_conn, android_conn)
        reactioncount = migrate_zreaction_to_reactions(message_ext_conn, android_conn)
        # 全部成功才寫入
        android_conn.commit()
    return chatcount, messagecount, reactioncount

def convert_chat_to_zchat(row, z_ent):
    read_up = int(row["read_up"]) if row["read_up"] else 0
    return {
        "Z_ENT": z_ent,
        "ZALERT": 1,
        "ZE2EECONTENTTYPES": 0,
        "ZENABLE": 1,
        "ZLASTRECEIVEDMESSAGEID": read_up,
        "ZLIVE": 0,
        "ZMID": clean(row["chat_id"]),
        "ZLASTMESSAGE": clean(row["last_message"]),
        "ZLASTUPDATED": ts_android_to_ios(int(row["last_created_time"])) if row["last_created_time"] else 0,
        "ZREADUPTOMESSAGEID": read_up,
        "ZREADUPTOMESSAGEIDSYNCED": read_up,
        "ZSESSIONID": 0,
        "ZSORTORDER": 0,
        "ZMETADATA": 0,  # todo
        "ZEXPIREINTERVAL": 0.0,
        "ZUNREAD": row["message_count"] or 0,
        "ZINPUTTEXT": clean(row["input_text"]),
        "ZTYPE": {1: 0, 3: 2}.get(row["type"], 1),
        "ZSKIN": clean(row["skin_key"])
    }

def convert_chathistory_to_zmessage(row, chat_lookup, zuser_lookup, z_ent=5):
    chat_pk = chat_lookup.get(row["chat_id"])
    if chat_pk is None:
        return None

    return {
        "ZID": clean(row["server_id"]),
        "ZCHAT": chat_pk,
        "ZSENDER": zuser_lookup.get(row["from_mid"]),
        "ZTEXT": clean(row["content"]) or "\t",
        "ZTIMESTAMP": int(row["created_time"]),
        # ZMESSAGETYPE 在樣本中都是 NULL，不設定
        "ZCONTENTTYPE": ANDROID_TO_IOS_CONTENT_TYPE.get(row["attachement_type"] or 0, 0),
        "Z_OPT": 1,  # todo
        "Z_ENT": z_ent,
        "ZREADCOUNT": 0,
        "ZSENDSTATUS": 1,
        "ZLATITUDE": 0.0,
        "ZLONGITUDE": 0.0,
    }

def convert_reactions_to_zreaction(row, z_ent=2):
    return {
        "Z_ENT": z_ent,
        "Z_OPT": 1,
        "ZMESSAGEID": str(row["server_message_id"]),
        "ZREACTORMID": clean(row["member_id"]),
        "ZCHATMID": clean(row["chat_id"]),
        "ZREACTIONTYPE": REACTION_TYPE_MAP_REVERSE.get(row["reaction_type"], 0),
        "ZCREATEDAT": ts_android_to_ios(row["reaction_time_millis"]),
        "ZCUSTOMREACTION": clean(row["custom_reaction"])
    }

def migrate_chat_to_zchat(android_conn, ios_conn):
    ios_cursor = ios_conn.cursor()
    z_ent = get_z_ent(ios_cursor, "Chat")
    # 先建立一個已存在 ZMID 的集合
    existing_zmids = {row["ZMID"] for row in ios_cursor.execute("SELECT ZMID FROM ZCHAT")}

    chats_to_insert = []
    for row in android_conn.execute("SELECT * FROM chat"):
        data = convert_chat_to_zchat(row, z_ent)
        if not data["ZMID"] or data["ZMID"] in existing_zmids:
            continue
        chats_to_insert.append(data)

    insert_rows(ios_cursor, "ZCHAT", chats_to_insert)
    update_z_max(ios_cursor, "ZCHAT", "Chat")
    print(f"✅ chat ➜ ZCHAT 匯入完成，共 {len(chats_to_insert)} 筆")
    return len(chats_to_insert)

def migrate_chathistory_to_zmessage(android_conn, ios_conn):
    ios_cursor = ios_conn.cursor()
    z_ent = get_z_ent(ios_cursor, "Message")

    # 要在 ZCHAT 匯入之後才建立，不然新聊天室的訊息會被略過
    user_lookup = {row["ZMID"]: row["Z_PK"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZUSER")}
    chat_lookup = {row["ZMID"]: row["Z_PK"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZCHAT")}

    existing_messages = {
        message_key(*row)
        for row in ios_cursor.execute("SELECT ZID, ZTIMESTAMP, ZTEXT, ZSENDER FROM ZMESSAGE")
    }

    messages_to_insert = []
    for row in android_conn.execute("SELECT * FROM chat_history"):
        data = convert_chathistory_to_zmessage(row, chat_lookup, user_lookup, z_ent)
        if not data:
            continue
        key = message_key(data["ZID"], data["ZTIMESTAMP"], data["ZTEXT"], data["ZSENDER"])
        if key in existing_messages:
            continue
        messages_to_insert.append(data)
        existing_messages.add(key)

    insert_rows(ios_cursor, "ZMESSAGE", messages_to_insert)
    update_z_max(ios_cursor, "ZMESSAGE", "Message")
    print(f"✅ chat_history ➜ ZMESSAGE 匯入完成，共 {len(messages_to_insert)} 筆")
    return len(messages_to_insert)

def migrate_reactions_to_zreaction(android_conn, message_ext_conn):
    msgext_cursor = message_ext_conn.cursor()
    z_ent = get_z_ent(msgext_cursor, "MessageReaction")
    # 先建立一個已存在的 (ZMESSAGEID, ZREACTORMID) 組合集合
    existing_pairs = {(row[0], row[1]) for row in msgext_cursor.execute("SELECT ZMESSAGEID, ZREACTORMID FROM ZMESSAGEREACTION")}

    reactions_to_insert = []
    for row in android_conn.execute("SELECT * FROM reactions"):
        data = convert_reactions_to_zreaction(row, z_ent)
        key = (data["ZMESSAGEID"], data["ZREACTORMID"])
        if key in existing_pairs:
            continue
        reactions_to_insert.append(data)
        existing_pairs.add(key)

    insert_rows(msgext_cursor, "ZMESSAGEREACTION", reactions_to_insert)
    update_z_max(msgext_cursor, "ZMESSAGEREACTION", "MessageReaction")
    print(f"✅ reactions ➜ ZMESSAGEREACTION 匯入完成，共 {len(reactions_to_insert)} 筆")
    return len(reactions_to_insert)

def migrate_android_to_ios(android_db_path, ios_folder):
    line_path = os.path.join(ios_folder, "Line.sqlite")
    msgext_path = os.path.join(ios_folder, "MessageExt.sqlite")
    # 先記錄原始檔案的修改時間
    mtimes = {p: os.path.getmtime(p) for p in (line_path, msgext_path)}

    try:
        with closing(sqlite3.connect(line_path)) as ios_line, \
             closing(sqlite3.connect(msgext_path)) as message_ext, \
             closing(sqlite3.connect(android_db_path)) as android:
            ios_line.row_factory = sqlite3.Row
            message_ext.row_factory = sqlite3.Row
            android.row_factory = sqlite3.Row

            chatcount = migrate_chat_to_zchat(android, ios_line)
            messagecount = migrate_chathistory_to_zmessage(android, ios_line)
            reactionscount = migrate_reactions_to_zreaction(android, message_ext)
            # 全部成功才寫入，避免資料庫只改到一半
            ios_line.commit()
            message_ext.commit()
    finally:
        # 恢復原始檔案的修改時間
        for path, mtime in mtimes.items():
            os.utime(path, (mtime, mtime))
    return chatcount, messagecount, reactionscount

def main():
    parser = argparse.ArgumentParser(description="iOS/Android LINE 資料庫轉換工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # iOS ➜ Android
    parser_ios2android = subparsers.add_parser("ios2android", help="iOS 轉 Android")
    parser_ios2android.add_argument("ios_folder", help="iOS 資料夾 (需含 Line.sqlite, MessageExt.sqlite)")
    parser_ios2android.add_argument("android_db", help="輸出 Android 資料庫檔案路徑")

    # Android ➜ iOS
    parser_android2ios = subparsers.add_parser("android2ios", help="Android 轉 iOS")
    parser_android2ios.add_argument("android_db", help="Android 資料庫檔案路徑")
    parser_android2ios.add_argument("ios_folder", help="輸出 iOS 資料夾 (需含 Line.sqlite, MessageExt.sqlite)")

    args = parser.parse_args()

    if args.command == "ios2android":
        migrate_ios_to_android(args.ios_folder, args.android_db)
    elif args.command == "android2ios":
        migrate_android_to_ios(args.android_db, args.ios_folder)

if __name__ == "__main__":
    main()
