import os
import sqlite3

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
        '''CREATE TABLE sqlite_sequence(name,seq);''',  # idk this
        '''INSERT INTO android_metadata (locale) VALUES ("en_US");'''
    ]

    for stmt in schema:
        cursor.execute(stmt)

    conn.commit()
    conn.close()