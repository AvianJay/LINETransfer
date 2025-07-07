import flet as ft
import gdrive
import ios
import convert


def main(page: ft.Page):
    page.title = "LINETransfer"

    convert_column = ft.Column(controls=[
        ft.Text("Convert View")
    ])

    tools_column = ft.Column(controls=[
        ft.Text("Tools View")
    ])

    settings_column = ft.Column(controls=[
        ft.Text("Settings View")
    ])

    def rail_on_change(e):
        vr.controls.pop(-1)
        if e.control.selected_index == 0:
            vr.controls.append(convert_column)
        elif e.control.selected_index == 1:
            vr.controls.append(tools_column)
        elif e.control.selected_index == 2:
            vr.controls.append(settings_column)
        page.update()

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
                    [ft.Text("Body!")],
                    alignment=ft.MainAxisAlignment.START,
                    expand=True,
                ),
            ],
            expand=True,
        )
    page.add(vr)


ft.app(main)
