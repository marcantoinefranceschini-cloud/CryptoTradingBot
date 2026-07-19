import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import aiohttp

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configs
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
ETHERSCAN_API = os.getenv('ETHERSCAN_API_KEY')

# Supabase Client
supabase = None
try:
    from supabase import create_client
    supabase = create_client(url=SUPABASE_URL, key=SUPABASE_KEY)
    logger.info("✅ Supabase connected!")
except Exception as e:
    logger.error(f"❌ Supabase error: {e}")
    supabase = None

class TokenAnalyzer:
    """Analyse les tokens"""
    
    async def get_token_info(self, ca: str) -> dict:
        """Récupère infos du token"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.dexscreener.com/latest/dex/search?q={ca}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('pairs'):
                            return data['pairs'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching token: {e}")
            return None
    
    def calculate_score(self, token_data: dict) -> tuple[int, str]:
        """Calcule score simplifié"""
        if not token_data:
            return 0, "❌ Token not found"
        
        score = 50  # Base
        
        # Liquidity bonus
        liq = float(token_data.get('liquidity', {}).get('usd', 0) or 0)
        if liq > 100000:
            score += 20
        elif liq > 50000:
            score += 15
        elif liq > 10000:
            score += 10
        
        # Volume bonus
        vol = float(token_data.get('volume', {}).get('h24', 0) or 0)
        if vol > 0:
            ratio = vol / max(liq, 1)
            if ratio < 10:
                score += 15
            elif ratio < 20:
                score += 10
        
        # Price action
        price_change = float(token_data.get('priceChange', {}).get('h24', 0) or 0)
        if -50 < price_change < 50:
            score += 15
        
        return min(100, score), "✅ Analyzed"

class TradingBot:
    """Bot principal"""
    
    def __init__(self):
        self.analyzer = TokenAnalyzer()
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Configure handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("setup", self.setup_user))
        self.app.add_handler(CommandHandler("analyze", self.analyze_token))
        self.app.add_handler(CommandHandler("status", self.user_status))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user_id = update.effective_user.id
        
        if not supabase:
            await update.message.reply_text("⚠️ Database connection issue. Try /setup anyway!")
            return
        
        try:
            user = supabase.table('users').select('*').eq('id', user_id).execute()
            
            if not user.data:
                await update.message.reply_text(
                    "🤖 **Welcome to CryptoBot!**\n\n"
                    "Use /setup to configure your wallet!"
                )
            else:
                await update.message.reply_text(
                    f"👋 Welcome back!\n\n"
                    f"💰 Wallet: {user.data[0]['wallet'][:10]}...\n"
                    f"Use /status to see your trades!"
                )
        except Exception as e:
            logger.error(f"Error in start: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def setup_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Setup user"""
        await update.message.reply_text(
            "⚙️ **SETUP**\n\n"
            "1️⃣ Send your wallet address (0x...)"
        )
        context.user_data['setup_step'] = 1
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        if 'setup_step' not in context.user_data:
            return
        
        step = context.user_data['setup_step']
        user_id = update.effective_user.id
        text = update.message.text
        
        if step == 1:
            if not text.startswith('0x') or len(text) != 42:
                await update.message.reply_text("❌ Invalid address. Send a valid Ethereum address (0x...)")
                return
            
            context.user_data['wallet'] = text
            context.user_data['setup_step'] = 2
            await update.message.reply_text("✅ Wallet saved!\n\n2️⃣ Budget per trade? (e.g., 50 for $50)")
        
        elif step == 2:
            try:
                budget = float(text)
                if budget <= 0:
                    raise ValueError
                context.user_data['budget'] = budget
                context.user_data['setup_step'] = 3
                await update.message.reply_text("✅ Budget: $" + str(budget) + "\n\n3️⃣ TP target? (e.g., 50 for +50%)")
            except:
                await update.message.reply_text("❌ Invalid number")
        
        elif step == 3:
            try:
                tp = float(text)
                if tp <= 0:
                    raise ValueError
                context.user_data['tp'] = tp
                context.user_data['setup_step'] = 4
                await update.message.reply_text("✅ TP: +" + str(tp) + "%\n\n4️⃣ Stop loss? (e.g., 30 for -30%)")
            except:
                await update.message.reply_text("❌ Invalid number")
        
        elif step == 4:
            try:
                sl = float(text)
                if sl <= 0:
                    raise ValueError
                
                if supabase:
                    try:
                        supabase.table('users').upsert({
                            'id': user_id,
                            'wallet': context.user_data['wallet'],
                            'budget_per_trade': context.user_data['budget'],
                            'tp_target': context.user_data['tp'],
                            'sl_limit': sl,
                            'created_at': datetime.now().isoformat()
                        }).execute()
                        
                        await update.message.reply_text(
                            "✅ **SETUP COMPLETE!**\n\n"
                            f"💰 Budget: ${context.user_data['budget']}\n"
                            f"📈 TP: +{context.user_data['tp']}%\n"
                            f"📉 SL: -{sl}%\n\n"
                            "Send a CA (Contract Address) to analyze a token!"
                        )
                    except Exception as e:
                        logger.error(f"Supabase save error: {e}")
                        await update.message.reply_text(f"⚠️ Setup saved locally (DB error: {str(e)})")
                else:
                    await update.message.reply_text("⚠️ Database offline. Setup saved locally!")
                
                del context.user_data['setup_step']
            except:
                await update.message.reply_text("❌ Invalid number")
    
    async def analyze_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze token"""
        if len(context.args) == 0:
            await update.message.reply_text("Usage: /analyze 0x...")
            return
        
        ca = context.args[0].strip()
        if not ca.startswith('0x'):
            await update.message.reply_text("❌ Invalid CA")
            return
        
        msg = await update.message.reply_text("🔍 Analyzing...")
        
        try:
            token_data = await self.analyzer.get_token_info(ca)
            score, status = self.analyzer.calculate_score(token_data)
            
            if score >= 80:
                position = 30
                risk = "🟢 LOW"
            elif score >= 60:
                position = 15
                risk = "🟡 MEDIUM"
            elif score >= 40:
                position = 8
                risk = "🔴 HIGH"
            else:
                position = 2
                risk = "🔴 VERY HIGH"
            
            rapport = f"""
🔍 **TOKEN ANALYSIS**

**Score: {score}/100** {risk}

📊 **DATA:**
• Liquidity: ${token_data.get('liquidity', {}).get('usd', 0) if token_data else 0:,.0f}
• Vol 24h: ${token_data.get('volume', {}).get('h24', 0) if token_data else 0:,.0f}
• Change 24h: {token_data.get('priceChange', {}).get('h24', 0) if token_data else 0:.1f}%

💰 **RECOMMENDATION:**
Position: **{position}%** of your budget

🔗 **CA:** `{ca}`
"""
            
            await msg.edit_text(rapport, parse_mode='Markdown')
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ BUY", callback_data=f"buy_{ca}"),
                 InlineKeyboardButton("❌ PASS", callback_data="pass")]
            ])
            await update.message.reply_text("Action?", reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            await msg.edit_text(f"❌ Error: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buttons"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("buy_"):
            ca = query.data.replace("buy_", "")
            await query.edit_message_text(
                f"✅ **BUY CONFIRMED**\n\n"
                f"**CA:** `{ca}`\n\n"
                f"Paste in BasedBot and buy! 🚀"
            )
        elif query.data == "pass":
            await query.edit_message_text("⏭️ Skipped")
    
    async def user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User status"""
        if not supabase:
            await update.message.reply_text("⚠️ Database offline")
            return
        
        try:
            trades = supabase.table('trades').select('*').eq('user_id', update.effective_user.id).execute()
            
            if not trades.data:
                await update.message.reply_text("No trades yet")
                return
            
            total_profit = sum([t.get('profit_loss', 0) for t in trades.data])
            
            msg = f"""
📊 **YOUR PORTFOLIO**

💰 Total P&L: ${total_profit:+.2f}
📈 Total trades: {len(trades.data)}
"""
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Status error: {e}")
            await update.message.reply_text("❌ Error")
    
    def run(self):
        """Run bot"""
        logger.info("🤖 Bot starting...")
        self.app.run_polling()

if __name__ == '__main__':
    bot = TradingBot()
    bot.run()
