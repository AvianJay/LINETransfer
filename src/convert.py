import os
import sqlite3
import time
import argparse

IOS_UNIX_OFFSET = 978307200

def ts_android_to_ios(android_ts_ms):
    return (android_ts_ms / 1000) - IOS_UNIX_OFFSET

import os
import time
import sqlite3

# should i get square data idk

IOS_UNIX_OFFSET = 978307200  # seconds

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


def convert_zchat_to_chat(row, cursor, groups_cursor):
    msg_count = row["ZUNREAD"] or 0
    mt = {0: 1, 1: 1, 2: 3}.get(row["ZTYPE"] or 0, 1)
    zmid = clean(row["ZMID"])
    name_row = None
    if mt == 1:
        name_row = cursor.execute("SELECT ZNAME FROM ZUSER WHERE ZMID = ?", (zmid,)).fetchone()
    elif mt == 2:
        name_row = groups_cursor.execute("SELECT ZNAME FROM ZUNIFIEDGROUP WHERE ZID = ?", (zmid,)).fetchone()

    name = clean(name_row["ZNAME"]) if name_row else None

    return {
        "chat_id": zmid,
        "chat_name": name,
        # "owner_mid": "",
        # "last_from_mid": "",
        "last_message": clean(row["ZLASTMESSAGE"]),
        "last_created_time": str(ts_ios_to_android(int(row["ZLASTUPDATED"]))) if row["ZLASTUPDATED"] else "0",
        "message_count": msg_count,
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

def migrate_zchat_to_chat(ios_conn, group_conn, android_conn):
    ios_cursor = ios_conn.cursor()
    ios_cursor.row_factory = sqlite3.Row
    group_cursor = group_conn.cursor()

    android_cursor = android_conn.cursor()

    ios_cursor.execute("SELECT * FROM ZCHAT")
    count = 0
    # 先建立一個已存在 chat_id 的集合
    android_cursor.execute("SELECT chat_id FROM chat")
    existing_chat_ids = set(row[0] for row in android_cursor.fetchall())

    for row in ios_cursor.fetchall():
        chat_row = convert_zchat_to_chat(row, ios_cursor, group_cursor)
        if not chat_row:
            continue
        # 檢查 chat_id 是否已存在
        if chat_row["chat_id"] in existing_chat_ids:
            continue  # 已存在則跳過
        placeholders = ', '.join('?' for _ in chat_row)
        columns = ', '.join(chat_row.keys())
        sql = f"INSERT INTO chat ({columns}) VALUES ({placeholders})"
        android_cursor.execute(sql, list(chat_row.values()))
        existing_chat_ids.add(chat_row["chat_id"])
        count += 1

    android_conn.commit()
    print(f"✅ ZCHAT ➜ chat 匯入完成，共 {count} 筆")
    return count

def convert_zmessage_to_chathistory(msg_row, chat_lookup, zuser_lookup):
    chat_id = chat_lookup.get(msg_row["ZCHAT"])
    if not chat_id:
        return None

    sender_id = zuser_lookup.get(msg_row["ZSENDER"], None)

    ts = int(msg_row["ZTIMESTAMP"]) if msg_row["ZTIMESTAMP"] else 0

    return {
        "server_id": str(msg_row["ZID"]),
        "type": msg_row["ZMESSAGETYPE"],
        "chat_id": chat_id,
        "from_mid": sender_id,
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
        "attachement_image": 0,
        "attachement_image_height": None,
        "attachement_image_width": None,
        "attachement_image_size": None,
        "attachement_type": 0,
        "attachement_local_uri": None,
        "parameter": "restored\ttrue",
        "chunks": None
    }

def migrate_zmessage_to_chathistory(ios_conn, android_conn):
    ios_cursor = ios_conn.cursor()
    ios_cursor.row_factory = sqlite3.Row

    android_cursor = android_conn.cursor()

    # 擷取 ZMESSAGE
    ios_cursor.execute("SELECT * FROM ZMESSAGE")
    zmessage_rows = ios_cursor.fetchall()

    # 使用新的 cursor 取得 lookup 資料，避免覆蓋主流程的 fetchall()
    lookup_cursor = ios_conn.cursor()
    lookup_cursor.row_factory = sqlite3.Row
    chat_lookup = {row["Z_PK"]: row["ZMID"] for row in lookup_cursor.execute("SELECT Z_PK, ZMID FROM ZCHAT").fetchall()}
    zuser_lookup = {row["Z_PK"]: row["ZMID"] for row in lookup_cursor.execute("SELECT Z_PK, ZMID FROM ZUSER").fetchall()}
    # print(chat_lookup)

    # 建立一個集合來記錄已存在的 (delivered_time, content, from_mid)
    existing_messages = set()
    android_cursor.execute("SELECT delivered_time, content, from_mid FROM chat_history")
    for r in android_cursor.fetchall():
        existing_messages.add((r[0], r[1], r[2]))

    count = 0
    for row in zmessage_rows:
        msg = convert_zmessage_to_chathistory(row, chat_lookup, zuser_lookup)
        if not msg:
            continue

        key = (msg["delivered_time"], msg["content"], msg["from_mid"])
        if key in existing_messages:
            print("Skip existed (same content)")
            continue  # 已存在且內容相同則跳過

        columns = ', '.join(msg.keys())
        placeholders = ', '.join(['?'] * len(msg))
        sql = f"INSERT INTO chat_history ({columns}) VALUES ({placeholders})"
        android_cursor.execute(sql, list(msg.values()))
        existing_messages.add(key)
        count += 1

    android_conn.commit()
    print(f"✅ ZMESSAGE ➜ chat_history 匯入完成，共 {count} 筆")
    return count

REACTION_TYPE_MAP = {
    2: "nice",
    3: "love",
    4: "fun",
    5: "amazing",
    6: "sad",
    7: "omg",
}

def convert_zreaction_to_reaction(row):
    reaction_type = REACTION_TYPE_MAP.get(row["ZREACTIONTYPE"], "unknown")

    if clean(row["ZCUSTOMREACTION"]):
        return

    return {
        "server_message_id": int(row["ZMESSAGEID"]),
        "member_id": clean(row["ZREACTORMID"]),
        "chat_id": clean(row["ZCHATMID"]),
        "reaction_time_millis": int(float(row["ZCREATEDAT"]) * 1000),
        "reaction_type": reaction_type,
        "custom_reaction": clean(row["ZCUSTOMREACTION"])
    }

def migrate_zreaction_to_reactions(message_ext_conn, android_conn):
    cursor = message_ext_conn.cursor()
    cursor.row_factory = sqlite3.Row
    dest = android_conn.cursor()

    cursor.execute("SELECT * FROM ZMESSAGEREACTION")
    rows = cursor.fetchall()

    count = 0
    # 先建立一個已存在的 (server_message_id, member_id) 組合集合
    dest.execute("SELECT server_message_id, member_id FROM reactions")
    existing_pairs = set((row[0], row[1]) for row in dest.fetchall())

    for row in rows:
        data = convert_zreaction_to_reaction(row)
        if data is None:
            continue

        key = (data["server_message_id"], data["member_id"])
        if key in existing_pairs:
            continue  # 已存在則跳過

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO reactions ({columns}) VALUES ({placeholders})"
        dest.execute(sql, list(data.values()))
        existing_pairs.add(key)
        count += 1

    android_conn.commit()
    print(f"✅ 已成功轉換 {count} 筆 reaction 資料")
    return count

def migrate_ios_to_android(ios_folder, android_db_path):
    """
    ios_folder: 包含 Line.sqlite, Group.sqlite, MessageExt.sqlite 的資料夾路徑
    android_db_path: 目標 Android 資料庫檔案路徑
    """
    ios_conn = sqlite3.connect(os.path.join(ios_folder, "Line.sqlite"))
    group_conn = sqlite3.connect(os.path.join(ios_folder, "UnifiedGroup.sqlite"))
    message_ext_conn = sqlite3.connect(os.path.join(ios_folder, "MessageExt.sqlite"))
    if not os.path.exists(android_db_path):
        gdrive_database_init(android_db_path)
        print("✅ 已成功創建 Google Drive 備份範本")
    android_conn = sqlite3.connect(android_db_path)

    # chat
    chatcount = migrate_zchat_to_chat(ios_conn, group_conn, android_conn)
    # message
    messagecount = migrate_zmessage_to_chathistory(sqlite3.connect(os.path.join(ios_folder, "Line.sqlite")), android_conn)
    # reaction
    reaction = migrate_zreaction_to_reactions(message_ext_conn, android_conn)

    # close all
    ios_conn.close()
    group_conn.close()
    message_ext_conn.close()
    android_conn.close()
    return chatcount, messagecount, reaction

def convert_chat_to_zchat(row, z_ent):
    return {
        "Z_ENT": z_ent,
        "ZALERT": 1,
        "ZE2EECONTENTTYPES": 0,
        "ZENABLE": 1,
        "ZLASTRECEIVEDMESSAGEID": int(row["read_up"]) if row["read_up"] else 0,
        "ZLIVE": 0,
        "ZMID": clean(row["chat_id"]),
        "ZLASTMESSAGE": clean(row["last_message"]),
        "ZLASTUPDATED": ts_android_to_ios(int(row["last_created_time"])) if row["last_created_time"] else 0,
        "ZREADUPTOMESSAGEID": int(row["read_up"]) if row["read_up"] else 0,
        "ZREADUPTOMESSAGEIDSYNCED": int(row["read_up"]) if row["read_up"] else 0,
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
    sender_pk = zuser_lookup.get(row["from_mid"])
    if chat_pk is None:
        return None
    sid = row["server_id"]
    try: sid = int(sid)
    except: sid = None
    zt = clean(row["content"])
    zt = "\t" if not zt else zt
    return {
        "ZID": sid,
        "ZCHAT": chat_pk,
        "ZSENDER": sender_pk,
        "ZTEXT": zt,
        "ZTIMESTAMP": int(row["created_time"]),
        # "ZMESSAGETYPE": row["type"],
        "ZCONTENTTYPE": 0,  # 0 = text other todo
        "Z_OPT": 1,  # todo
        "Z_ENT": z_ent,
        "ZREADCOUNT": 0,
        "ZSENDSTATUS": 1,
        "ZLATITUDE": 0.0,
        "ZLONGITUDE": 0.0,
    }

def convert_reactions_to_zreaction(row, z_ent=2):
    TYPE_MAP_REVERSE = {
        "nice": 2,
        "love": 3,
        "fun": 4,
        "amazing": 5,
        "sad": 6,
        "omg": 7,
    }
    return {
        "Z_ENT": z_ent,
        "Z_OPT": 1,
        "ZMESSAGEID": row["server_message_id"],
        "ZREACTORMID": clean(row["member_id"]),
        "ZCHATMID": clean(row["chat_id"]),
        "ZREACTIONTYPE": TYPE_MAP_REVERSE.get(row["reaction_type"], 0),
        "ZCREATEDAT": row["reaction_time_millis"] / 1000.0,
        "ZCUSTOMREACTION": clean(row["custom_reaction"])
    }

def migrate_android_to_ios(android_db_path, ios_folder):
    # 先記錄原始檔案的修改時間
    line_path = os.path.join(ios_folder, "Line.sqlite")
    group_path = os.path.join(ios_folder, "UnifiedGroup.sqlite")
    msgext_path = os.path.join(ios_folder, "MessageExt.sqlite")

    line_mtime = os.path.getmtime(line_path)
    group_mtime = os.path.getmtime(group_path)
    msgext_mtime = os.path.getmtime(msgext_path)

    ios_line = sqlite3.connect(line_path)
    group = sqlite3.connect(group_path)
    message_ext = sqlite3.connect(msgext_path)
    android = sqlite3.connect(android_db_path)

    ios_line.row_factory = sqlite3.Row
    group.row_factory = sqlite3.Row
    android.row_factory = sqlite3.Row

    ios_cursor = ios_line.cursor()
    group_cursor = group.cursor()
    msgext_cursor = message_ext.cursor()
    android_cursor = android.cursor()

    # 建立 ZUSER/ZCHAT lookup
    user_lookup = {row["ZMID"]: row["Z_PK"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZUSER")}
    chat_lookup = {row["ZMID"]: row["Z_PK"] for row in ios_cursor.execute("SELECT Z_PK, ZMID FROM ZCHAT")}

    # chat
    ios_cursor.execute("SELECT * FROM Z_PRIMARYKEY WHERE Z_NAME = 'Chat'")
    z_pk_row = ios_cursor.fetchone()
    z_ent = z_pk_row["Z_ENT"] if z_pk_row else 0
    count = 0
    # 先建立一個已存在 ZMID 的集合
    existing_zmids = set(row["ZMID"] for row in ios_cursor.execute("SELECT ZMID FROM ZCHAT"))
    for row in android_cursor.execute("SELECT * FROM chat"):
        data = convert_chat_to_zchat(row, z_ent)
        if not data or not data["ZMID"]:
            continue
        if data["ZMID"] in existing_zmids:
            continue
        placeholders = ', '.join(['?'] * len(data))
        columns = ', '.join(data.keys())
        sql = f"INSERT INTO ZCHAT ({columns}) VALUES ({placeholders})"
        ios_cursor.execute(sql, list(data.values()))
        # existing_zmids.add(data["ZMID"])
        count += 1
    ios_line.commit()

    # 更新 Z_PRIMARYKEY 的 Z_MAX
    ios_cursor.execute("SELECT MAX(Z_PK) FROM ZCHAT LIMIT 1")
    max_zpk = ios_cursor.fetchone()[0]
    if max_zpk is not None:
        ios_cursor.execute(
            "UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = 'Chat'",
            (max_zpk,)
        )
        ios_line.commit()
    print(f"✅ chat ➜ ZCHAT 匯入完成，共 {count} 筆")
    chatcount = count

    # chat_history
    ios_cursor.execute("SELECT * FROM Z_PRIMARYKEY WHERE Z_NAME = 'Message'")
    z_pk_row = ios_cursor.fetchone()
    z_ent = z_pk_row["Z_ENT"] if z_pk_row else 0
    count = 0
    # 先建立一個已存在 ZMESSAGE 的 (ZTIMESTAMP, ZTEXT, ZSENDER) 索引集合
    ios_cursor.execute("SELECT ZTIMESTAMP, ZTEXT, ZSENDER FROM ZMESSAGE")
    existing_messages = set(
        (row[0], row[1], row[2]) for row in ios_cursor.fetchall()
    )

    for row in android_cursor.execute("SELECT * FROM chat_history"):
        data = convert_chathistory_to_zmessage(row, chat_lookup, user_lookup, z_ent)
        if not data:
            continue
        key = (data["ZTIMESTAMP"], data["ZTEXT"], data["ZSENDER"])
        if key in existing_messages:
            # print("Skip existed (same content)")
            continue
        if data["ZCHAT"] in chat_lookup:
            continue
        placeholders = ', '.join(['?'] * len(data))
        columns = ', '.join(data.keys())
        sql = f"INSERT INTO ZMESSAGE ({columns}) VALUES ({placeholders})"
        ios_cursor.execute(sql, list(data.values()))
        existing_messages.add(key)
        count += 1
    ios_line.commit()
    # 更新 Z_PRIMARYKEY 的 Z_MAX
    ios_cursor.execute("SELECT MAX(Z_PK) FROM ZMESSAGE LIMIT 1")
    max_zpk = ios_cursor.fetchone()[0]
    if max_zpk is not None:
        ios_cursor.execute(
            "UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = 'Message'",
            (max_zpk,)
        )
        ios_line.commit()
    print(f"✅ chat_history ➜ ZMESSAGE 匯入完成，共 {count} 筆")
    messagecount = count

    # reactions
    msgext_cursor.execute("SELECT Z_ENT FROM Z_PRIMARYKEY WHERE Z_NAME = 'MessageReaction'")
    z_pk_row = msgext_cursor.fetchone()
    z_ent = z_pk_row[0] if z_pk_row else 0
    count = 0
    # 先建立一個已存在的 (ZMESSAGEID, ZREACTORMID) 組合集合
    msgext_cursor.execute("SELECT ZMESSAGEID, ZREACTORMID FROM ZMESSAGEREACTION")
    existing_pairs = set((row[0], row[1]) for row in msgext_cursor.fetchall())

    for row in android_cursor.execute("SELECT * FROM reactions"):
        data = convert_reactions_to_zreaction(row, z_ent)
        if not data:
            continue
        key = (data["ZMESSAGEID"], data["ZREACTORMID"])
        if key in existing_pairs:
            continue
        placeholders = ', '.join(['?'] * len(data))
        columns = ', '.join(data.keys())
        sql = f"INSERT INTO ZMESSAGEREACTION ({columns}) VALUES ({placeholders})"
        msgext_cursor.execute(sql, list(data.values()))
        # existing_pairs.add(key)
        count += 1
    message_ext.commit()
    # 更新 Z_PRIMARYKEY 的 Z_MAX
    msgext_cursor.execute("SELECT MAX(Z_PK) FROM ZMESSAGEREACTION LIMIT 1")
    max_zpk = msgext_cursor.fetchone()[0]
    if max_zpk is not None:
        msgext_cursor.execute(
            "UPDATE Z_PRIMARYKEY SET Z_MAX = ? WHERE Z_NAME = 'MessageReaction'",
            (max_zpk,)
        )
        message_ext.commit()
    print(f"✅ reactions ➜ ZMESSAGEREACTION 匯入完成，共 {count} 筆")
    reactionscount = count

    # 關閉資料庫
    ios_line.close()
    group.close()
    message_ext.close()
    android.close()
    # 恢復原始檔案的修改時間
    os.utime(line_path, (line_mtime, line_mtime))
    os.utime(group_path, (group_mtime, group_mtime))
    os.utime(msgext_path, (msgext_mtime, msgext_mtime))
    return chatcount, messagecount, reactionscount

def main():
    parser = argparse.ArgumentParser(description="iOS/Android LINE 資料庫轉換工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # iOS ➜ Android
    parser_ios2android = subparsers.add_parser("ios2android", help="iOS 轉 Android")
    parser_ios2android.add_argument("ios_folder", help="iOS 資料夾 (需含 Line.sqlite, UnifiedGroup.sqlite, MessageExt.sqlite)")
    parser_ios2android.add_argument("android_db", help="輸出 Android 資料庫檔案路徑")

    # Android ➜ iOS
    parser_android2ios = subparsers.add_parser("android2ios", help="Android 轉 iOS")
    parser_android2ios.add_argument("android_db", help="Android 資料庫檔案路徑")
    parser_android2ios.add_argument("ios_folder", help="輸出 iOS 資料夾 (需含 Line.sqlite, UnifiedGroup.sqlite, MessageExt.sqlite)")

    args = parser.parse_args()

    if args.command == "ios2android":
        migrate_ios_to_android(args.ios_folder, args.android_db)
    elif args.command == "android2ios":
        migrate_android_to_ios(args.android_db, args.ios_folder)

if __name__ == "__main__":
    main()