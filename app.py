import flet as ft
import json
import random
import os
import asyncio
import inspect
import time
from datetime import date, timedelta

async def main(page: ft.Page):
    # --- アプリの基本設定 ---
    page.title = "DOPAMINE FOCUS"
    page.theme_mode = "dark"
    page.padding = 20
    
    # 画面の中央揃えとスクロールを有効化
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE

    def safe_update():
        if hasattr(page, "update"):
            try:
                page.update()
            except Exception:
                pass

    # --- 爆速キャッシュ ---
    app_state = {
        "rewards": [{"name": "チョコを1個食べる", "rarity": "Normal", "weight": 60}],
        "logs": {}
    }

    # --- データ操作系（壊れたデータを自動修復する強化版） ---
    async def load_json(filename, default):
        storage = getattr(page, "shared_preferences", getattr(page, "client_storage", None))
        if storage is None: return default
        try:
            has_key = storage.contains_key(filename)
            if inspect.isawaitable(has_key): has_key = await has_key
            if has_key:
                val = storage.get(filename)
                if inspect.isawaitable(val): val = await val
                if isinstance(val, str):
                    try: return json.loads(val)
                    except: return default # 文字列として壊れていたら初期化して返す
                return val
        except Exception:
            pass
        return default

    async def save_json(filename, data):
        storage = getattr(page, "shared_preferences", getattr(page, "client_storage", None))
        if storage is None: return
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            res = storage.set(filename, json_str)
            if inspect.isawaitable(res): await res
        except Exception:
            pass

    # 保存を裏で行い、画面をフリーズさせない仕組み
    def background_save(filename, data):
        asyncio.create_task(save_json(filename, data))

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

    history_table = ft.DataTable(columns=[ft.DataColumn(ft.Text("日付")), ft.DataColumn(ft.Text("達成回数"), numeric=True)], rows=[])
    reward_list_view = ft.Column()

    def update_ui_sync():
        reward_list_view.controls.clear()
        
        # データが壊れていたら強制リセット
        if not isinstance(app_state["rewards"], list):
            app_state["rewards"] = [{"name": "チョコを1個食べる", "rarity": "Normal", "weight": 60}]
            
        for i, r in enumerate(app_state["rewards"]):
            dot_color = "amber" if r.get('rarity') == "Legend" else "blue" if r.get('rarity') == "Rare" else "white"
            def make_delete_action(index):
                def delete_item(e):
                    if len(app_state["rewards"]) > 1:
                        app_state["rewards"].pop(index)
                        background_save('rewards.json', app_state["rewards"])
                        update_ui_sync()
                    else:
                        result_display.value = "最低1つのご褒美が必要です！"
                        result_display.color = "red400"
                        safe_update()
                        async def reset_msg():
                            await asyncio.sleep(3)
                            result_display.value = "集中を始めよう"
                            result_display.color = "grey400"
                            safe_update()
                        asyncio.create_task(reset_msg())
                return delete_item

            row = ft.Row(
                controls=[
                    ft.Text(f"• {r.get('name', '不明')} [{r.get('rarity', 'Normal')}]", size=14, color=dot_color, expand=True),
                    ft.TextButton("削除", on_click=make_delete_action(i))
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
            )
            reward_list_view.controls.append(row)
        
        # ログデータが壊れていたら強制リセット
        if not isinstance(app_state["logs"], dict):
            app_state["logs"] = {}
            
        today = str(date.today())
        today_count_text.value = f"今日の達成: {app_state['logs'].get(today, 0)} 回"
        
        history_table.rows.clear()
        for i in range(5):
            day = str(date.today() - timedelta(days=i))
            history_table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(day)), ft.DataCell(ft.Text(str(app_state['logs'].get(day, 0))))]))
        safe_update()

    gacha_button = ft.ElevatedButton("ご褒美を受け取る！", icon="CARD_GIFT_CARD", disabled=True, width=250, height=50)
    start_button = ft.ElevatedButton("集中を開始", icon="PLAY_ARROW", width=150)
    cancel_button = ft.ElevatedButton("中断", icon="STOP", width=100, disabled=True, color="red400")

    is_timer_running = [False]

    def finish_logic():
        timer_text.value = "完成！"
        timer_text.color = "green400"
        is_timer_running[0] = False
        
        # 【最重要】ログデータが壊れていたら確実にリセットする安全装置
        if not isinstance(app_state["logs"], dict):
            app_state["logs"] = {}
            
        today = str(date.today())
        app_state["logs"][today] = app_state["logs"].get(today, 0) + 1
        
        gacha_button.disabled = False
        start_button.disabled = False
        cancel_button.disabled = True
        time_selector.disabled = False
        update_ui_sync()
        
        background_save('timer_state.json', {"running": False, "end_time": 0})
        background_save('logs.json', app_state["logs"])

    async def start_timer(e, resume_end_time=None):
        is_timer_running[0] = True
        start_button.disabled = True
        cancel_button.disabled = False
        time_selector.disabled = True
        gacha_button.disabled = True
        timer_text.color = "amber400"
        safe_update() 

        if resume_end_time:
            end_time = resume_end_time
        else:
            minutes = float(time_selector.value)
            seconds = int(minutes * 60)
            end_time = time.time() + seconds
            background_save('timer_state.json', {"running": True, "end_time": end_time})

        while is_timer_running[0]:
            remaining = int(end_time - time.time())
            if remaining <= 0:
                break
            
            mins, secs = divmod(remaining, 60)
            new_display = f"{mins:02d}:{secs:02d}"
            
            if timer_text.value != new_display:
                timer_text.value = new_display
                safe_update()
            
            await asyncio.sleep(0.1)

        if is_timer_running[0] and remaining <= 0:
            finish_logic()

    def cancel_timer(e):
        is_timer_running[0] = False
        timer_text.value = "00:00"
        timer_text.color = "amber400"
        start_button.disabled = False
        cancel_button.disabled = True
        time_selector.disabled = False
        safe_update()
        
        background_save('timer_state.json', {"running": False, "end_time": 0})

    start_button.on_click = start_timer
    cancel_button.on_click = cancel_timer

    def draw_gacha(e):
        # ご褒美データが壊れていたら強制リセット
        if not isinstance(app_state["rewards"], list) or not app_state["rewards"]:
            app_state["rewards"] = [{"name": "チョコを1個食べる", "rarity": "Normal", "weight": 60}]
            
        rewards = app_state["rewards"]
        result = random.choices(population=rewards, weights=[r.get('weight', 60) for r in rewards], k=1)[0]
        rarity_badge.value = f"【{result.get('rarity', 'Normal')}】"
        rarity_badge.color = "amber" if result.get('rarity') == "Legend" else "blue" if result.get('rarity') == "Rare" else "white"
        result_display.value = result.get('name', '不明なご褒美')
        result_display.italic = False
        result_display.size = 24
        result_display.color = "white"
        gacha_button.disabled = True
        safe_update()

    gacha_button.on_click = draw_gacha

    new_reward_input = ft.TextField(label="ご褒美の内容", expand=True)
    rarity_dropdown = ft.Dropdown(width=110, value="Normal", options=[ft.dropdown.Option("Normal"), ft.dropdown.Option("Rare"), ft.dropdown.Option("Legend")])

    def add_reward_click(e):
        if new_reward_input.value:
            new_reward = new_reward_input.value
            new_reward_input.value = ""
            
            if not isinstance(app_state["rewards"], list):
                app_state["rewards"] = []
                
            w = 60 if rarity_dropdown.value == "Normal" else 30 if rarity_dropdown.value == "Rare" else 10
            app_state["rewards"].append({"name": new_reward, "rarity": rarity_dropdown.value, "weight": w})
            
            update_ui_sync()
            background_save('rewards.json', app_state["rewards"])

    add_btn = ft.ElevatedButton("追加", icon="ADD", on_click=add_reward_click)

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

    async def initialize_app():
        # キャッシュの初期化（壊れていたらデフォルト値を使う）
        r = await load_json('rewards.json', None)
        if r is not None and isinstance(r, list): 
            app_state["rewards"] = r
            
        l = await load_json('logs.json', {})
        if isinstance(l, dict):
            app_state["logs"] = l
            
        update_ui_sync()
        
        state = await load_json('timer_state.json', {"running": False, "end_time": 0})
        if state and isinstance(state, dict) and state.get("running"):
            now = time.time()
            if state.get("end_time", 0) > now:
                await start_timer(None, resume_end_time=state["end_time"])
            else:
                finish_logic()

    asyncio.create_task(initialize_app())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port, assets_dir="assets")
