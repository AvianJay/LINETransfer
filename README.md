# LINETransfer
LINE資料庫轉換器（Android ⇄ iOS）

~~我才不要花600塊~~
## 下載最新成功構建的檔案
[Windows](https://nightly.link/AvianJay/LINETransfer/workflows/build/main/linetransfer-windows.zip)
[macOS](https://nightly.link/AvianJay/LINETransfer/workflows/build/main/linetransfer-macos.zip)
[Linux](https://nightly.link/AvianJay/LINETransfer/workflows/build/main/linetransfer-linux.zip)
# WIP
這個項目目前還在製作當中

然後GUI做很爛請見諒。
# 使用前注意
 - 這是非官方工具，跟 LINE 沒有任何關係，資料遺失請自行負責。
 - 轉換前請先自己備份好聊天紀錄。
 - 還原到 iOS 裝置是用整機備份還原，還原前請先關閉「尋找我的 iPhone」。
 - 登入 Google 後取得的 token 會以明文存在執行目錄的 `.googleauth.json`，請不要把這個檔案分享給別人。
# 需求
 - iOS 裝置：Windows 需要安裝 iTunes 或 Apple 裝置 App（提供驅動程式），Linux 需要 `usbmuxd`
 - Google Drive 備份：需要 Google Chrome（用來登入 Google 帳號）
# 從原始碼執行
```sh
pip install -r requirements.txt
python src/main.py
```
設定檔、下載的資料庫和 iOS 備份都會存在執行時的目錄。

只想轉換資料庫的話可以直接用 `convert.py`：
```sh
python src/convert.py ios2android <iOS資料夾> <輸出的Android資料庫>
python src/convert.py android2ios <Android資料庫> <iOS資料夾>
```
iOS 資料夾需要包含 `Line.sqlite` 和 `MessageExt.sqlite`。
# 目前功能
 - [ ] Android轉iOS (持續完善中)
   - [ ] 可以正常開啟LINE (有時候可以)
   - [x] 辨認誰發的訊息
   - [x] 訊息文字
   - [ ] 媒體內容
   - [ ] 通話紀錄 (會變文字)
 - [ ] iOS轉Android (持續完善中)
   - [x] 可以正常還原轉換後的備份
   - [ ] 辨認誰發的訊息
   - [x] 訊息文字
   - [ ] 媒體內容
   - [ ] 通話紀錄 (尚未測試)
 - [x] 獲取 Google Drive 上的聊天備份
 - [x] 獲取 iOS 裝置上的聊天資料 (目前的方法可能會需要很久的時間)
 - [x] 上傳聊天備份到 Google Drive
 - [x] 在 iOS 裝置上還原聊天資料 (目前的方法可能會需要很久的時間)
 - [ ] CLI (半成品：`convert.py`、`ios.py`、`gdrive.py` 可以單獨執行)
 - [x] GUI (半成品)
