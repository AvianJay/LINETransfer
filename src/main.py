import flet as ft
import gdrive
import ios
import convert
import config
import os
import time
import traceback


def main(page: ft.Page):
    page.title = "LINETransfer"

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    os.makedirs("databases", exist_ok=True)
    ios_db_dir = os.path.join("databases", "iOS")
    converted_db_path = os.path.join("databases", "gdrive_converted.sqlite")

    def update_theme(theme=config.config("theme")):
        config.config("theme", ft.ThemeMode(theme).value, "w")
        page.theme_mode = ft.ThemeMode(config.config("theme"))
        page.update()
    update_theme()

    def go_to_home(e=None):
        convert_column.controls = convert_column_home.copy()
        home_show_page(0)

    def show_error(message):
        """在目前畫面顯示錯誤，並提供回到主頁的按鈕"""
        convert_column.controls.append(ft.Text(message, text_align=ft.TextAlign.CENTER, size=20, color=ft.Colors.RED_700))
        convert_column.controls.append(ft.TextButton("回到主頁", on_click=go_to_home))
        page.update()

    def show_progress(title, subtitle, status=None):
        """切換到進度畫面，回傳 (ProgressRing, 副標題, 狀態文字) 方便之後更新"""
        ring = ft.ProgressRing(scale=5)
        subtitle_text = ft.Text(subtitle, text_align=ft.TextAlign.CENTER, size=20)
        status_text = ft.Text(status, text_align=ft.TextAlign.CENTER)
        convert_column.controls = [
            ft.Text(title, text_align=ft.TextAlign.CENTER, size=30),
            subtitle_text,
            ft.Container(
                expand=True,
                content=ring,
                alignment=ft.alignment.center,
            ),
        ]
        if status is not None:
            convert_column.controls.append(status_text)
        page.update()
        return ring, subtitle_text, status_text

    def progress_updater(ring, status_text, start_text, done_text):
        """備份 / 還原用的進度回呼"""
        def on_upd(p):
            if p == 100 or p == 0:
                ring.value = None
                status_text.value = start_text if p == 0 else done_text
            else:
                ring.value = p / 100
                status_text.value = str(p) + "%"
            page.update()
        return on_upd

    def check_device_then(on_connected):
        """按鈕的 on_click：確認有連接 iOS 裝置才繼續"""
        def check_device(e):
            e.control.disabled = True
            page.update()
            if ios.check_device():
                on_connected()
            else:
                convert_column.controls.append(ft.Text("沒有連接到iOS裝置！", color=ft.Colors.RED_700))
                e.control.disabled = False
                page.update()
        return check_device

    def backup_and_extract(subtitle, on_success, on_error):
        """備份 iOS 裝置並取出 LINE 資料庫到 databases/iOS"""
        ring, subtitle_text, status_text = show_progress("備份iOS裝置", subtitle, "正在啟動備份。")
        try:
            print("Starting iOS backup...")
            bd = ios.backup_device(
                config.config("ios_backup_location"),
                progress_updater(ring, status_text, "正在啟動備份。", "備份完成，善後中。"),
            )
            ring.value = None
            subtitle_text.value = "正在取得資料庫..."
            page.update()
            if not ios.backup_get_database(bd, ios_db_dir):
                raise RuntimeError("LINE data not found in backup")
        except Exception as e:
            print("Backup ERROR:", e)
            traceback.print_exc()
            on_error("請解鎖裝置。" if "Device locked" in str(e) else "備份或獲取資料庫時發生錯誤。")
            return
        on_success(bd)

    def convert_android_finish():
        convert_column.controls = [
            ft.Text("上傳成功！", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text(f"已經幫你轉換了 {str(config.converted)} 筆資料啦！", text_align=ft.TextAlign.CENTER, size=20),
            ft.Text("請在Android裝置還原聊天備份！", text_align=ft.TextAlign.CENTER, size=20),
            ft.TextButton("回到主頁", on_click=go_to_home),
        ]
        page.update()

    def convert_android_upload(path):
        email_field = ft.TextField(label="Google Email", value=config.config("google_email"), hint_text="example@gmail.com")

        def start_upload(e):
            email = email_field.value.strip()
            config.config("google_email", email, "w")
            e.control.disabled = True
            ring = ft.ProgressRing()
            convert_column.controls.append(ring)
            page.update()
            try:
                filename = gdrive.download(email, False)
            except Exception:
                traceback.print_exc()
                filename = None
            if not filename:
                convert_column.controls.remove(ring)
                convert_column.controls.append(ft.Text("請確保您已經備份了！", text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
                e.control.disabled = False
                page.update()
                return
            show_progress("上傳至Google Drive", "正在上傳轉換後的備份...")
            try:
                gdrive.upload_file(email, path, filename)
            except Exception:
                traceback.print_exc()
                show_error("上傳失敗！")
                return
            convert_android_finish()
        convert_column.controls = [
            ft.Text("上傳至Google Drive", size=30),
            ft.Text("請先在Android裝置登入您的LINE帳號(無須還原)。", size=15),
            ft.Text("然後在Android裝置執行備份的操作。", size=15),
            ft.Text("這樣我們才能獲取備份檔名。", size=15),
            ft.Text("在下一步，您可能需要登入您的Google帳戶。", size=15),
            ft.Text("請確保下面填入的帳號跟備份的帳號是同一個的。", size=15),
            email_field,
            ft.TextButton("下一步", on_click=start_upload),
        ]
        page.update()

    def convert_android_ios_converting(path):
        if os.path.exists(converted_db_path): os.remove(converted_db_path)
        show_progress("轉換程序", "正在轉換中，請稍後...")
        try:
            c, m, r = convert.migrate_ios_to_android(path, converted_db_path)
        except Exception as e:
            print("ERROR:", str(e))
            traceback.print_exc()
            show_error("轉換錯誤！")
            return
        config.converted = c + m + r
        convert_android_upload(converted_db_path)

    def convert_android_selected(source):
        continue_button = ft.TextButton("繼續", on_click=lambda e: convert_android_ios_converting(e.control.data), disabled=True)

        def on_result(e):
            print(e.path)
            # verify
            if not e.path or not all(os.path.exists(os.path.join(e.path, f)) for f in convert.IOS_DATABASE_FILES):
                convert_column.controls.append(ft.Text("選擇的資料夾中沒有包含所需的檔案！", color=ft.Colors.RED_700))
                continue_button.disabled = True
                page.update()
                return
            continue_button.data = e.path
            continue_button.disabled = False
            page.update()
        file_picker.on_result = on_result
        if source == "ios_backup":
            convert_column.controls = [
                ft.Text("備份iOS裝置", size=30),
                ft.Text("請先將iTunes打開以及插入你的iOS裝置。", size=20),
                ft.TextButton("繼續", on_click=check_device_then(
                    lambda: backup_and_extract("正在備份...", lambda bd: convert_android_ios_converting(ios_db_dir), show_error)
                )),
            ]
        elif source == "ios_database":
            convert_column.controls = [
                ft.Text("選擇iOS資料庫", size=30),
                ft.Text(f"請選擇包含{'、'.join(convert.IOS_DATABASE_FILES)}的資料夾。", size=20),
                ft.ElevatedButton(
                    "選擇資料夾...",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: file_picker.get_directory_path("選擇包含sqlite檔案的資料夾..."),
                ),
                continue_button,
            ]
        page.update()

    def convert_android(e):
        source = ft.Dropdown(
            label="資料庫來源",
            options=[
                ft.DropdownOption(key="ios_backup", content=ft.Text("iOS裝置的備份"), text="iOS裝置的備份"),
                ft.DropdownOption(key="ios_database", content=ft.Text("iOS格式的資料庫"), text="iOS格式的資料庫"),
            ],
            value="ios_backup",
            alignment=ft.alignment.center,
            text_align=ft.TextAlign.CENTER,
        )
        convert_column.controls = [
            ft.Text("轉換至Android", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請選擇下面一種資料庫的來源。", text_align=ft.TextAlign.CENTER, size=20),
            source,
            ft.TextButton("繼續", on_click=lambda e: convert_android_selected(source.value)),
        ]
        page.update()

    def convert_ios_finish():
        convert_column.controls = [
            ft.Text("還原成功！", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text(f"已經幫你轉換了 {str(config.converted)} 筆資料啦！", text_align=ft.TextAlign.CENTER, size=20),
            ft.TextButton("回到主頁", on_click=go_to_home),
        ]
        page.update()

    def convert_ios_restore(db_path, bd):
        ring, _, status_text = show_progress("還原iOS裝置", "正在還原iOS裝置...", "正在啟動還原程序。")
        print("Starting iOS restore...")
        ok, reason = ios.restore_device(db_path, bd, progress_updater(ring, status_text, "正在啟動還原程序。", "還原完成，善後中。"))
        if not ok:
            convert_ios_before_restore(db_path, bd, reason)
            return
        convert_ios_finish()

    def convert_ios_before_restore(db_path, bd, error=None):
        convert_column.controls = [
            ft.Text("還原iOS裝置", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請先將iTunes打開以及插入你的iOS裝置。", text_align=ft.TextAlign.CENTER, size=20),
            ft.Text("確保「尋找我的裝置」是關閉的，你可以在還原之後開啟。", text_align=ft.TextAlign.CENTER, size=20),
        ]
        if error:
            convert_column.controls.append(ft.Text(error, text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
        convert_column.controls.append(ft.TextButton("繼續", on_click=check_device_then(lambda: convert_ios_restore(db_path, bd))))
        page.update()

    def convert_ios_converting(fp, db_path, bd):
        show_progress("轉換程序", "正在轉換中，請稍後...")
        try:
            c, m, r = convert.migrate_android_to_ios(fp, db_path)
        except Exception as e:
            print("ERROR:", str(e))
            traceback.print_exc()
            show_error("轉換錯誤！")
            return
        config.converted = c + m + r
        convert_ios_before_restore(db_path, bd)

    def convert_ios_backuping(fp):
        backup_and_extract(
            "正在備份iOS裝置...",
            lambda bd: convert_ios_converting(fp, ios_db_dir, bd),
            lambda error: convert_ios_get_backup(fp, error),
        )

    def convert_ios_get_backup(fp, error=None):
        convert_column.controls = [
            ft.Text("備份iOS裝置", size=30),
            ft.Text("請先在iOS裝置上登入LINE。", size=15),
            ft.Text("將iTunes打開以及插入你的iOS裝置。", size=15),
            ft.TextButton("繼續", on_click=check_device_then(lambda: convert_ios_backuping(fp))),
        ]
        if error:
            convert_column.controls.append(ft.Text(error, size=15, color=ft.Colors.RED_700))
        page.update()

    def convert_ios_gdrive_download(retries=3):
        show_progress("下載Google Drive備份", "正在下載Google Drive上的備份...")
        try:
            fn = gdrive.download(config.config("google_email"), True)
        except Exception as e:
            traceback.print_exc()
            if "Quota exceeded" in str(e) and retries > 0:
                convert_column.controls.append(ft.Text("被Google限制！10秒後重試。", text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
                page.update()
                time.sleep(10)
                convert_ios_gdrive_download(retries - 1)
                return
            fn = None
        print(fn)
        fp = os.path.join("databases", "gdrive", fn) if fn else None
        if not fp or not os.path.exists(fp):
            show_error("下載失敗！請確保您已經備份了！")
            return
        convert_ios_get_backup(fp)

    def convert_ios_selected(source):
        continue_button = ft.TextButton("繼續", on_click=lambda e: convert_ios_get_backup(e.control.data), disabled=True)

        def on_result(e):
            # verify
            f = e.files[0].path if e.files else None
            print(f or "No files selected")
            if not f or not os.path.exists(f):
                convert_column.controls.append(ft.Text("選擇的檔案不是正確的！", color=ft.Colors.RED_700))
                continue_button.disabled = True
                page.update()
                return
            continue_button.data = f
            continue_button.disabled = False
            page.update()
        file_picker.on_result = on_result

        email_field = ft.TextField(label="Google Email", value=config.config("google_email"), hint_text="example@gmail.com")
        next_button = ft.TextButton("下一步", disabled=not email_field.value)

        def on_email_change(e):
            next_button.disabled = not email_field.value
            page.update()

        def on_next(e):
            config.config("google_email", email_field.value.strip(), "w")
            convert_ios_gdrive_download()
        email_field.on_change = on_email_change
        next_button.on_click = on_next

        if source == "gdrive":
            convert_column.controls = [
                ft.Text("請先在Android裝置執行備份的操作。", size=15),
                ft.Text("在下一步，您可能需要登入您的Google帳戶。", size=15),
                ft.Text("請確保下面填入的帳號跟備份的帳號是同一個的。", size=15),
                email_field,
                next_button,
            ]
        elif source == "android_database":
            convert_column.controls = [
                ft.Text("選擇Android資料庫", size=30),
                ft.Text("請選擇資料庫。", size=20),
                ft.ElevatedButton(
                    "選擇檔案...",
                    icon=ft.Icons.FILE_OPEN,
                    on_click=lambda e: file_picker.pick_files(dialog_title="選擇sqlite檔案...", file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["sqlite"]),
                ),
                continue_button,
            ]
        page.update()

    def convert_ios(e):
        source = ft.Dropdown(
            label="資料庫來源",
            options=[
                ft.DropdownOption(key="gdrive", content=ft.Text("Google Drive上的備份"), text="Google Drive上的備份"),
                ft.DropdownOption(key="android_database", content=ft.Text("Android格式的資料庫"), text="Android格式的資料庫"),
            ],
            value="gdrive",
            alignment=ft.alignment.center,
            text_align=ft.TextAlign.CENTER,
        )
        convert_column.controls = [
            ft.Text("轉換至iOS", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請選擇下面一種資料庫的來源。", text_align=ft.TextAlign.CENTER, size=20),
            source,
            ft.TextButton("繼續", on_click=lambda e: convert_ios_selected(source.value)),
        ]
        page.update()

    convert_column_home = [
        ft.Text("歡迎來到LINETransfer！", text_align=ft.TextAlign.CENTER, size=30),
        ft.Text("請選擇下面一種轉換方式。", text_align=ft.TextAlign.CENTER, size=20),
        ft.Row(
            [
                ft.TextButton(
                    content=ft.Container(
                        content=ft.Column(
                                [
                                    ft.Icon(name=ft.Icons.ANDROID),
                                    ft.Text(value="轉換至Android", size=20),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        padding=10,
                        on_click=convert_android,
                        alignment=ft.alignment.center,
                    ),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY), shape=ft.RoundedRectangleBorder(radius=15)),
                ),
                ft.TextButton(
                    content=ft.Container(
                        content=ft.Column(
                                [
                                    ft.Icon(name=ft.Icons.APPLE),
                                    ft.Text(value="轉換至iOS", size=20),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        padding=10,
                        on_click=convert_ios,
                        alignment=ft.alignment.center,
                    ),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY), shape=ft.RoundedRectangleBorder(radius=15)),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,  # 讓按鈕在水平方向置中
            vertical_alignment=ft.CrossAxisAlignment.CENTER,  # 讓按鈕在垂直方向置中
        ),
    ]

    convert_column = ft.Column(
        controls=[],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    tools_column = ft.Column(
        controls=[
            ft.Container(
                expand=True,
                content=ft.Text(
                        "¯\\_(ツ)_/¯\n空空如也",
                        text_align=ft.TextAlign.CENTER,
                        size=30
                    ),
                alignment=ft.alignment.center,
            )
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    settings_column = ft.Column(
        controls=[
            ft.Text("應用程式設定", size=25),
            ft.Text("主題設定", size=20),
            ft.Dropdown(
                label="主題",
                options=[
                    ft.DropdownOption(
                        key="system",
                        leading_icon=ft.Icons.BRIGHTNESS_AUTO,
                        text="跟隨系統",
                        content=ft.Text("跟隨系統"),
                    ),
                    ft.DropdownOption(
                        key="light",
                        leading_icon=ft.Icons.LIGHT_MODE,
                        text="淺色",
                        content=ft.Text("淺色"),
                    ),
                    ft.DropdownOption(
                        key="dark",
                        leading_icon=ft.Icons.DARK_MODE,
                        text="深色",
                        content=ft.Text("深色"),
                    ),
                ],
                on_change=lambda e: update_theme(e.control.value),
                value=config.config("theme"),
            ),
            ft.Text("iOS裝置備份位置", size=20),
            ft.TextField(
                label="備份位置",
                value=config.config("ios_backup_location"),
                # 離開輸入框才儲存，不用每打一個字就寫一次檔
                on_blur=lambda e: config.config("ios_backup_location", e.control.value, "w"),
                hint_text="iDeviceBackups",
            ),
            ft.Text("應用程式更新檢查設定", size=20),
            ft.Dropdown(
                label="自動更新方式",
                options=[
                    ft.DropdownOption(key="no", text="不提示更新", content=ft.Text("不提示更新")),
                    ft.DropdownOption(key="popup", text="彈出更新提示", content=ft.Text("彈出更新提示")),
                    ft.DropdownOption(key="notify", text="通知更新", content=ft.Text("通知更新")),
                ],
                on_change=lambda e: config.config("app_update_check", e.control.value, "w"),
                value=config.config("app_update_check"),
            ),
            ft.Text(f"App Version: {config.app_version}"),
            ft.Text(f"Update Channel: {config.update_channel}"),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def home_show_page(index):
        vr.controls.pop(-1)
        vr.controls.append(ft.Container(
            content=[convert_column, tools_column, settings_column][index],
            expand=True,
            alignment=ft.alignment.center,
        ))
        page.update()

    def rail_on_change(e):
        home_show_page(e.control.selected_index)

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.SYNC_OUTLINED,
                selected_icon=ft.Icons.SYNC,
                label="轉換",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.HANDYMAN_OUTLINED,
                selected_icon=ft.Icons.HANDYMAN,
                label="工具",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="設定",
            ),
        ],
        on_change=rail_on_change,
    )

    vr = ft.Row(
            [
                rail,
                ft.VerticalDivider(width=1),
                ft.Column(
                    [
                        ft.Text("Hello!")
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    expand=True,
                ),
            ],
            expand=True,
        )
    page.add(vr)
    go_to_home()

    def open_app_update_dialog(updates, data):
        def app_update(e):
            page.open(ft.SnackBar(
                content=ft.Text("正在更新"),
            ))
            page.launch_url(data)
        link = updates.split("](")[1].split(")")[0] if "](http" in updates else None
        upddlg = ft.AlertDialog(
            title=ft.Text("應用程式有新更新"),
            content=ft.Markdown(updates),
            actions=[
                *( [ft.TextButton("網頁", on_click=lambda e: page.launch_url(link))] if link else [] ),
                ft.TextButton("下次再說", on_click=lambda e: page.close(upddlg)),
                ft.TextButton("更新", on_click=app_update),
            ],
        )
        page.open(upddlg)

    def check_app_update():
        try:
            updates, data = config.check_update()
        except Exception as e:
            print("Failed to check app update:", str(e))
            page.open(ft.SnackBar(
                content=ft.Text("檢查程式更新時發生錯誤。"),
                action="確定",
            ))
            return
        if updates:
            if config.config("app_update_check") == "popup":
                open_app_update_dialog(updates, data)
            elif config.config("app_update_check") == "notify":
                page.open(ft.SnackBar(
                    content=ft.Text("應用程式有新版本"),
                    action="查看",
                    on_action=lambda e: open_app_update_dialog(updates, data),
                ))
        elif data:
            page.open(ft.SnackBar(
                content=ft.Text("錯誤: " + data),
                action="確定",
            ))

    # 在背景檢查更新，網路慢時不會卡住啟動
    if config.config("app_update_check") != "no":
        page.run_thread(check_app_update)

ft.app(main)
