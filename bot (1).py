import os
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import TelegramError
import logging
from supabase import create_client, Client
from web3 import Web3
import aiohttp
import re

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configs
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
ETHERSCAN_API = os.getenv('ETHERSCAN_API_KEY')
DEX_SCREENER_API = "https://api.dexscreener.com/latest/dex"

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Web3 setup
W3 = Web3(Web3.HTTPProvider('https://eth.blockscout.com'))

class TokenAnalyzer:
    """Analyse les tokens avec scoring intelligent"""
    
    def __init__(self):
        self.etherscan_api = ETHERSCAN_API
        
    async def get_token_info(self, ca: str) -> dict:
        """Récupère infos du token"""
        try:
            async with aiohttp.ClientSession() as session:
                # Dex Screener
                async with session.get(f"{DEX_SCREENER_API}/search?q={ca}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['pairs']:
                            return data['pairs'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching token: {e}")
            return None
    
    async def get_holder_data(self, ca: str) -> dict:
        """Récupère les holders via Etherscan"""
        try:
            url = f"https://api.etherscan.io/api?module=token&action=tokenholderlist&contractaddress={ca}&apikey={self.etherscan_api}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['result']:
                            holders = data['result']
                            top_10_holding = sum([float(h['TokenHolding']) for h in holders[:10]])
                            total_supply = sum([float(h['TokenHolding']) for h in holders])
                            concentration = (top_10_holding / total_supply * 100) if total_supply > 0 else 0
                            return {
                                'total_holders': len(holders),
                                'top_10_concentration': concentration,
                                'top_holder_pct': float(holders[0]['TokenHolding']) / total_supply * 100 if total_supply > 0 else 0
                            }
            return None
        except Exception as e:
            logger.error(f"Error fetching holders: {e}")
            return None
    
    async def get_contract_safety(self, ca: str) -> dict:
        """Vérifie sécurité du contrat"""
        try:
            url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={ca}&apikey={self.etherscan_api}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data['result']:
                            source = data['result'][0]['SourceCode'].lower()
                            return {
                                'has_mint': 'mint' in source,
                                'has_pause': 'pause' in source,
                                'is_proxy': data['result'][0]['Proxy'] == '1'
                            }
            return None
        except Exception as e:
            logger.error(f"Error checking contract: {e}")
            return None
    
    def calculate_score(self, token_data: dict, holders_data: dict, contract_data: dict) -> tuple[int, dict]:
        """Calcule le score de fiabilité (0-100)"""
        score = 0
        details = {}
        
        # 1. HOLDERS ANALYSIS (25 pts)
        if holders_data:
            holder_score = 0
            total_holders = holders_data.get('total_holders', 0)
            
            if total_holders >= 100:
                holder_score += 10
            elif total_holders >= 50:
                holder_score += 7
            elif total_holders >= 20:
                holder_score += 4
            
            concentration = holders_data.get('top_10_concentration', 100)
            if concentration < 30:
                holder_score += 10
            elif concentration < 50:
                holder_score += 6
            elif concentration < 70:
                holder_score += 2
            
            top_holder = holders_data.get('top_holder_pct', 100)
            if top_holder < 20:
                holder_score += 5
            elif top_holder > 50:
                holder_score = max(0, holder_score - 5)
            
            score += holder_score
            details['holders_score'] = holder_score
        
        # 2. CONTRACT SAFETY (20 pts)
        if contract_data:
            safety_score = 15
            if not contract_data.get('has_mint', False):
                safety_score += 3
            if not contract_data.get('has_pause', False):
                safety_score += 2
            if not contract_data.get('is_proxy', False):
                safety_score += 0  # Neutral
            
            score += safety_score
            details['safety_score'] = safety_score
        
        # 3. LIQUIDITY & VOLUME (20 pts)
        if token_data:
            liq_score = 0
            liquidity = float(token_data.get('liquidity', {}).get('usd', 0) or 0)
            volume_24h = float(token_data.get('volume', {}).get('h24', 0) or 0)
            
            if liquidity > 100000:
                liq_score += 10
            elif liquidity > 50000:
                liq_score += 7
            elif liquidity > 10000:
                liq_score += 4
            
            if volume_24h > 0 and liquidity > 0:
                volume_liq_ratio = volume_24h / liquidity
                if volume_liq_ratio < 5:
                    liq_score += 10
                elif volume_liq_ratio < 10:
                    liq_score += 6
                elif volume_liq_ratio < 20:
                    liq_score += 2
            
            score += liq_score
            details['liquidity_score'] = liq_score
        
        # 4. AGE & FRESHNESS (15 pts)
        if token_data and token_data.get('pairCreatedAt'):
            age_score = 0
            created = datetime.fromisoformat(token_data['pairCreatedAt'].replace('Z', '+00:00'))
            age_hours = (datetime.now(created.tzinfo) - created).total_seconds() / 3600
            
            if age_hours < 1:
                age_score = 2  # Très neuf = risqué
            elif age_hours < 24:
                age_score = 8
            elif age_hours < 7*24:
                age_score = 12
            else:
                age_score = 15
            
            score += age_score
            details['age_score'] = age_score
        
        # 5. PRICE ACTION (20 pts)
        if token_data:
            price_score = 0
            price_change_24h = float(token_data.get('priceChange', {}).get('h24', 0) or 0)
            
            if -50 < price_change_24h < 50:
                price_score = 10
            elif -80 < price_change_24h < 100:
                price_score = 6
            else:
                price_score = 2
            
            score += price_score
            details['price_score'] = price_score
        
        return min(100, score), details

class TradingBot:
    """Bot principal Telegram"""
    
    def __init__(self):
        self.analyzer = TokenAnalyzer()
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Configure les handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("setup", self.setup_user))
        self.app.add_handler(CommandHandler("status", self.user_status))
        self.app.add_handler(CommandHandler("analyze", self.analyze_token))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user_id = update.effective_user.id
        
        try:
            user = supabase.table('users').select('*').eq('id', user_id).execute()
            
            if not user.data:
                await update.message.reply_text(
                    "🤖 Bienvenue sur CryptoBot!\n\n"
                    "C'est ta première fois? Utilise /setup pour configurer!"
                )
            else:
                await update.message.reply_text(
                    f"👋 Welcome back!\n\n"
                    f"💰 Wallet: {user.data[0]['wallet']}\n"
                    f"💵 Budget: ${user.data[0]['budget_per_trade']}\n"
                    f"Utilise /status pour voir tes trades!"
                )
        except Exception as e:
            logger.error(f"Error in start: {e}")
            await update.message.reply_text("❌ Erreur. Réessaie avec /setup")
    
    async def setup_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Configuration utilisateur"""
        user_id = update.effective_user.id
        
        msg = await update.message.reply_text(
            "⚙️ **SETUP INITIAL**\n\n"
            "1️⃣ Envoie ton adresse wallet (0x...)"
        )
        context.user_data['setup_step'] = 1
        context.user_data['user_id'] = user_id
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les messages texte (setup flow)"""
        if 'setup_step' not in context.user_data:
            return
        
        step = context.user_data['setup_step']
        user_id = context.user_data['user_id']
        text = update.message.text
        
        if step == 1:  # Wallet
            if not text.startswith('0x') or len(text) != 42:
                await update.message.reply_text("❌ Adresse invalide. Envoie une adresse Ethereum valide (0x...)")
                return
            
            context.user_data['wallet'] = text
            context.user_data['setup_step'] = 2
            await update.message.reply_text("✅ Wallet sauvegardé!\n\n2️⃣ Quel est ton budget par trade? (ex: 50 pour $50)")
        
        elif step == 2:  # Budget
            try:
                budget = float(text)
                if budget <= 0:
                    raise ValueError
                context.user_data['budget'] = budget
                context.user_data['setup_step'] = 3
                await update.message.reply_text(
                    "✅ Budget: $" + str(budget) + "\n\n"
                    "3️⃣ Target profit? (ex: 50 pour +50%, 100 pour +100%)"
                )
            except:
                await update.message.reply_text("❌ Entre un nombre valide")
        
        elif step == 3:  # TP
            try:
                tp = float(text)
                if tp <= 0:
                    raise ValueError
                context.user_data['tp'] = tp
                context.user_data['setup_step'] = 4
                await update.message.reply_text(
                    "✅ TP: +" + str(tp) + "%\n\n"
                    "4️⃣ Stop loss? (ex: 30 pour -30%)"
                )
            except:
                await update.message.reply_text("❌ Entre un nombre valide")
        
        elif step == 4:  # SL
            try:
                sl = float(text)
                if sl <= 0:
                    raise ValueError
                
                # Save to Supabase
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
                    "Envoie un CA (Contract Address) pour analyser un token!"
                )
                del context.user_data['setup_step']
            except:
                await update.message.reply_text("❌ Entre un nombre valide")
    
    async def analyze_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyse un token"""
        if len(context.args) == 0:
            await update.message.reply_text("Usage: /analyze 0x...")
            return
        
        ca = context.args[0].strip()
        if not ca.startswith('0x'):
            await update.message.reply_text("❌ Contract Address invalide")
            return
        
        msg = await update.message.reply_text("🔍 Analyse en cours...")
        
        try:
            token_data = await self.analyzer.get_token_info(ca)
            holders_data = await self.analyzer.get_holder_data(ca)
            contract_data = await self.analyzer.get_contract_safety(ca)
            
            score, details = self.analyzer.calculate_score(token_data, holders_data, contract_data)
            
            # Calcule position sizing
            if score >= 80:
                position = 30
                risk = "🟢 BAS"
            elif score >= 60:
                position = 15
                risk = "🟡 MOYEN"
            elif score >= 40:
                position = 8
                risk = "🔴 HAUT"
            else:
                position = 2
                risk = "🔴 TRÈS HAUT"
            
            # Build rapport
            rapport = f"""
🔍 **ANALYSE TOKEN**

**Score: {score}/100** {risk}

📊 **DONNÉES:**
• Holders: {holders_data.get('total_holders', 'N/A') if holders_data else 'N/A'}
• Top 10: {holders_data.get('top_10_concentration', 0):.1f}%" if holders_data else 'N/A'
• Liquidité: ${token_data.get('liquidity', {}).get('usd', 0) if token_data else 0:,.0f}"
• Vol 24h: ${token_data.get('volume', {}).get('h24', 0) if token_data else 0:,.0f}"

💰 **RECOMMANDATION:**
Position: **{position}%** du capital

🔗 **CA:** `{ca}`
"""
            
            await msg.edit_text(rapport, parse_mode='Markdown')
            
            # Buttons
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ BUY", callback_data=f"buy_{ca}"),
                 InlineKeyboardButton("❌ PASS", callback_data="pass")]
            ])
            await update.message.reply_text("Action?", reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error analyzing: {e}")
            await msg.edit_text(f"❌ Erreur: {str(e)}")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les boutons"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("buy_"):
            ca = query.data.replace("buy_", "")
            user_id = update.effective_user.id
            
            try:
                user = supabase.table('users').select('*').eq('id', user_id).execute()
                if not user.data:
                    await query.edit_message_text("❌ Setup d'abord avec /setup")
                    return
                
                await query.edit_message_text(
                    f"✅ **BUY CONFIRMÉ**\n\n"
                    f"**CA:** `{ca}`\n"
                    f"**Budget:** ${user.data[0]['budget_per_trade']}\n\n"
                    f"Paste dans BasedBot et achète! 🚀"
                )
            except Exception as e:
                await query.edit_message_text(f"❌ Erreur: {e}")
        
        elif query.data == "pass":
            await query.edit_message_text("⏭️ Passé")
    
    async def user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Affiche le statut utilisateur"""
        user_id = update.effective_user.id
        
        try:
            trades = supabase.table('trades').select('*').eq('user_id', user_id).execute()
            
            if not trades.data:
                await update.message.reply_text("Pas de trades encore")
                return
            
            total_profit = sum([t.get('profit_loss', 0) for t in trades.data])
            active_trades = [t for t in trades.data if t['status'] == 'holding']
            
            msg = f"""
📊 **TON PORTFOLIO**

💰 Total P&L: ${total_profit:+.2f}
📈 Trades actifs: {len(active_trades)}
✅ Trades fermés: {len(trades.data) - len(active_trades)}
"""
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in status: {e}")
            await update.message.reply_text("❌ Erreur")
    
    def run(self):
        """Lance le bot"""
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.run_polling()

if __name__ == '__main__':
    bot = TradingBot()
    bot.run()
