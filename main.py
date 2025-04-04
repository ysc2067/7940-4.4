import os
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import openai
import firebase_admin
from firebase_admin import credentials, firestore

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从环境变量获取 API Token 和密钥
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Firebase 服务账号 JSON 文件的路径，默认放在项目根目录下
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "firebase-service-account.json")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    logger.error("请设置 TELEGRAM_TOKEN 和 OPENAI_API_KEY 环境变量")
    exit(1)

# 初始化 OpenAI
openai.api_key = OPENAI_API_KEY

# 初始化 Firebase
try:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    logger.error(f"初始化 Firebase 失败: {e}")
    exit(1)


def start(update, context):
    """欢迎信息，介绍基本功能。"""
    user = update.effective_user
    update.message.reply_text(
        f"欢迎 {user.first_name} 使用 ChatGPT Telegram 机器人！\n"
        "你可以直接发送消息，我会调用 ChatGPT API 回答。\n"
        "另外，你可以使用以下额外功能：\n"
        "1. /set_interests 设置你的兴趣（如：/set_interests gaming, music）\n"
        "2. /match 匹配与你兴趣相似的用户\n"
        "3. /recommend 根据你的兴趣推荐活动\n"
        "更多帮助请使用 /help"
    )


def help_command(update, context):
    """显示帮助信息。"""
    update.message.reply_text(
        "帮助信息：\n"
        "/set_interests [兴趣列表] - 设置你的兴趣，使用逗号分隔\n"
        "/match - 匹配与你兴趣相似的用户\n"
        "/recommend - 根据你的兴趣推荐活动\n"
        "直接发送其他消息，我会调用 ChatGPT 回答。"
    )


def set_interests(update, context):
    """
    设置用户兴趣：
    格式：/set_interests interest1, interest2, ...
    将用户兴趣存储到 Firebase Firestore 的 'users' 集合中，文档 id 使用 Telegram 的 user id。
    """
    user = update.effective_user
    text = update.message.text
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        update.message.reply_text("请使用正确的格式：/set_interests interest1, interest2, ...")
        return
    interests_raw = parts[1]
    interests = [i.strip().lower() for i in interests_raw.split(',') if i.strip()]
    user_data = {
        'user_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'interests': interests
    }
    try:
        db.collection('users').document(str(user.id)).set(user_data)
        update.message.reply_text("你的兴趣已设置成功！")
    except Exception as e:
        logger.error(f"保存兴趣失败: {e}")
        update.message.reply_text("设置兴趣时发生错误，请稍后重试。")


def match(update, context):
    """
    匹配与你兴趣相似的其他用户：
    读取当前用户的兴趣，然后遍历 Firebase 中所有用户，
    如果存在交集，则将对方的用户名和共同兴趣展示给你。
    """
    user = update.effective_user
    try:
        user_doc = db.collection('users').document(str(user.id)).get()
        if not user_doc.exists:
            update.message.reply_text("请先使用 /set_interests 设置你的兴趣。")
            return
        user_interests = set(user_doc.to_dict().get('interests', []))
    except Exception as e:
        logger.error(f"获取用户兴趣出错: {e}")
        update.message.reply_text("获取你的兴趣信息时发生错误，请稍后重试。")
        return

    try:
        users_ref = db.collection('users')
        all_users = users_ref.stream()
        matches = []
        for doc in all_users:
            data = doc.to_dict()
            if data['user_id'] == user.id:
                continue  # 跳过自己
            other_interests = set(data.get('interests', []))
            common = user_interests.intersection(other_interests)
            if common:
                display_name = data.get('username') or data.get('first_name') or "未知用户"
                matches.append((display_name, list(common)))
        if matches:
            reply = "匹配到以下与你有相似兴趣的用户：\n"
            for match_user, common_interests in matches:
                reply += f"{match_user}：共同兴趣 - {', '.join(common_interests)}\n"
        else:
            reply = "目前没有匹配到与你兴趣相似的用户。"
        update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"匹配用户出错: {e}")
        update.message.reply_text("匹配用户时发生错误，请稍后重试。")


def recommend(update, context):
    """
    根据用户兴趣推荐活动：
    根据预定义的兴趣与活动映射，返回对应的活动推荐。
    """
    user = update.effective_user
    try:
        user_doc = db.collection('users').document(str(user.id)).get()
        if not user_doc.exists:
            update.message.reply_text("请先使用 /set_interests 设置你的兴趣。")
            return
        user_interests = user_doc.to_dict().get('interests', [])
    except Exception as e:
        logger.error(f"获取用户兴趣出错: {e}")
        update.message.reply_text("获取你的兴趣信息时发生错误，请稍后重试。")
        return

    # 简单的兴趣到活动的映射
    events_map = {
        'gaming': '线上电竞比赛或游戏直播活动',
        'music': '虚拟音乐会或在线音乐分享会',
        'movies': '在线电影首映或观影讨论会',
        'tech': '在线技术分享会或黑客马拉松活动',
        'art': '虚拟艺术展览或创意工作坊'
    }
    recommendations = []
    for interest in user_interests:
        if interest in events_map:
            recommendations.append(f"{interest}：{events_map[interest]}")
    if recommendations:
        reply = "根据你的兴趣，推荐以下活动：\n" + "\n".join(recommendations)
    else:
        reply = "抱歉，目前没有针对你的兴趣的活动推荐。"
    update.message.reply_text(reply)


def chat(update, context):
    """
    非命令消息处理：
    将用户消息作为 prompt 发给 ChatGPT API，并返回生成的回答。
    """
    user_text = update.message.text
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=user_text,
            max_tokens=150,
            temperature=0.7
        )
        answer = response.choices[0].text.strip()
        update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"调用 OpenAI API 出错: {e}")
        update.message.reply_text("调用 ChatGPT API 时出错，请稍后重试。")


def main():
    """初始化 Telegram Bot，并注册各个命令和消息处理函数。"""
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # 注册命令处理器
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("set_interests", set_interests))
    dp.add_handler(CommandHandler("match", match))
    dp.add_handler(CommandHandler("recommend", recommend))

    # 非命令文本消息调用 ChatGPT
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, chat))

    # 启动机器人
    updater.start_polling()
    logger.info("机器人已启动，等待消息中...")
    updater.idle()


if __name__ == '__main__':
    main()
