import os
import json
import requests

# info
app_version = "0.0.1"
config_version = 2
update_channel = "dev"
repo = "AvianJay/LINETransfer"

# some global variables
converted = None
platform = os.getenv("FLET_PLATFORM")

# config
default_config = {
    "config_version": config_version,
    "firstrun": True,
    "theme": "system",
    "app_update_check": "popup", # no, notify, popup
    "ios_backup_location":"iDeviceBackups",
    "google_email": "",
}
config_path = "config.json"
_config = None

def _save():
    with open(config_path, "w") as f:
        json.dump(_config, f)

try:
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            _config = json.load(f)
        # Todo: verify
        if not isinstance(_config, dict):
            print("Config file is not a valid JSON object, resetting to default config.")
            _config = default_config.copy()
        for key in _config.keys():
            if key in default_config and not isinstance(_config[key], type(default_config[key])):
                print(f"Config key '{key}' has an invalid type, resetting to default value.")
                _config[key] = default_config[key]
        if "config_version" not in _config:
            print("Config file does not have 'config_version', resetting to default config.")
            _config = default_config.copy()
    else:
        _config = default_config.copy()
        _save()
except ValueError:
    _config = default_config.copy()
    _save()

if _config.get("config_version", 0) < config_version:
    print("Updating config file from version", _config.get("config_version", 0), "to version", config_version)
    for k in default_config.keys():
        if _config.get(k) == None:
            _config[k] = default_config[k]
    _config["config_version"] = config_version
    print("Saving...")
    _save()
    print("Done.")

def config(key, value=None, mode="r"):
    if mode == "r":
        return _config.get(key)
    elif mode == "w":
        _config[key] = value
        _save()
        return True
    else:
        raise ValueError(f"Invalid mode: {mode}")

# check updates
def check_update():
    global app_version
    if update_channel == "nightly":
        workflows_url = f"https://api.github.com/repos/{repo}/actions/workflows"
        res = requests.get(workflows_url, timeout=10).json()
        workflow_url = next((s["url"] for s in res.get("workflows", []) if s["name"] == "Build"), None)
        if not workflow_url:
            return False, "Workflow not found"
        # nightly.link 提供的是 main 上最新一次成功的 build
        workflow_url += "/runs?branch=main&status=success&per_page=1"
        runs = requests.get(workflow_url, timeout=10).json().get("workflow_runs")
        if not runs:
            return False, None
        hash = runs[0].get("head_sha")[0:7].strip().lower()
        app_version = app_version.strip().lower()
        if not hash == app_version:
            return f"### New commit: {hash}\n\n**Full Changelog**: [{app_version}...{hash}](https://github.com/{repo}/compare/{app_version}...{hash})", f"https://nightly.link/{repo}/workflows/build/main/linetransfer-{platform}.zip"
        return False, None
    return False, None
