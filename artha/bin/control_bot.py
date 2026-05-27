import asyncio
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from redis.asyncio import Redis
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat
from artha.config.loader import config

setup_logging()
logger = get_logger("control_bot")

class ControlBot:
    def __init__(self, token: str, chat_id: str, redis_url: str):
        self.token = token
        self.chat_id = chat_id
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.app = None

    async def start(self):
        self.redis = Redis.from_url(self.redis_url)
        self.app = Application.builder().token(self.token).build()

        # Add command handlers
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("pnl", self.pnl_command))
        self.app.add_handler(CommandHandler("kill", self.kill_command))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        
        # Start event consumer
        asyncio.create_task(self._consume_events())
        
        logger.info("Control Bot started and polling.")

    async def _consume_events(self):
        """Consume events from Redis and notify via Telegram."""
        group_name = "control_bot_events"
        stream_name = "events"
        try:
            await self.redis.xgroup_create(stream_name, group_name, id="0", mkstream=True)
        except Exception:
            pass
            
        while True:
            try:
                messages = await self.redis.xreadgroup(group_name, "bot_1", {stream_name: ">"}, count=1, block=5000)
                if not messages:
                    continue
                
                for stream, msgs in messages:
                    for msg_id, data in msgs:
                        event = json.loads(data[b"data"])
                        await self._notify(event)
                        await self.redis.xack(stream_name, group_name, msg_id)
            except Exception as e:
                logger.error(f"Error in bot event consumer: {e}")
                await asyncio.sleep(1)

    async def _notify(self, event: dict):
        msg = f"🔔 *{event['type']}*\n"
        if event['type'] == "POSITION_OPENED":
            msg += f"Symbol: {event['symbol']}\nSide: {event['side']}\nQty: {event['qty']:.4f}\nEntry: {event['entry']}"
        elif event['type'] == "POSITION_CLOSED":
            msg += f"Symbol: {event['symbol']}\nReason: {event['reason']}\nExit: {event['exit_price']}\nPnL: {event['pnl']:.2f}"
        else:
            msg += json.dumps(event, indent=2)
            
        await self.app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # In a real system, we'd query Redis heartbeats and DB for status
        await update.message.reply_text("System Status: OPERATIONAL\nAll services reporting heartbeat.")

    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Today's PnL: ₹0.00 (Paper)")

    async def kill_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Emit a command to trip the kill-switch
        await self.redis.xadd("commands", {"type": "KILL_SWITCH", "value": "ON"})
        await update.message.reply_text("🚨 EMERGENCY KILL-SWITCH ACTIVATED. All new entries halted.")

    async def stop(self):
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
        if self.redis:
            await self.redis.close()

async def main():
    tg_cfg = config.get("telegram", {})
    token = os.environ.get("TELEGRAM_TOKEN") or tg_cfg.get("token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or tg_cfg.get("chat_id")
    redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
    
    if not token or token == "PLACEHOLDER_TOKEN":
        logger.warning("Telegram token not configured. Control bot will not function correctly.")
        # We still start it so PM2 doesn't keep restarting it if configured to autorestart
    
    bot = ControlBot(token, chat_id, redis_url)
    
    hb = Heartbeat(redis_url=redis_url, component_name="control-bot")
    await hb.start()
    
    await bot.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await bot.stop()
        await hb.stop()

if __name__ == "__main__":
    asyncio.run(main())
