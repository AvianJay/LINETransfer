import os
import sys
import traceback
import shutil
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pymobiledevice3.exceptions import NoDeviceConnectedError, PyMobileDevice3Exception
from pyiosbackup import Backup
from sparserestore import backup, perform_restore

def backup_get_database(path, output=None):
    if output:
        if not os.path.exists(output):
            os.mkdir(output)
    backup = Backup.from_path(path)
    pt = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", "Library/Application Support/PrivateStore")
    for d in pt.iterdir():
        try:
            entry = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", f"Library/Application Support/PrivateStore/{d.name}/Messages/Line.sqlite")
            id = d.name
        except:
            continue
    if not id:
        return False

    if output:
        files = [
            ("Line.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/Line.sqlite"),
            ("UnifiedGroup.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/UnifiedGroup.sqlite"),
            ("MessageExt.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/MessageExt.sqlite"),
        ]

        for filename, entry_path in files:
            entry = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", entry_path)
            out_path = os.path.join(output, filename)
            with open(out_path, "wb") as f:
                f.write(entry.read_raw())
            # Set file modification time
            mtime = entry.last_modified
            atime = mtime.timestamp()
            os.utime(out_path, (atime, atime))

        return output
    else:
        files = [
            ("Line.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/Line.sqlite"),
            ("UnifiedGroup.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/UnifiedGroup.sqlite"),
            ("MessageExt.sqlite", f"Library/Application Support/PrivateStore/{id}/Messages/MessageExt.sqlite"),
        ]
        fileids = []

        for filename, entry_path in files:
            entry = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", entry_path)
            fileids.append((filename, entry.file_id))
        return id, fileids

def backup_device(backup_directory, pg=lambda x: None):
    lockdown = create_using_usbmux()
    full = not os.path.exists(os.path.join(backup_directory, lockdown.udid, "Manifest.db"))
    backup_client = Mobilebackup2Service(lockdown)
    backup_client.backup(full=full, backup_directory=backup_directory, progress_callback=pg)
    return os.path.join(backup_directory, lockdown.udid)

def restore_device(db_path, backup_directory, pg=lambda x: None):
    id, fileids = backup_get_database(backup_directory)
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
        # elif "crash_on_purpose" not in str(e):
        #     return False, f"恢復失敗: {e}"
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
    if not os.path.exists("iDeviceBackups"): os.mkdir("iDeviceBackups")
    bd = backup_device("iDeviceBackups")
    return backup_get_database(bd, out)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "get_database":
            print("Database saved to", get_database())
        if sys.argv[1] == "get_backup_database":
            if len(sys.argv) > 3:
                print("Database saved to", backup_get_database(sys.argv[2], sys.argv[3]))
            else:
                print("Usage:", sys.argv[0], "{get_database,get_backup_database,backup} ...\n  get_database\n  Backup your device and get database\n\n  get_backup_database [DIR] [OUTPUT]\n  Get LINE database from backup\n    DIR: Backup location\n    OUTPUT: Database output dir\n\n  backup <DIR>\n  Backup your device\n    DIR: Backup directory")
        elif sys.argv[1] == "backup":
            if len(sys.argv) > 2:
                backup_device(sys.argv[2])
            else:
                backup_device(".")
        else:
            print("Usage:", sys.argv[0], "{get_database,get_backup_database,backup} ...\n  get_database\n  Backup your device and get database\n\n  get_backup_database [DIR] [OUTPUT]\n  Get LINE database from backup\n    DIR: Backup location\n    OUTPUT: Database output dir\n\n  backup <DIR>\n  Backup your device\n    DIR: Backup directory")
    else:
        print("Usage:", sys.argv[0], "{get_database,get_backup_database,backup} ...\n  get_database\n  Backup your device and get database\n\n  get_backup_database [DIR] [OUTPUT]\n  Get LINE database from backup\n    DIR: Backup location\n    OUTPUT: Database output dir\n\n  backup <DIR>\n  Backup your device\n    DIR: Backup directory")
