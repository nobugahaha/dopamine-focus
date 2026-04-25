import flet as ft
import json
import random
import os
import asyncio
import inspect
from datetime import date, timedelta

async def main(page: ft.Page):
    # --- アプリの基本設定 ---
    page.title = "DOPAMINE FOCUS"
    page.theme_mode = "dark"
    page.padding = 20
    
    try:
        page.window.width = 500
        page.window.height = 950
    except:
        pass
        
    try:
        page.window_width = 500
        page.window_height = 950
    except:
        pass
        
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE

    # 安全に画面を更新するヘルパー
    def safe_update():
        if hasattr(page, "update"):
            try:
                page.update()
            except Exception:
                pass

    # --- データ操作系（最新Flet対応 ＆ 文字列変換バグ修正版） ---
    async def load_json(filename, default):
        storage = getattr(page, "shared_preferences", getattr(page, "client_storage", None))
        if storage is None:
            return default
            
        has_key = storage.contains_key(filename)
        if inspect.isawaitable(has_key):
            has_key = await has_key
            
        if has_key:
            val = storage.get(filename)
            if inspect.isawaitable(val):
                val = await val
            # 保存されている文字列を、Pythonで使えるデータ（辞書やリスト）に戻す
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    pass
            return val
        return default

    async def save_json(filename, data):
        storage = getattr(page, "shared_preferences", getattr(page, "client_storage", None))
        if storage is None:
            return

        # Pythonのデータ（辞書やリスト）を、一度「ただの文字列」に変換してから保存する
        json_str = json.dumps(data, ensure_ascii=False)
        res = storage.set(filename, json_str)
        if inspect.isawaitable(res):
            await res

    # --- UIパーツ ---
    today_count_text = ft.Text("", size=20, weight="bold", color="green200")
    timer_text = ft.Text("00:00", size=70, weight="w900", color="amber400")
    rarity_badge = ft.Text("", size=20, weight="bold")
    result_display = ft.Text("集中を始めよう", size=18, italic=True, color="grey400")
    
    time_selector = ft.Dropdown(
        value="25",
        width=150,
        options=[
            ft.dropdown.Option("0.16", "10秒 (テスト)"),
            ft.dropdown.Option("15", "15分 (ショート)"),
            ft.dropdown.Option("25", "25分 (標準)"),
            ft.dropdown.Option("50", "50分 (ディープ)"),
        ]
    )

    history_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("日付")), ft.DataColumn(ft.Text("達成回数"), numeric=True)],
        rows=[]
    )
    reward_list_view = ft.Column()

    async def update_ui():
        # 1. 報酬リストの更新
        reward_list_view.controls.clear()
        rewards = await load_json('rewards.json', [{"name": "チョコを1個食べる", "rarity": "Normal", "weight": 60}])
        
        for i, r in enumerate(rewards):
            dot_color = "amber" if r['rarity'] == "Legend" else "blue" if r['rarity'] == "Rare" else "white"
            
            def make_delete_action(index):
                async def delete_item(e):
                    current_rewards = await load_json('rewards.json', [])
                    if len(current_rewards) > 1:
                        current_rewards.pop(index)
                        await save_json('rewards.json', current_rewards)
                        await update_ui()
                    else:
                        result_display.value = "最低1つのご褒美が必要です！"
                        result_display.color = "red400"
                        safe_update()
                        await asyncio.sleep(2)
                        result_display.value = "集中を始めよう"
                        result_display.color = "grey400"
                        safe_update()
                return delete_item

            row = ft.Row(
                controls=[
                    ft.Text(f"• {r['name']} [{r['rarity']}]", size=14, color=dot_color, expand=True),
                    ft.TextButton("削除", on_click=make_delete_action(i))
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
            reward_list_view.controls.append(row)
        
        # 2. ログと履歴表の更新
        logs = await load_json('logs.json', {})
        today = str(date.today())
        today_count_text.value = f"今日の達成: {logs.get(today, 0)} 回"
        
        history_table.rows.clear()
        for i in range(5):
            day = str(date.today() - timedelta(days=i))
            history_table.rows.append(
                ft.DataRow(cells=[ft.DataCell(ft.Text(day)), ft.DataCell(ft.Text(str(logs.get(day, 0))))])
            )
        safe_update()

    # --- ボタン類 ---
    gacha_button = ft.ElevatedButton("ご褒美を受け取る！", icon="CARD_GIFT_CARD", disabled=True, width=250, height=50)
    start_button = ft.ElevatedButton("集中を開始", icon="PLAY_ARROW", width=150)
    cancel_button = ft.ElevatedButton("中断", icon="STOP", width=100, disabled=True, color="red400")

    is_timer_running = [False]

    async def start_timer(e):
        minutes = float(time_selector.value)
        seconds = int(minutes * 60)
        
        is_timer_running[0] = True
        start_button.disabled = True
        cancel_button.disabled = False
        time_selector.disabled = True
        gacha_button.disabled = True
        timer_text.color = "amber400"
        safe_update()

        while seconds > 0 and is_timer_running[0]:
            mins, secs = divmod(seconds, 60)
            timer_text.value = f"{mins:02d}:{secs:02d}"
            safe_update()
            await asyncio.sleep(1)
            seconds -= 1

        if seconds == 0 and is_timer_running[0]:
            timer_text.value = "完成！"
            timer_text.color = "green400"
            logs = await load_json('logs.json', {})
            today = str(date.today())
            logs[today] = logs.get(today, 0) + 1
            await save_json('logs.json', logs)
            gacha_button.disabled = False
            await update_ui()
            
        is_timer_running[0] = False
        start_button.disabled = False
        cancel_button.disabled = True
        time_selector.disabled = False
        safe_update()

    async def cancel_timer(e):
        is_timer_running[0] = False
        timer_text.value = "00:00"
        timer_text.color = "amber400"
        safe_update()

    start_button.on_click = start_timer
    cancel_button.on_click = cancel_timer

    async def draw_gacha(e):
        rewards = await load_json('rewards.json', [])
        if not rewards: return
        result = random.choices(population=rewards, weights=[r['weight'] for r in rewards], k=1)[0]
        rarity_badge.value = f"【{result['rarity']}】"
        rarity_badge.color = "amber" if result['rarity'] == "Legend" else "blue" if result['rarity'] == "Rare" else "white"
        result_display.value = result['name']
        result_display.italic = False
        result_display.size = 24
        result_display.color = "white"
        gacha_button.disabled = True
        safe_update()

    gacha_button.on_click = draw_gacha

    new_reward_input = ft.TextField(label="ご褒美の内容", expand=True)
    rarity_dropdown = ft.Dropdown(width=110, value="Normal", options=[ft.dropdown.Option("Normal"), ft.dropdown.Option("Rare"), ft.dropdown.Option("Legend")])

    async def add_reward_click(e):
        if new_reward_input.value:
            rewards = await load_json('rewards.json', [])
            w = 60 if rarity_dropdown.value == "Normal" else 30 if rarity_dropdown.value == "Rare" else 10
            rewards.append({"name": new_reward_input.value, "rarity": rarity_dropdown.value, "weight": w})
            await save_json('rewards.json', rewards)
            new_reward_input.value = ""
            await update_ui()

    add_btn = ft.ElevatedButton("追加", icon="ADD", on_click=add_reward_click)

    await update_ui()

    # --- レイアウト ---
    page.add(
        ft.Column(
            [
                ft.Text("DOPAMINE FOCUS", size=32, weight="w900", color="blue200"),
                today_count_text,
                
                ft.Container(
                    content=ft.Column([
                        timer_text, 
                        time_selector,
                        ft.Row([start_button, cancel_button], alignment=ft.MainAxisAlignment.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
                    padding=30, bgcolor="white10", border_radius=20
                ),
                
                ft.Divider(height=30, color="transparent"),
                rarity_badge,
                result_display,
                gacha_button,
                ft.Divider(height=30),
                
                ft.Text("達成履歴（直近5日間）", size=18, color="green200", weight="bold"),
                ft.Container(content=history_table, bgcolor="white5", border_radius=10, padding=10),
                ft.Divider(height=30),
                
                ft.Text("ご褒美リスト", size=18, color="blue200", weight="bold"),
                ft.Container(content=reward_list_view, padding=15, bgcolor="white5", border_radius=10, width=450),
                ft.Row([new_reward_input, rarity_dropdown], alignment=ft.MainAxisAlignment.CENTER),
                add_btn
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.ADAPTIVE
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
