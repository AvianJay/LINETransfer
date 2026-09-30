import os
import sys
import traceback
import shutil
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pymobiledevice3.exceptions import NoDeviceConnectedError, PyMobileDevice3Exception
from pyiosbackup import Backup

LINE_DOMAIN = "AppDomainGroup-group.com.linecorp.line"
PRIVATE_STORE = "Library/Application Support/PrivateStore"
DATABASE_FILES = ("Line.sqlite", "UnifiedGroup.sqlite", "MessageExt.sqlite")

USAGE = """Usage: {0} {{get_database,get_backup_database,backup}} ...
  get_database
  Backup your device and get database

  get_backup_database [DIR] [OUTPUT]
  Get LINE database from backup
    DIR: Backup location
    OUTPUT: Database output dir

  backup <DIR>
  Backup your device
    DIR: Backup directory"""

def backup_get_database(path, output=None):
    backup = Backup.from_path(path)
    pt = backup.get_entry_by_domain_and_path(LINE_DOMAIN, PRIVATE_STORE)
    id = None
    for d in pt.iterdir():
        try:
            backup.get_entry_by_domain_and_path(LINE_DOMAIN, f"{PRIVATE_STORE}/{d.name}/Messages/Line.sqlite")
            id = d.name
        except Exception:
            continue
    if not id:
        return False

    entries = [
        (filename, backup.get_entry_by_domain_and_path(LINE_DOMAIN, f"{PRIVATE_STORE}/{id}/Messages/{filename}"))
        for filename in DATABASE_FILES
    ]

    if not output:
        return id, [(filename, entry.file_id) for filename, entry in entries]

    os.makedirs(output, exist_ok=True)
    for filename, entry in entries:
        out_path = os.path.join(output, filename)
        # 舊的 -wal / -shm 留著的話 SQLite 會把它套用到新的資料庫上
        for suffix in ("-wal", "-shm", "-journal"):
            if os.path.exists(out_path + suffix):
                os.remove(out_path + suffix)
        with open(out_path, "wb") as f:
            f.write(entry.read_raw())
        # Set file modification time
        mtime = entry.last_modified.timestamp()
        os.utime(out_path, (mtime, mtime))

    return output

def backup_device(backup_directory, pg=lambda x: None):
    os.makedirs(backup_directory, exist_ok=True)
    lockdown = create_using_usbmux()
    full = not os.path.exists(os.path.join(backup_directory, lockdown.udid, "Manifest.db"))
    backup_client = Mobilebackup2Service(lockdown)
    backup_client.backup(full=full, backup_directory=backup_directory, progress_callback=pg)
    return os.path.join(backup_directory, lockdown.udid)

def restore_device(db_path, backup_directory, pg=lambda x: None):
    try:
        result = backup_get_database(backup_directory)
    except Exception:
        traceback.print_exc()
        result = None
    if not result:
        return False, "備份中找不到LINE的資料。"
    id, fileids = result
    # 只還原 LINE 部分的做法 (sparserestore)，目前沒有使用
    # back = backup.Backup(
    #     files=[
    #         backup.Directory("", "AppDomainGroup-group.com.linecorp.line"),
    #         backup.Directory("Library", "AppDomainGroup-group.com.linecorp.line"),
    #         backup.Directory("Library/Application Support", "AppDomainGroup-group.com.linecorp.line"),
    #         backup.Directory("Library/Application Support/PrivateStore", "AppDomainGroup-group.com.linecorp.line"),
    #         backup.Directory("Library/Application Support/PrivateStore/" + id, "AppDomainGroup-group.com.linecorp.line"),
    #         backup.ConcreteFile(
    #             "Library/Application Support/PrivateStore/" + id + "/Messages/Line.sqlite",
    #             "AppDomainGroup-group.com.linecorp.line",
    #             contents=open(os.path.join(db_path, "Line.sqlite"), "rb").read(),
    #             owner=501,
    #             group=501,
    #         ),
    #         backup.ConcreteFile(
    #             "Library/Application Support/PrivateStore/" + id + "/Messages/UnifiedGroup.sqlite",
    #             "AppDomainGroup-group.com.linecorp.line",
    #             contents=open(os.path.join(db_path, "UnifiedGroup.sqlite"), "rb").read(),
    #             owner=501,
    #             group=501,
    #         ),
    #         backup.ConcreteFile(
    #             "Library/Application Support/PrivateStore/" + id + "/Messages/MessageExt.sqlite",
    #             "AppDomainGroup-group.com.linecorp.line",
    #             contents=open(os.path.join(db_path, "MessageExt.sqlite"), "rb").read(),
    #             owner=501,
    #             group=501,
    #         ),
    #     ]
    # )
    for file, fileid in fileids:
        op = os.path.join(db_path, file)
        rp = os.path.join(backup_directory, fileid[0:2], fileid)
        try:
            if os.path.isfile(rp):
                os.remove(rp)
            elif os.path.isdir(rp):
                shutil.rmtree(rp)
        except Exception as e:
            print(f"Warning: Failed to remove '{rp}': {e}")
        shutil.copy2(op, rp)
    try:
        # perform_restore(back, progress_callback=pg)
        lockdown = create_using_usbmux()
        with Mobilebackup2Service(lockdown) as mb:
            mb.restore(backup_directory, reboot=True, copy=False, source=".", progress_callback=pg)
        return True, "恢復成功。"
    except PyMobileDevice3Exception as e:
        if "Find My" in str(e):
            return False, "尋找我的裝置已啟用，請先關閉。"
        return False, "未知錯誤：" + str(e)
    except NoDeviceConnectedError:
        return False, "沒有連接的 iOS 裝置。請確保裝置已連接並解鎖。"
    except Exception as e:
        print("ERROR:", str(e))
        traceback.print_exc()
        return False, "未知錯誤：" + str(e)

def check_device():
    try:
        lockdown = create_using_usbmux()
        return lockdown.display_name
    except Exception as e:
        print("No iOS device connected:", e)
        return False

def get_database(out=os.path.join("databases", "iOS")):
    bd = backup_device("iDeviceBackups")
    return backup_get_database(bd, out)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "get_database":
        print("Database saved to", get_database())
    elif len(sys.argv) > 3 and sys.argv[1] == "get_backup_database":
        print("Database saved to", backup_get_database(sys.argv[2], sys.argv[3]))
    elif len(sys.argv) > 1 and sys.argv[1] == "backup":
        backup_device(sys.argv[2] if len(sys.argv) > 2 else ".")
    else:
        print(USAGE.format(sys.argv[0]))
