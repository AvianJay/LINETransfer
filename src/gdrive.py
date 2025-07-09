#!/usr/bin/env python
import os
import sys
import time
import json
import requests
import httplib2
import datetime

import googleapiclient
from apiclient import discovery
from oauth2client import client
from selenium import webdriver
# from selenium.common import NoSuchElementException, ElementNotInteractableException
# from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver import Keys
# from selenium.webdriver.support.ui import Select
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.chrome.options import Options
import gzip
import shutil
import tempfile

opt = webdriver.ChromeOptions()
opt.add_argument("--disable-blink-features=AutomationControlled")
opt.add_argument("--no-sandbox")
opt.add_argument("--disable-infobars")
opt.add_argument("--disable-dev-shm-usage")
opt.add_argument("--disable-notifications")
opt.add_experimental_option("excludeSwitches", ['enable-automation'])
opt.add_argument("--app=https://accounts.google.com/embedded/setup/v2/android")

AUTH_URL = "https://android.clients.google.com/auth"
DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"

DEVICE_ID = "0000000000000000"

GMS_SIG = "38918a453d07199354f8b19af05ec6562ced5788"
GMS_PKG = "com.google.android.gms"
GMS_VERSION = 11055440
GMS_UA = "GoogleAuth/1.4 (bullhead MTC20F); gzip"
LINE_PKG = "jp.naver.line.android"
LINE_SIG = "89396dc419292473972813922867e6973d6f5c50"


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

    r = requests.post(AUTH_URL, headers=headers, data=data)
    r.raise_for_status()

    token = None
    lines = r.text.split("\n")
    for l in lines:
        if l.startswith("Token"):
            token = l.split("=")[1].strip()
            break

    return token


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

    r = requests.post(AUTH_URL, headers=headers, data=data)
    r.raise_for_status()

    token = None
    lines = r.text.split("\n")
    for l in lines:
        if l.startswith("Auth"):
            token = l.split("=")[1].strip()
            break

    return token


def get_gdrive_service(gdrive_token):
    credentials = client.AccessTokenCredentials(gdrive_token, "Mozilla/5.0 compatible")
    credentials.scopes.add(DRIVE_FILE_SCOPE)
    credentials.scopes.add(DRIVE_APPDATA_SCOPE)

    http = credentials.authorize(httplib2.Http())
    service = discovery.build("drive", "v3", http=http)

    return service


def download_file(service, todownload=True):
    result = (
        service.files()
        .list(
            spaces="appDataFolder",
            fields="nextPageToken, files(id, name, modifiedTime)",
            q="not trashed",
            pageSize=1000,
        )
        .execute()
    )

    files = result.get("files", [])
    nextPageToken = result.get("nextPageToken")

    while nextPageToken:
        result = (
            service.files()
            .list(
                spaces="appDataFolder",
                pageSize=1000,
                pageToken=nextPageToken,
                fields="nextPageToken, files(id, name, modifiedTime)",
            )
            .execute()
        )

        files.extend(result.get("files", []))
        nextPageToken = result.get("nextPageToken")

    if not files:
        print("No files found")
        return False

    print(f"Found {len(files)} files, starting download nearest...")

    output_dir = os.path.join("databases", "gdrive")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 只挑最新的檔案下載
    latest_file = max(files, key=lambda x: x["modifiedTime"])
    if todownload:
        print(f"Downloading latest file {latest_file['name']} with id {latest_file['id']}")
        req = service.files().get_media(fileId=latest_file["id"])
        output_path = os.path.join(output_dir, f"{latest_file['name']}")
        # 先下載到暫存檔
        with tempfile.NamedTemporaryFile(delete=False) as tmp_f:
            downloader = googleapiclient.http.MediaIoBaseDownload(tmp_f, req)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
            tmp_path = tmp_f.name

        # 解壓縮gzip到output_path
        with open(tmp_path, "rb") as f_in, open(output_path, "wb") as f_out:
            with gzip.GzipFile(fileobj=f_in) as gz:
                shutil.copyfileobj(gz, f_out)

        os.remove(tmp_path)

        modified_time = datetime.datetime.fromisoformat(latest_file["modifiedTime"]).timestamp()
        os.utime(output_path, (modified_time, modified_time))

    return latest_file['name']

def browser_get_oauth_token(email=None):
    # if os.path.exists(".googleoauth") and not force:
    #     return open(".googleoauth", "r").read()
    driver = webdriver.Chrome(options=opt)
    if email:
        driver.find_element(By.CSS_SELECTOR, "input[type=email]").send_keys(email, Keys.ENTER)
    while not driver.get_cookie("oauth_token"):
        time.sleep(.5)
    time.sleep(2)
    token = driver.get_cookie("oauth_token").get("value")
    print("Got OAuth Token")
    # print(token)
    # open(".googleoauth", "w").write(token)
    driver.quit()
    return token

def download(email, todownload=True):
    auth = None
    if os.path.exists(".googleauth.json"):
        auths = json.load(open(".googleauth.json", "r"))
        if auths.get(email):
            auth = auths.get(email)
    else:
        auths = {}
    if not auth:
        oauthtoken = browser_get_oauth_token(email)
        mastertoken = get_master_token(oauthtoken)
        
        auths[email] = {
            "oauth": oauthtoken,
            "master": mastertoken,
            "gdrive": None,
        }
    try:
        auths[email]["gdrive"] = get_gdrive_access_token(email, auths[email]["master"], LINE_PKG, LINE_SIG)
    except:
        # need relogin
        oauthtoken = browser_get_oauth_token(email)
        mastertoken = get_master_token(oauthtoken)
        
        auths[email] = {
            "oauth": oauthtoken,
            "master": mastertoken,
            "gdrive": None,
        }
        auths[email]["gdrive"] = get_gdrive_access_token(email, auths[email]["master"], LINE_PKG, LINE_SIG)
    json.dump(auths, open(".googleauth.json", "w"))
    service = get_gdrive_service(auths[email]["gdrive"])
    download_file(service, todownload)

def upload_file(email, filepath, filename):
    auth = None
    if os.path.exists(".googleauth.json"):
        auths = json.load(open(".googleauth.json", "r"))
        if auths.get(email):
            auth = auths.get(email)
    else:
        auths = {}
    if not auth:
        oauthtoken = browser_get_oauth_token(email)
        mastertoken = get_master_token(oauthtoken)
        
        auths[email] = {
            "oauth": oauthtoken,
            "master": mastertoken,
            "gdrive": None,
        }
    auths[email]["gdrive"] = get_gdrive_access_token(email, auths[email]["master"], LINE_PKG, LINE_SIG)
    json.dump(auths, open(".googleauth.json", "w"))
    service = get_gdrive_service(auths[email]["gdrive"])
    gz_path = filepath + ".gz"
    with open(filepath, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    file_metadata = {
        "name": filename,
        "parents": ["appDataFolder"],
    }
    media = googleapiclient.http.MediaFileUpload(
        gz_path,
        mimetype="application/gzip",
        resumable=True
    )
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name"
    ).execute()

    os.remove(gz_path)
    print(f"Uploaded {filepath} as {uploaded['name']} (id: {uploaded['id']})")
    return uploaded

if __name__ == "__main__":
    if len(sys.argv) > 2:
        if sys.argv[1] == "download":
            download(sys.argv[2])
        else:
            print("Usage:", sys.argv[0], "{download} ...\n  download [EMAIL]\n  Download LINE backup from Google Drive\n    EMAIL: Your Google Account Email")
    else:
        print("Usage:", sys.argv[0], "{download} ...\n  download [EMAIL]\n  Download LINE backup from Google Drive\n    EMAIL: Your Google Account Email")
