#!/usr/bin/env python
import os
import sys
import time
import json
import requests
import httplib2
import datetime
import gzip
import shutil
import tempfile

from googleapiclient import discovery
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from oauth2client import client
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

opt = webdriver.ChromeOptions()
opt.add_argument("--disable-blink-features=AutomationControlled")
opt.add_argument("--no-sandbox")
opt.add_argument("--disable-infobars")
opt.add_argument("--disable-dev-shm-usage")
opt.add_argument("--disable-notifications")
opt.add_experimental_option("excludeSwitches", ['enable-automation'])
opt.add_argument("--app=https://accounts.google.com/embedded/setup/v2/android")

AUTH_FILE = ".googleauth.json"
AUTH_URL = "https://android.clients.google.com/auth"
DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
REQUEST_TIMEOUT = 30  # seconds

DEVICE_ID = "0000000000000000"

GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"
GMS_PKG = "com.google.android.gms"
GMS_VERSION = 11055440
GMS_UA = "GoogleAuth/1.4 (bullhead MTC20F); gzip"
LINE_PKG = "jp.naver.line.android"
LINE_SIG = "89396dc419292473972813922867e6973d6f5c50"


def parse_auth_response(text, key):
    for l in text.split("\n"):
        if l.startswith(key + "="):
            return l.split("=", 1)[1].strip()
    return None


def get_master_token(oauth_token):
    data = {
        "app": GMS_PKG,
        "client_sig": GMS_SIG,
        "google_play_services_version": GMS_VERSION,
        "androidId": DEVICE_ID,
        "lang": "en_US",
        "ACCESS_TOKEN": "1",
        "Token": oauth_token,
        "service": "ac2dm",
    }

    headers = {
        "Content-type": "application/x-www-form-urlencoded",
        "User-Agent": GMS_UA,
        "device": DEVICE_ID,
        "Connection": "close",
    }

    r = requests.post(AUTH_URL, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return parse_auth_response(r.text, "Token")


def get_gdrive_access_token(account, master_token, app_id, app_sig):
    requestedService = "oauth2: https://www.googleapis.com/auth/drive.appdata"

    data = {
        "androidId": DEVICE_ID,
        "lang": "en_US",
        "google_play_services_version": GMS_VERSION,
        "sdk_version": 23,
        "device_country": "us",
        "is_called_from_account_manager": 1,
        "client_sig": app_sig,
        "callerSig": GMS_SIG,
        "Email": account,
        "has_permission": 1,
        "service": requestedService,
        "app": app_id,
        "check_email": 1,
        "token_request_options": "CAA4AQ==",
        "system_partition": 1,
        "_opt_is_called_from_account_manager": 1,
        "callerPkg": GMS_PKG,
        "Token": master_token,
    }

    headers = {"Content-type": "application/x-www-form-urlencoded", "Connection": "close"}

    r = requests.post(AUTH_URL, headers=headers, data=data, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return parse_auth_response(r.text, "Auth")


def get_gdrive_service(gdrive_token):
    credentials = client.AccessTokenCredentials(gdrive_token, "Mozilla/5.0 compatible")
    credentials.scopes.add(DRIVE_FILE_SCOPE)
    credentials.scopes.add(DRIVE_APPDATA_SCOPE)

    http = credentials.authorize(httplib2.Http(timeout=REQUEST_TIMEOUT))
    service = discovery.build("drive", "v3", http=http)

    return service


def list_backup_files(service):
    files = []
    page_token = None
    while True:
        result = (
            service.files()
            .list(
                spaces="appDataFolder",
                fields="nextPageToken, files(id, name, modifiedTime)",
                q="not trashed",
                pageSize=1000,
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(result.get("files", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return files


def download_file(service, todownload=True):
    files = list_backup_files(service)
    if not files:
        print("No files found")
        return False

    print(f"Found {len(files)} file(s)")

    # 只挑最新的檔案下載
    latest_file = max(files, key=lambda x: x["modifiedTime"])
    if todownload:
        print(f"Downloading latest file {latest_file['name']} with id {latest_file['id']}")
        output_dir = os.path.join("databases", "gdrive")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, latest_file["name"])
        req = service.files().get_media(fileId=latest_file["id"])
        # 先下載到暫存檔，再解壓縮 gzip 到 output_path
        with tempfile.TemporaryFile() as tmp_f:
            downloader = MediaIoBaseDownload(tmp_f, req)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
            tmp_f.seek(0)
            with gzip.GzipFile(fileobj=tmp_f) as gz, open(output_path, "wb") as f_out:
                shutil.copyfileobj(gz, f_out)

        modified_time = datetime.datetime.fromisoformat(latest_file["modifiedTime"]).timestamp()
        os.utime(output_path, (modified_time, modified_time))

    return latest_file['name']

def browser_get_oauth_token(email=None):
    driver = webdriver.Chrome(options=opt)
    try:
        if email:
            try:
                WebDriverWait(driver, timeout=30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type=email]"))
                ).send_keys(email, Keys.ENTER)
            except TimeoutException:
                pass  # 讓使用者自己輸入
        while not driver.get_cookie("oauth_token"):
            time.sleep(.5)
        time.sleep(2)
        token = driver.get_cookie("oauth_token").get("value")
    finally:
        driver.quit()
    print("Got OAuth Token")
    return token

def load_auths():
    if not os.path.exists(AUTH_FILE):
        return {}
    with open(AUTH_FILE, "r") as f:
        return json.load(f)

def save_auths(auths):
    with open(AUTH_FILE, "w") as f:
        json.dump(auths, f)

def login(email):
    oauthtoken = browser_get_oauth_token(email)
    mastertoken = get_master_token(oauthtoken)
    if not mastertoken:
        raise RuntimeError("Failed to get master token")
    return {
        "oauth": oauthtoken,
        "master": mastertoken,
        "gdrive": None,
    }

def refresh_gdrive_token(email, auth):
    auth["gdrive"] = get_gdrive_access_token(email, auth["master"], LINE_PKG, LINE_SIG)
    if not auth["gdrive"]:
        raise RuntimeError("Failed to get Google Drive access token")

def get_service(email):
    """取得 LINE 在 Google Drive appDataFolder 的存取權，token 失效時重新登入"""
    auths = load_auths()
    auth = auths.get(email)
    just_logged_in = not auth
    if just_logged_in:
        auth = login(email)
    try:
        refresh_gdrive_token(email, auth)
    except Exception:
        if just_logged_in:
            raise
        # need relogin
        auth = login(email)
        refresh_gdrive_token(email, auth)
    auths[email] = auth
    save_auths(auths)
    return get_gdrive_service(auth["gdrive"])

def download(email, todownload=True):
    return download_file(get_service(email), todownload)

def upload_file(email, filepath, filename):
    service = get_service(email)
    file_metadata = {
        "name": filename,
        "parents": ["appDataFolder"],
    }
    # 壓縮到暫存檔再上傳，結束後自動刪除
    with tempfile.TemporaryFile() as gz_f:
        with open(filepath, "rb") as f_in, gzip.GzipFile(fileobj=gz_f, mode="wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        gz_f.seek(0)
        media = MediaIoBaseUpload(gz_f, mimetype="application/gzip", resumable=True)
        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name"
        ).execute()

    print(f"Uploaded {filepath} to {filename} as {uploaded['name']} (id: {uploaded['id']})")
    return uploaded

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "download":
        download(sys.argv[2])
    else:
        print("Usage:", sys.argv[0], "{download} ...\n  download [EMAIL]\n  Download LINE backup from Google Drive\n    EMAIL: Your Google Account Email")
