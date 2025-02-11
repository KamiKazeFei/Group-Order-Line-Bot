import threading
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, SourceGroup

app = Flask(__name__)

# 你的 LINE OA Token & Secret
LINE_CHANNEL_ACCESS_TOKEN = "pRtxi/TXgMpTjSAqeCWFJ6n7kihkW1Tb7S/4+Pf8+BQ0KiLzuWc2YlASF/y3MxwJ/DyzJ92GtOpdiyLRowOVBUXT17TcAriGWyFTqi0J/ujvGKawWg3TCaoVYGO0pdDLpI0Cq+NQW8Q09hztzJYsaAdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "f98afe553b2a7f0c04db20464c2ebe76"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 存點餐清單
order_queue = {}
# 記錄每個sender的活動時間
last_activity_time = {}
# 設定30分鐘超時清除
TIMEOUT = 1800  # 30 minutes in seconds

description = "輸入 #+1【內容】來跟單\n輸入 #代+1 【名稱】【內容】來幫人代訂\n輸入 #-1 移除自己的點餐紀錄\n輸入 #代-1 【名稱】幫他人移除點餐紀錄 \n輸入 #結單 輸出統計點餐紀錄\n輸入 #取消 取消團購\n輸入 #檢視 來查看目前團購紀錄"

# 用來儲存點餐名稱的變數
title_obj = {"title": None}

# 設定計時器來檢查是否超時


def clear_timeout(sender_id):
    """清除超過30分鐘未操作的sender_id的點餐紀錄"""
    if sender_id in order_queue:
        del order_queue[sender_id]
        del last_activity_time[sender_id]
        print(f"已清除 {sender_id} 的點餐紀錄，因為超過30分鐘未操作。")

# 每次有新訊息，重設該sender的計時器


def reset_timer(sender_id):
    """重設計時器，並設置過期時間"""
    if sender_id in last_activity_time:
        last_activity_time[sender_id].cancel()

    timer = threading.Timer(TIMEOUT, clear_timeout, [sender_id])
    timer.start()
    last_activity_time[sender_id] = timer


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    sender_id = event.source.group_id if isinstance(event.source, SourceGroup) else event.source.user_id
    profile = line_bot_api.get_profile(event.source.user_id)
    display_name = profile.display_name

    # 每次有訊息，重設計時器
    reset_timer(sender_id)

    # 取得說明
    if text.startswith("#說明"):
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=f'{description}'))
        return
    # 開團
    if text.startswith("#開團"):
        title_obj["title"] = text.replace('#開團', '').strip() or '團購'
        order_queue[sender_id] = {}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f'{display_name} 開啟了團購：{title_obj["title"]}\n{description}'))
        return

    # 查看目前的點餐紀錄
    if text == "#檢視":
        if title_obj["title"]:
            order_list = "\n".join(
                [f"{name}：{meal}" for name, meal in order_queue[sender_id].items()])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"【{title_obj['title']}】\n目前點餐紀錄：\n{order_list if len(order_list) > 0 else '無'}"))
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))
        return

    # 跟單
    if text.startswith("#+1") or text.startswith("#代+1"):
        if title_obj["title"] is None:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))
        else:
            if text.startswith("#+1"):
                meal = text.replace('#+1', '').strip()
                if meal:
                    order_queue.setdefault(sender_id, {})[display_name] = meal
                else:
                    line_bot_api.reply_message(
                        event.reply_token, TextSendMessage(text="請輸入正確的點餐內容"))
            elif text.startswith("#代+1"):
                meal = text.replace('#代+1', '').strip().split(' ')[0]
                user = text.replace('#代+1', '').strip().split(' ')[1]
                if meal and user:
                    order_queue.setdefault(sender_id, {})[meal] = user
                else:
                    line_bot_api.reply_message(
                        event.reply_token, TextSendMessage(text="請輸入正確的點餐內容"))

            # 回傳目前的點餐紀錄
            order_list = "\n".join(
                [f"{name}：{meal}" for name, meal in order_queue[sender_id].items()])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"【{title_obj['title']}】\n目前點餐紀錄：\n{order_list if len(order_list) > 0 else '無'}"))
    # 處理取消點餐
    elif text.startswith("#-1"):
        if title_obj["title"] is None:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))
        else:
            if sender_id in order_queue and display_name in order_queue[sender_id]:
                del order_queue[sender_id][display_name]
                order_list = "\n".join(
                    [f"{name}：{meal}" for name, meal in order_queue[sender_id].items()])
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text=f"{display_name} 已取消點餐"))
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text=f"【{title_obj['title']}】\n目前點餐紀錄：\n{order_list if len(order_list) > 0 else '無'}"))
            else:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="您未點餐"))

    # 取消代訂點餐
    elif text.startswith("#代-1"):
        if title_obj["title"] is None:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))
        else:
            # 處理取消代訂點餐
            user = text.replace('#代-1', '').strip().split(' ')[0]
            if sender_id in order_queue and user in order_queue[sender_id]:
                del order_queue[sender_id][user]
                order_list = "\n".join(
                    [f"{name}：{meal}" for name, meal in order_queue[sender_id].items()])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text=f"已取消 {user} 的代訂\n【{title_obj['title']}】\n目前點餐紀錄：\n{order_list if len(order_list) > 0 else '無'}"))
            else:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="無此代訂紀錄"))

    elif text == "#結單":
        if title_obj["title"]:            
            if sender_id in order_queue and order_queue[sender_id]:
                order_list = "\n".join(
                    [f"{name}：{meal}" for name, meal in order_queue[sender_id].items()])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text=f"【{title_obj['title']}】 結單：\n{order_list if len(order_list) > 0 else '無'}"))
                title_obj["title"] = None
                del order_queue[sender_id]
            else:
                line_bot_api.reply_message(
                    event.reply_token, TextSendMessage(text="不存在點餐紀錄"))
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))

    elif text == "#取消":
        if title_obj["title"]:
            del order_queue[sender_id]
            title_obj["title"] = None
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="已取消團購"))
        else:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="尚未創建團購"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
