import flet as ft
import gdrive
import ios
import convert
import config
import os


def main(page: ft.Page):
    page.title = "LINETransfer"

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    if not os.path.exists("databases"): os.mkdir("databases")

    def update_theme(theme=config.config("theme")):
        config.config("theme", ft.ThemeMode(theme).value, "w")
        page.theme_mode = ft.ThemeMode(config.config("theme"))
        page.update()
    update_theme()

    def go_to_home(e=None):
        nonlocal convert_column
        convert_column = default_convert_column()
        home_show_page(0)

    def convert_android_finish():
        convert_column.controls = [
            ft.Text("上傳成功！", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text(f"已經幫你轉換了 {str(config.converted)} 筆資料啦！", text_align=ft.TextAlign.CENTER, size=20),
            ft.Text("請在Android裝置還原聊天備份！", text_align=ft.TextAlign.CENTER, size=20),
            ft.TextButton("回到主頁", on_click=go_to_home),
        ]
        page.update()

    def convert_android_upload(path):
        def start_upload(e):
            convert_column.controls.append(ft.ProgressRing())
            page.update()
            email = convert_column.controls[6].value
            filename = gdrive.download(email, False)
            if filename:
                convert_column.controls = [
                    ft.Text("上傳至Google Drive", text_align=ft.TextAlign.CENTER, size=30),
                    ft.Text("正在上傳轉換後的備份...", text_align=ft.TextAlign.CENTER, size=20),
                    ft.Container(
                        expand=True,
                        content=ft.ProgressRing(scale=5),
                        alignment=ft.alignment.center,
                    ),
                ]
                page.update()
                gdrive.upload_file(email, path, filename)
                convert_android_finish()
            else:
                convert_column.controls.pop(-1)
                convert_column.controls.append(ft.Text("請確保您已經備份了！", text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
                page.update()
        convert_column.controls = [
            ft.Text("上傳至Google Drive", size=30),
            ft.Text("請先在Android裝置登入您的LINE帳號(無須還原)。", size=15),
            ft.Text("然後在Android裝置執行備份的操作。", size=15),
            ft.Text("這樣我們才能獲取備份檔名。", size=15),
            ft.Text("在下一步，您可能需要登入您的Google帳戶。", size=15),
            ft.Text("請確保下面填入的帳號跟備份的帳號是同一個的。", size=15),
            ft.TextField(label="Google Email", value=config.config("google_email"), hint_text="example@gmail.com"),
            ft.TextButton("下一步", on_click=start_upload),
        ]
        page.update()

    def convert_android_ios_backup(e):
        convert_column.controls = [
            ft.Text("備份iOS裝置", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("正在備份...", text_align=ft.TextAlign.CENTER, size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        def on_upd(p):
            if p == 100 or p == 0:
                convert_column.controls[2].content.value = None
            else:
                convert_column.controls[2].content.value = p / 100
            page.update()
        print("Starting iOS backup...")
        bd = ios.backup_device(config.config("ios_backup_location"), on_upd)
        convert_column.controls[2].content.value = None
        convert_column.controls[1].value = "正在取得資料庫..."
        page.update()
        ios.backup_get_database(bd, os.path.join("databases", "iOS"))
        convert_android_ios_converting(os.path.join("databases", "iOS"))

    def convert_android_ios_converting(path):
        if os.path.exists(os.path.join("databases", "gdrive_converted.sqlite")): os.remove(os.path.join("databases", "gdrive_converted.sqlite"))
        convert_column.controls = [
            ft.Text("轉換程序", size=30),
            ft.Text("正在轉換中，請稍後...", size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        try:
            c, m, r = convert.migrate_ios_to_android(path, os.path.join("databases", "gdrive_converted.sqlite"))
            config.converted = c + m + r
            convert_android_upload(os.path.join("databases", "gdrive_converted.sqlite"))
        except:
            convert_column.controls.append(ft.Text("轉換錯誤！請重新開啟程式！", size=20, color=ft.Colors.RED_700))
            page.update()

    def convert_android_selected(e):
        def on_result(e):
            print(e.path)
            # verify
            files = ["Line.sqlite", "UnifiedGroup.sqlite", "MessageExt.sqlite"]
            for f in files:
                if not os.path.exists(os.path.join(e.path, f)):
                    convert_column.controls.append(ft.Text("選擇的資料夾中沒有包含所需的檔案！", color=ft.Colors.RED_700))
                    page.update()
                    return
            convert_column.controls[3].disabled = False
            page.update()
        file_picker.on_result = on_result
        def check_device(e):
            e.control.disabled = True
            page.update()
            if ios.check_device():
                convert_android_ios_backup(e)
            else:
                convert_column.controls.append(ft.Text("沒有連接到iOS裝置！", color=ft.Colors.RED_700))
                e.control.disabled = False
                page.update()
        if e.control.parent.controls[2].value == "ios_backup":
            convert_column.controls = [
                ft.Text("備份iOS裝置", size=30),
                ft.Text("請先將iTunes打開以及插入你的iOS裝置。", size=20),
                ft.TextButton("繼續", on_click=check_device),
            ]
        elif e.control.parent.controls[2].value == "ios_database":
            convert_column.controls = [
                ft.Text("選擇iOS資料庫", size=30),
                ft.Text("請選擇包含Line.sqlite、UnifiedGroup.sqlite、MessageExt.sqlite的資料夾。", size=20),
                ft.ElevatedButton(
                    "選擇資料夾...",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: file_picker.get_directory_path("選擇包含sqlite檔案的資料夾..."),
                ),
                ft.TextButton("繼續", on_click=lambda e:convert_android_ios_converting(file_picker.result.path), disabled=True),
            ]
        page.update()

    def convert_android(e):
        convert_column.controls.clear()
        convert_column.controls = [
            ft.Text("轉換至Android", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請選擇下面一種資料庫的來源。", text_align=ft.TextAlign.CENTER, size=20),
            ft.Dropdown(
                label="資料庫來源",
                options=[
                    ft.DropdownOption(key="ios_backup", content=ft.Text("iOS裝置的備份")),
                    ft.DropdownOption(key="ios_database", content=ft.Text("iOS格式的資料庫")),
                ],
                value="ios_backup",
                alignment=ft.alignment.center,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.TextButton("繼續", on_click=convert_android_selected),
        ]
        page.update()
    
    def convert_ios_finish():
        convert_column.controls = [
            ft.Text("還原成功！", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text(f"已經幫你轉換了 {str(config.converted)} 筆資料啦！", text_align=ft.TextAlign.CENTER, size=20),
            ft.TextButton("回到主頁", on_click=go_to_home),
        ]
        page.update()
    
    def convert_ios_restore(db_path):
        convert_column.controls = [
            ft.Text("還原iOS裝置", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("正在還原iOS裝置...", text_align=ft.TextAlign.CENTER, size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        def on_upd(p):
            if p == 100 or p == 0:
                convert_column.controls[2].content.value = None
            else:
                convert_column.controls[2].content.value = p / 100
            page.update()
        print("Starting iOS restore...")
        status, reason = ios.restore_device(db_path, config.config("ios_backup_location"), on_upd)
        if not status:
            convert_ios_before_restore(db_path, reason)
        convert_column.controls[2].content.value = None
        convert_ios_finish()

    def convert_ios_before_restore(db_path, error=None):
        def check_device(e):
            e.control.disabled = True
            page.update()
            if ios.check_device():
                convert_ios_restore(db_path)
            else:
                convert_column.controls.append(ft.Text("沒有連接到iOS裝置！", color=ft.Colors.RED_700))
                e.control.disabled = False
                page.update()
        convert_column.controls = [
            ft.Text("還原iOS裝置", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請先將iTunes打開以及插入你的iOS裝置。", text_align=ft.TextAlign.CENTER, size=20),
            ft.Text("確保「尋找我的裝置」是關閉的，你可以在還原之後開啟。", text_align=ft.TextAlign.CENTER, size=20),
        ]
        if error:
            convert_column.controls.append(ft.Text(error, text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
        convert_column.controls.append(ft.TextButton("繼續", on_click=check_device))
        page.update()
    
    def convert_ios_converting(fp, db_path):
        if os.path.exists(os.path.join("databases", "gdrive_converted.sqlite")): os.remove(os.path.join("databases", "gdrive_converted.sqlite"))
        convert_column.controls = [
            ft.Text("轉換程序", size=30),
            ft.Text("正在轉換中，請稍後...", size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        try:
            c, m, r = convert.migrate_android_to_ios(fp, db_path)
            config.converted = c + m + r
            convert_ios_before_restore(db_path)
        except:
            convert_column.controls.append(ft.Text("轉換錯誤！請重新開啟程式！", size=20, color=ft.Colors.RED_700))
            page.update()
    
    def convert_ios_backuping(fp):
        convert_column.controls = [
            ft.Text("備份iOS裝置", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("正在備份iOS裝置...", text_align=ft.TextAlign.CENTER, size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        def on_upd(p):
            if p == 100 or p == 0:
                convert_column.controls[2].content.value = None
            else:
                convert_column.controls[2].content.value = p / 100
            page.update()
        print("Starting iOS backup...")
        bd = ios.backup_device(config.config("ios_backup_location"), on_upd)
        convert_column.controls[2].content.value = None
        convert_column.controls[1].value = "正在取得資料庫..."
        page.update()
        ios.backup_get_database(bd, os.path.join("databases", "iOS"))
        convert_ios_converting(fp, os.path.join("databases", "iOS"))

    def convert_ios_get_backup(fp):
        def check_device(e):
            e.control.disabled = True
            page.update()
            if ios.check_device():
                convert_ios_backuping(fp)
            else:
                convert_column.controls.append(ft.Text("沒有連接到iOS裝置！", color=ft.Colors.RED_700))
                e.control.disabled = False
                page.update()
        convert_column.controls = [
            ft.Text("備份iOS裝置", size=30),
            ft.Text("請先在iOS裝置上登入LINE。", size=15),
            ft.Text("將iTunes打開以及插入你的iOS裝置。", size=15),
            ft.TextButton("繼續", on_click=check_device),
        ]

    def convert_ios_gdrive_download(e):
        convert_column.controls = [
            ft.Text("下載Google Drive備份", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("正在下載Google Drive上的備份...", text_align=ft.TextAlign.CENTER, size=20),
            ft.Container(
                expand=True,
                content=ft.ProgressRing(scale=5),
                alignment=ft.alignment.center,
            ),
        ]
        page.update()
        fn = gdrive.download(config.config("google_email"), True)
        fp = os.path.join("databases", "gdrive", fn)
        if not os.path.exists(fp):
            convert_column.controls.append(ft.Text("下載失敗！請確保您已經備份了！", text_align=ft.TextAlign.CENTER, color=ft.Colors.RED_700))
            page.update()
            return
        convert_ios_get_backup(fp)

    def convert_ios_selected(e):
        def on_result(e):
            # verify
            f = e.files[0].name if e.files else None
            print(e.files[0].path if e.files else "No files selected")
            if not os.path.exists(os.path.join(e.path, f)):
                convert_column.controls.append(ft.Text("選擇的檔案不是正確的！", color=ft.Colors.RED_700))
                page.update()
                return
            convert_column.controls[3].disabled = False
            page.update()
        file_picker.on_result = on_result
        def on_email_change(e):
            config.config("google_email", e.control.value, "w")
            if e.control.value:
                convert_column.controls[4].disabled = False
            else:
                convert_column.controls[4].disabled = True
            page.update()
        if e.control.parent.controls[2].value == "gdrive":
            convert_column.controls = [
                ft.Text("請先在Android裝置執行備份的操作。", size=15),
                ft.Text("在下一步，您可能需要登入您的Google帳戶。", size=15),
                ft.Text("請確保下面填入的帳號跟備份的帳號是同一個的。", size=15),
                ft.TextField(label="Google Email", value=config.config("google_email"), hint_text="example@gmail.com", on_change=on_email_change),
                ft.TextButton("下一步", on_click=convert_ios_gdrive_download),
            ]
        elif e.control.parent.controls[2].value == "android_database":
            convert_column.controls = [
                ft.Text("選擇Android資料庫", size=30),
                ft.Text("請選擇資料庫。", size=20),
                ft.ElevatedButton(
                    "選擇資料夾...",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: file_picker.pick_files(dialog_title="選擇sqlite檔案...", file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["sqlite"]),
                ),
                ft.TextButton("繼續", on_click=lambda e:convert_ios_converting(file_picker.result.path), disabled=True),
            ]
        page.update()
    
    def convert_ios(e):
        convert_column.controls.clear()
        convert_column.controls = [
            ft.Text("轉換至iOS", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請選擇下面一種資料庫的來源。", text_align=ft.TextAlign.CENTER, size=20),
            ft.Dropdown(
                label="資料庫來源",
                options=[
                    ft.DropdownOption(key="gdrive", content=ft.Text("Google Drive上的備份")),
                    ft.DropdownOption(key="android_database", content=ft.Text("Android格式的資料庫")),
                ],
                value="gdrive",
                alignment=ft.alignment.center,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.TextButton("繼續", on_click=convert_ios_selected),
        ]
        page.update()


    def default_convert_column():
        return ft.Column(controls=[
            ft.Text("歡迎來到LINETransfer！", text_align=ft.TextAlign.CENTER, size=30),
            ft.Text("請選擇下面一種轉換方式。", text_align=ft.TextAlign.CENTER, size=20),
            ft.Row([
                ft.TextButton(
                    content=ft.Container(
                        content=ft.Column(
                                [
                                    ft.Icon(name=ft.Icons.ANDROID),
                                    # ft.Column(
                                    #     [
                                    ft.Text(value="轉換至Android", size=20),
                                    #     ],
                                    #     alignment=ft.MainAxisAlignment.CENTER,
                                    #     spacing=5,
                                    # ),
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
                                    # ft.Column(
                                    #     [
                                    ft.Text(value="轉換至iOS", size=20),
                                    #     ],
                                    #     alignment=ft.MainAxisAlignment.CENTER,
                                    #     spacing=5,
                                    # ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        padding=10,
                        on_click=convert_ios,
                        alignment=ft.alignment.center,
                    ),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY), shape=ft.RoundedRectangleBorder(radius=15)),
                ),
            ])
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        )

    convert_column = default_convert_column()

    tools_column = ft.Column(controls=[
        ft.Text("Tools Page"),
    ])

    settings_column = ft.Column(controls=[
        ft.Text("Settings Page"),
        ft.Text("主題設定"),
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
        # config.config("ios_backup_location")
        ft.Text("iOS裝置備份位置"),
        ft.TextField(
            label="備份位置",
            value=config.config("ios_backup_location"),
            on_change=lambda e: config.config("ios_backup_location", e.control.value, "w"),
            hint_text="iDeviceBackups",
            helper_text="請確保這個資料夾已經存在。",
        ),
        ft.Text("應用程式更新檢查設定"),
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
    ])

    def home_show_page(index):
        vr.controls.pop(-1)
        if index == 0:
            vr.controls.append(ft.Container(
                content=convert_column,
                expand=True,
                alignment=ft.alignment.center,
            ))
        elif index == 1:
            vr.controls.append(tools_column)
        elif index == 2:
            vr.controls.append(settings_column)
        page.update()

    def rail_on_change(e):
        home_show_page(e.control.selected_index)

    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=400,
        # leading=ft.FloatingActionButton(
        #     icon=ft.Icons.CREATE, text="Add", on_click=lambda e: print("FAB clicked!")
        # ),
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.SYNC_OUTLINED,
                selected_icon=ft.Icons.SYNC,
                label="轉換",
            ),
            # ft.NavigationRailDestination(
            #     icon=ft.Icons.APPLE_OUTLINED,
            #     selected_icon=ft.Icons.APPLE,
            #     label="轉iOS",
            # ),
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
                    alignment=ft.MainAxisAlignment.START,
                    expand=True,
                ),
            ],
            expand=True,
        )
    page.add(vr)
    home_show_page(0)

ft.app(main)
