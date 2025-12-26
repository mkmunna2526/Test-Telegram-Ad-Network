"""
Telegram Ad Network Bot
With environment variables for better security
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# CONFIGURATION FROM ENVIRONMENT VARIABLES
# ============================================

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'TestTelegramAdNetwork_bot')
CHANNEL_URL = os.getenv('TELEGRAM_CHANNEL_URL', 'https://t.me/momtetop')
WEB_APP_URL = os.getenv('WEB_APP_URL')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL')

# Firebase credentials file path
FIREBASE_CRED_FILE = 'firebase-credentials.json'

# ============================================
# FIREBASE INITIALIZATION
# ============================================

def init_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        if os.path.exists(FIREBASE_CRED_FILE):
            cred = credentials.Certificate(FIREBASE_CRED_FILE)
            firebase_admin.initialize_app(cred, {
                'databaseURL': DATABASE_URL
            })
            print("✅ Firebase initialized")
        else:
            print("❌ Firebase credentials file not found!")
            print(f"Please download firebase-credentials.json from Firebase Console")
            exit(1)
    except Exception as e:
        print(f"❌ Firebase error: {e}")
        exit(1)

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_user_data(telegram_id):
    """Get user data from Firebase"""
    try:
        ref = db.reference(f'users/tg_{telegram_id}')
        return ref.get()
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def create_user(telegram_id, username, first_name, last_name, referrer_id=None):
    """Create new user in Firebase"""
    try:
        user_id = f'tg_{telegram_id}'
        ref = db.reference(f'users/{user_id}')
        
        user_data = {
            'userId': user_id,
            'telegramId': telegram_id,
            'telegramName': f"{first_name} {last_name or ''}".strip(),
            'username': username or '',
            'balance': 0,
            'adsWatched': 0,
            'dailyAdsWatched': 0,
            'network1AdsWatched': 0,
            'network2AdsWatched': 0,
            'referrals': 0,
            'referralEarnings': 0,
            'totalEarnings': 0,
            'totalWithdrawals': 0,
            'withdrawalPending': False,
            'lastReferralCount': 0,
            'joinDate': db.ServerValue.TIMESTAMP,
            'lastUpdated': db.ServerValue.TIMESTAMP
        }
        
        ref.set(user_data)
        
        # Handle referral
        if referrer_id and referrer_id != user_id:
            handle_referral(referrer_id, user_id, telegram_id)
        
        print(f"✅ User created: {user_id}")
        return user_data
        
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def handle_referral(referrer_id, new_user_id, new_telegram_id):
    """Handle referral reward"""
    try:
        # Save referral relationship
        ref = db.reference(f'referrals/{referrer_id}/{new_user_id}')
        ref.set({
            'referredAt': db.ServerValue.TIMESTAMP,
            'userId': new_user_id,
            'telegramId': new_telegram_id
        })
        
        # Update referrer stats
        referrer_ref = db.reference(f'users/{referrer_id}')
        referrer_data = referrer_ref.get()
        
        if referrer_data:
            referrer_ref.update({
                'referrals': (referrer_data.get('referrals', 0) + 1),
                'referralEarnings': (referrer_data.get('referralEarnings', 0) + 0.01),
                'balance': (referrer_data.get('balance', 0) + 0.01),
                'totalEarnings': (referrer_data.get('totalEarnings', 0) + 0.01)
            })
            
            print(f"✅ Referral: {referrer_id} → {new_user_id}")
        
    except Exception as e:
        print(f"Error handling referral: {e}")

# ============================================
# BOT COMMANDS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    telegram_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    # Get referrer ID from start parameter
    referrer_id = None
    if context.args:
        referrer_id = context.args[0]
        print(f"Referrer detected: {referrer_id}")
    
    # Check if user exists
    user_data = get_user_data(telegram_id)
    
    if not user_data:
        # Create new user
        user_data = create_user(telegram_id, username, first_name, last_name, referrer_id)
        
        welcome_text = (
            f"🎉 <b>Welcome!</b>\n\n"
            f"👤 {first_name} {last_name or ''}\n"
            f"🆔 ID: <code>{telegram_id}</code>\n\n"
            f"💰 <b>Earn Money:</b>\n"
            f"  • Watch 10 ads daily\n"
            f"  • Refer friends (+$0.01)\n"
            f"  • Complete tasks\n\n"
            f"📲 Click below to start!"
        )
        
        if referrer_id:
            welcome_text += f"\n\n🎁 Referred by a friend!"
    else:
        welcome_text = (
            f"👋 <b>Welcome back, {first_name}!</b>\n\n"
            f"💰 Balance: ${user_data.get('balance', 0):.2f}\n"
            f"📺 Ads Today: {user_data.get('dailyAdsWatched', 0)}/10\n"
            f"👥 Referrals: {user_data.get('referrals', 0)}\n\n"
            f"📲 Continue earning!"
        )
    
    # Create keyboard
    keyboard = [
        [InlineKeyboardButton("🚀 Open App", web_app={"url": f"{WEB_APP_URL}?tg_id={telegram_id}&tg_name={first_name}"})],
        [InlineKeyboardButton("📱 Join Channel", url=CHANNEL_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user = update.effective_user
    telegram_id = user.id
    
    user_data = get_user_data(telegram_id)
    
    if not user_data:
        await update.message.reply_text("❌ Use /start first!")
        return
    
    balance_text = (
        f"💰 <b>Your Balance</b>\n\n"
        f"💵 Balance: ${user_data.get('balance', 0):.2f}\n"
        f"📊 Total Earned: ${user_data.get('totalEarnings', 0):.2f}\n"
        f"🎁 From Referrals: ${user_data.get('referralEarnings', 0):.2f}\n\n"
        f"📺 Total Ads: {user_data.get('adsWatched', 0)}\n"
        f"📺 Today: {user_data.get('dailyAdsWatched', 0)}/10\n"
        f"👥 Referrals: {user_data.get('referrals', 0)}"
    )
    
    await update.message.reply_html(balance_text)

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /referrals command"""
    user = update.effective_user
    telegram_id = user.id
    
    user_data = get_user_data(telegram_id)
    
    if not user_data:
        await update.message.reply_text("❌ Use /start first!")
        return
    
    user_id = f"tg_{telegram_id}"
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    referrals_text = (
        f"👥 <b>Your Referrals</b>\n\n"
        f"📊 Total: {user_data.get('referrals', 0)}\n"
        f"💰 Earned: ${user_data.get('referralEarnings', 0):.2f}\n\n"
        f"🔗 <b>Your Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"💡 Earn $0.01 per referral!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={referral_link}&text=Join and earn!")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(referrals_text, reply_markup=reply_markup)

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /withdraw command"""
    user = update.effective_user
    telegram_id = user.id
    
    user_data = get_user_data(telegram_id)
    
    if not user_data:
        await update.message.reply_text("❌ Use /start first!")
        return
    
    balance = user_data.get('balance', 0)
    referrals = user_data.get('referrals', 0)
    total_withdrawals = user_data.get('totalWithdrawals', 0)
    withdrawal_pending = user_data.get('withdrawalPending', False)
    
    if withdrawal_pending:
        await update.message.reply_text("⏳ Withdrawal pending!")
        return
    
    if total_withdrawals == 0 and referrals < 15:
        remaining = 15 - referrals
        await update.message.reply_html(
            f"🚫 <b>Cannot Withdraw</b>\n\n"
            f"Need {remaining} more referrals!\n"
            f"Current: {referrals}/15"
        )
        return
    
    if balance < 60:
        await update.message.reply_html(
            f"🚫 <b>Insufficient Balance</b>\n\n"
            f"Minimum: $60.00\n"
            f"Balance: ${balance:.2f}\n"
            f"Need: ${(60 - balance):.2f}"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("💳 Withdraw", web_app={"url": f"{WEB_APP_URL}?tg_id={telegram_id}&screen=withdraw"})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"✅ <b>You Can Withdraw!</b>\n\n"
        f"💰 Balance: ${balance:.2f}\n"
        f"👥 Referrals: {referrals}",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📚 <b>Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Start earning\n"
        "/balance - Check balance\n"
        "/referrals - View referrals\n"
        "/withdraw - Withdraw funds\n"
        "/help - This message\n"
        "/stats - Bot stats (Admin)\n\n"
        "<b>How to Earn:</b>\n"
        "• 10 ads/day ($0.01 each)\n"
        "• Referrals ($0.01 each)\n"
        "• Tasks\n\n"
        "<b>Withdrawal:</b>\n"
        "• First: 15 refs + $60\n"
        "• Next: 10 refs each"
    )
    
    await update.message.reply_html(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (Admin only)"""
    user = update.effective_user
    
    # Admin check
    if str(user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    try:
        # Get stats
        users_ref = db.reference('users')
        users_snapshot = users_ref.get()
        total_users = len(users_snapshot) if users_snapshot else 0
        
        refs_ref = db.reference('referrals')
        refs_snapshot = refs_ref.get()
        total_refs = 0
        if refs_snapshot:
            for user_refs in refs_snapshot.values():
                total_refs += len(user_refs)
        
        withdrawals_ref = db.reference('withdrawals')
        withdrawals_snapshot = withdrawals_ref.get()
        total_withdrawals = len(withdrawals_snapshot) if withdrawals_snapshot else 0
        
        stats_text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Users: {total_users}\n"
            f"🔗 Referrals: {total_refs}\n"
            f"💳 Withdrawals: {total_withdrawals}\n\n"
            f"🤖 @{BOT_USERNAME}"
        )
        
        await update.message.reply_html(stats_text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Start the bot"""
    print("🚀 Starting Telegram Ad Network Bot...")
    print(f"Bot: @{BOT_USERNAME}")
    
    # Check environment variables
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env file!")
        exit(1)
    
    if not WEB_APP_URL:
        print("❌ WEB_APP_URL not found in .env file!")
        exit(1)
    
    # Initialize Firebase
    init_firebase()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("referrals", referrals_command))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Start polling
    print("✅ Bot is running!")
    print(f"🔗 https://t.me/{BOT_USERNAME}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
