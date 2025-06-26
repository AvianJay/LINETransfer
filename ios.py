import os
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service
from pyiosbackup import Backup

def backup_get_database(path, filename):
    backup = Backup.from_path(path)
    pt = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", "Library/Application Support/PrivateStore")
    for d in pt.iterdir(): id = d.name
    dbf = backup.get_entry_by_domain_and_path("AppDomainGroup-group.com.linecorp.line", f"Library/Application Support/PrivateStore/{id}/Messages/Line.sqlite")
    open(filename, "wb").write(dbf.read_raw())
    return filename

def backup_device(backup_directory, pg=lambda x: None):
    lockdown = create_using_usbmux()
    full = not os.path.exists(os.path.join(backup_directory, lockdown.udid, "Manifest.db"))
    backup_client = Mobilebackup2Service(lockdown)
    backup_client.backup(full=full, backup_directory=backup_directory, progress_callback=pg)
    return os.path.join(backup_directory, lockdown.udid)

def get_database(out):
    if not os.path.exists("iDeviceBackups"): os.mkdir("iDeviceBackups")
    bd = backup_device("iDeviceBackups")
    backup_get_database(bd, out)
