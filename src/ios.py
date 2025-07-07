import os
import sys
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pyiosbackup import Backup

def backup_get_database(path, output):
    if not os.path.exists(output):
        os.mkdir(output)
    backup = Backup.from_path(path)
    pt = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", "Library/Application Support/PrivateStore")
    for d in pt.iterdir():
        id = d.name

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

def backup_device(backup_directory, pg=lambda x: None):
    lockdown = create_using_usbmux()
    full = not os.path.exists(os.path.join(backup_directory, lockdown.udid, "Manifest.db"))
    backup_client = Mobilebackup2Service(lockdown)
    backup_client.backup(full=full, backup_directory=backup_directory, progress_callback=pg)
    return os.path.join(backup_directory, lockdown.udid)

def get_database(out):
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
