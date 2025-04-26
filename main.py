import os
import logging
from urllib.parse import quote

import discord
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv, set_key, dotenv_values

# ─ 환경 변수 설정 ───────────────────────────────────────────────────────
# MABINOGI_API_KEY     : 넥슨 개발자센터에서 발급받은 Mabinogi API 키
# MABINOGI_ITEMS       : 모니터링할 아이템 이름 (쉼표로 구분)
# DISCORD_BOT_TOKEN    : Discord 봇의 토큰
# DISCORD_CHANNEL_ID   : Discord 채널 ID
#
# 예) 리눅스/맥 환경에서 export
# export MABINOGI_API_KEY="your_mabi_api_key"
# export MABINOGI_ITEMS="심술 난 고양이의 구슬"
# export DISCORD_BOT_TOKEN="your_discord_bot_token"
# export DISCORD_CHANNEL_ID="your_discord_channel_id"
# ───────────────────────────────────────────────────────────────────────

load_dotenv()

API_KEY = os.getenv("MABINOGI_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
CHECK_INTERVAL = 1  # 초 단위; 예: 1초마다 체크
API_ENDPOINT = "https://open.api.nexon.com/mabinogi/v1/auction/list"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Discord 봇 세팅
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def get_items():
    """환경 변수에서 아이템 목록을 가져옵니다."""
    vals = dotenv_values(".env")
    raw = vals.get("MABINOGI_ITEMS", "")
    return [i.strip() for i in raw.split(",") if i.strip()]


def save_items(items):
    """아이템 목록을 환경 변수에 저장합니다."""
    set_key(".env", "MABINOGI_ITEMS", ",".join(items))
    load_dotenv()


def fetch_market_data(item_name):
    """Mabinogi API에서 평균 판매가와 등록 최저가를 가져옵니다."""
    headers = {
        "accept": "application/json",
        "x-nxopen-api-key": API_KEY,
    }
    params = {
        "item_name": quote(item_name),
    }

    try:
        resp = requests.get(API_ENDPOINT, headers=headers, params=params)
        if resp.status_code != 200:
            logging.error(f"API 요청 실패: {resp.status_code} {resp.text}")
            return None, None
    except requests.RequestException as e:
        logging.error(f"API 요청 실패: {e}")
        return None, None

    data = resp.json()
    auction_item = data.get("auction_item", [])
    if not auction_item:
        logging.error(f"아이템 {item_name} 데이터 없음")
        return None, None
    auction_item.sort(key=lambda x: x["auction_price_per_unit"])

    first_item, second_item = auction_item[0], auction_item[1]
    lowest_price, next_price = first_item.get("auction_price_per_unit", 0), second_item.get("auction_price_per_unit", 0)

    return lowest_price, next_price


async def send_discord_alert(item_name, next_price, lowest_price):
    """봇으로 지정 채널에 알림을 보냅니다."""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)
        except discord.NotFound:
            logging.error(f"채널({DISCORD_CHANNEL_ID})을 찾을 수 없습니다.")
            return
        except discord.Forbidden:
            logging.error(f"채널({DISCORD_CHANNEL_ID}) 접근 권한이 없습니다.")
            return
        except Exception as e:
            logging.error(f"채널 조회 실패: {e}")
            return

    discount = 100 * (1 - lowest_price / next_price)
    await channel.send(
        f":rotating_light: **아이템 `{item_name}` 특가 알림!**\n" f"- 일반 판매가: `{next_price:,}`\n" f"- 최저 등록가: `{lowest_price:,}`\n" f"- 할인율: `{discount:.1f}%`"
    )
    logging.info(f"봇 알림 전송 완료: 아이템 {item_name}")


@tasks.loop(seconds=CHECK_INTERVAL)
async def price_check():
    """가격 모니터링 태스크"""
    items = get_items()
    for name in items:
        lowest_price, next_price = fetch_market_data(name)
        if lowest_price is None or next_price is None:
            logging.warning(f"{name} 데이터 부족, 스킵")
            continue
        logging.info(f"{name} → 일반: {next_price:,}, 최저: {lowest_price:,}")
        if lowest_price <= next_price * 0.1:
            await send_discord_alert(name, next_price, lowest_price)


@price_check.before_loop
async def before():
    """태스크 시작 전 대기"""
    await bot.wait_until_ready()
    logging.info("가격 모니터링 태스크 시작")


@bot.event
async def on_ready():
    if not price_check.is_running():
        price_check.start()
    logging.info(f"{bot.user} 으로 로그인 성공, 가격 모니터링 시작!")


@bot.command(name="추가")
async def add_item(ctx, *, item_name: str):
    items = get_items()
    if item_name in items:
        return await ctx.send(f"❗️ {item_name}은 이미 모니터링 중입니다.")

    items.append(item_name)
    save_items(items)
    await ctx.send(f"✅ {item_name} 추가 완료!\n현재 모니터링:\n{'\n'.join(items)}")
    if price_check.is_running():
        price_check.restart()


@add_item.error
async def add_item_error(ctx, error):
    await ctx.send("❗️ 아이템 이름을 다시 확인해주세요.")


@bot.command(name="제거")
async def remove_item(ctx, *, item_name: str):
    items = get_items()
    if item_name not in items:
        return await ctx.send(f"❗️ {item_name}은(는) 목록에 없습니다.")

    items.remove(item_name)
    save_items(items)
    await ctx.send(f"✅ {item_name} 제거 완료!\n현재 모니터링:\n{'\n'.join(items) or '없음'}")
    if price_check.is_running():
        price_check.restart()


@remove_item.error
async def remove_item_error(ctx, error):
    await ctx.send("❗️ 아이템 이름을 다시 확인해주세요.")


@bot.command(name="목록")
async def list_items(ctx):
    items = get_items()
    if not items:
        return await ctx.send("❗️ 현재 모니터링 중인 아이템이 없습니다.")
    await ctx.send(f"✅ 현재 모니터링 중인 아이템:\n{'\n'.join(items)}")


if __name__ == "__main__":
    if not all([API_KEY, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID]):
        logging.error("`.env` 에 MABINOGI_API_KEY, DISCORD_WEBHOOK_URL 설정 필요")
        exit(1)
    bot.run(DISCORD_BOT_TOKEN)
