import flet as ft
import gdrive
import ios
import convert


def main(page: ft.Page):
    page.title = "LINETransfer"

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
                icon=ft.Icons.ANDROID_OUTLINED,
                selected_icon=ft.Icons.ANDROID,
                label="轉Android",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.APPLE_OUTLINED,
                selected_icon=ft.Icons.APPLE,
                label="轉iOS",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icon(ft.Icons.SETTINGS),
                label="設定",
            ),
        ],
        on_change=lambda e: print("Selected destination:", e.control.selected_index),
    )

    page.add(
        ft.Row(
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
    )


ft.app(main)
