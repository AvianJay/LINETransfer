import os
import json
import requests
import flet as ft
import threading

# info
app_version = "0.0.1"
config_version = 1
update_channel = "dev"

# some global variables
current_bus = None

platform = os.getenv("FLET_PLATFORM")

# config
default_config = {
    "config_version": config_version,
    "firstrun": True,
    "theme": "system",
    "app_update_check": "popup", # no, notify, popup
}
config_path = "config.json"
_config = None

try:
    if os.path.exists(config_path):
        _config = json.load(open(config_path, "r"))
        # Todo: verify
        if not isinstance(_config, dict):
            print("Config file is not a valid JSON object, resetting to default config.")
            _config = default_config.copy()
        for key in _config.keys():
            if not isinstance(_config[key], type(default_config[key])):
                print(f"Config key '{key}' has an invalid type, resetting to default value.")
                _config[key] = default_config[key]
        if "config_version" not in _config:
            print("Config file does not have 'config_version', resetting to default config.")
            _config = default_config.copy()
    else:
        _config = default_config.copy()
        json.dump(_config, open(config_path, "w"))
except ValueError:
    _config = default_config.copy()
    json.dump(_config, open(config_path, "w"))

if _config.get("config_version", 0) < config_version:
    print("Updating config file from version", _config.get("config_version", 0), "to version", config_version)
    for k in default_config.keys():
        if _config.get(k) == None:
            _config[k] = default_config[k]
    _config["config_version"] = config_version
    print("Saving...")
    json.dump(_config, open(config_path, "w"))
    print("Done.")

def config(key, value=None, mode="r"):
    if mode == "r":
        return _config.get(key)
    elif mode == "w":
        _config[key] = value
        json.dump(_config, open(config_path, "w"))
        return True
    else:
        raise ValueError(f"Invalid mode: {mode}")

# check updates
def check_update():
    global app_version
    if update_channel == "nightly":
        workflows_url = "https://api.github.com/repos/AvianJay/LINETransfer/actions/workflows"
        res = requests.get(workflows_url).json()
        workflow_url = next((s["url"] for s in res.get("workflows") if s["name"] == "Build"), None)
        if not workflow_url:
            return False, "Workflow not found"
        workflow_url += "/runs?per_page=1"
        res = requests.get(workflow_url).json()
        hash = res.get("workflow_runs")[0].get("head_sha")[0:7].strip().lower()
        app_version = app_version.strip().lower()
        if not hash == app_version:
            if res.get("workflow_runs")[0].get("status") == "completed":
                return f"### New commit: {hash}\n\n**Full Changelog**: [{app_version}...{hash}](https://github.com/AvianJay/LINETransfer/compare/{app_version}...{hash})", f"https://nightly.link/AvianJay/TaiwanBusFlet/workflows/build/main/taiwanbusflet-{platform}.zip"
        return False, None
    return False, None
