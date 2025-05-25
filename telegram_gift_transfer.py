import requests
import json
import sys
import time
import os
import argparse
from datetime import datetime
import logging
import logging.config
import logging.handlers
import traceback

# Parse command line arguments
parser = argparse.ArgumentParser(description='Telegram Gift Transfer Tool')
parser.add_argument('--config', help='Path to a JSON configuration file')
args = parser.parse_args()

# === CONFIGURATION ===
# Default configuration values
BOT_TOKEN = '0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
BUSINESS_CONNECTION_ID = '0000000000'   
TARGET_CHAT_ID = 0000000000
STAR_COUNT = 25
MAX_RETRIES = 3
RETRY_DELAY = 5
TRANSFER_WAIT_TIME = 60

# Override configuration from file if provided
if args.config and os.path.exists(args.config):
    try:
        with open(args.config, 'r') as config_file:
            config_data = json.load(config_file)
            
            # Update configuration with values from file
            BOT_TOKEN = config_data.get('BOT_TOKEN', BOT_TOKEN)
            BUSINESS_CONNECTION_ID = config_data.get('BUSINESS_CONNECTION_ID', BUSINESS_CONNECTION_ID)
            TARGET_CHAT_ID = config_data.get('TARGET_CHAT_ID', TARGET_CHAT_ID)
            STAR_COUNT = config_data.get('STAR_COUNT', STAR_COUNT)
            MAX_RETRIES = config_data.get('MAX_RETRIES', MAX_RETRIES)
            RETRY_DELAY = config_data.get('RETRY_DELAY', RETRY_DELAY)
            TRANSFER_WAIT_TIME = config_data.get('TRANSFER_WAIT_TIME', TRANSFER_WAIT_TIME)
            
            print(f"Configuration loaded from {args.config}")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading configuration file: {e}")

# API endpoints
API_BASE_URL = 'https://api.telegram.org/bot'
API_ENDPOINTS = {
    'get_me': 'getMe',
    'get_chat': 'getChat',
    'get_business_star_balance': 'getBusinessAccountStarBalance',
    'transfer_business_stars': 'transferBusinessAccountStars',
    'get_business_gifts': 'getBusinessAccountGifts',
    'transfer_gift': 'transferGift'
}

# Setup logging
# Create logs directory if it doesn't exist
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
try:
    with open('logging_config.json', 'r') as f:
        config = json.load(f)
    
    # Ensure logs directory exists
    log_path = os.path.dirname(config['handlers']['file']['filename'])
    os.makedirs(log_path, exist_ok=True)
    
    # Generate unique log filename with timestamp if not using rotating handler
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    config['handlers']['file']['filename'] = f"logs/gift_transfer_log_{timestamp}.log"
    
    logging.config.dictConfig(config)
    logger = logging.getLogger("telegram_gift_transfer")
    logger.info("Logging configured successfully")
except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    # Fallback logging configuration if the config file is missing or invalid
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"logs/gift_transfer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        ]
    )
    logger = logging.getLogger("telegram_gift_transfer")
    logger.warning(f"Could not load logging config file: {str(e)}. Using default configuration.")

# Store the current log file path for reference
current_log_file = logger.handlers[1].baseFilename if len(logger.handlers) > 1 else "logs/gift_transfer_log.log"

def log_and_print(message, level="INFO"):
    """Log message and print to console with color formatting."""
    # Log to file with appropriate level
    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)
    
    # Print with appropriate color based on level (this is in addition to the logger's console output)
    if level == "ERROR":
        print(f"\033[91m{message}\033[0m")  # Red for errors
    elif level == "WARNING":
        print(f"\033[93m{message}\033[0m")  # Yellow for warnings
    elif level == "DEBUG":
        # Debug messages are usually verbose, so we don't print them to console unless configured
        pass
    else:
        # Regular messages are already handled by the console logger
        pass

def make_api_request(endpoint, payload=None, retry_count=MAX_RETRIES):
    """Make a request to the Telegram API with retry logic."""
    api_url = f'{API_BASE_URL}{BOT_TOKEN}/{endpoint}'
    
    for attempt in range(1, retry_count + 1):
        try:
            if payload:
                log_and_print(f"Sending request to {endpoint}")
                log_and_print(f"Payload: {json.dumps(payload, indent=2)}", "DEBUG")
                response = requests.post(api_url, json=payload, timeout=10)
            else:
                log_and_print(f"Sending request to {endpoint}")
                response = requests.post(api_url, timeout=10)
            
            result = response.json()
            
            log_and_print(f"Response: {json.dumps(result, indent=2)}", "DEBUG")
            
            if not result.get('ok') and attempt < retry_count:
                log_and_print(f"Request failed, retrying in {RETRY_DELAY} seconds... (Attempt {attempt}/{retry_count})", "WARNING")
                time.sleep(RETRY_DELAY)
                continue
                
            return result
            
        except Exception as e:
            log_and_print(f"Error making API request: {str(e)}", "ERROR")
            if attempt < retry_count:
                log_and_print(f"Will retry in {RETRY_DELAY} seconds... (Attempt {attempt}/{retry_count})", "WARNING")
                time.sleep(RETRY_DELAY)
            else:
                return {"ok": False, "description": f"Request failed after {retry_count} attempts: {str(e)}"}
    
    return {"ok": False, "description": f"Request failed after {retry_count} attempts"}

def check_api_connectivity():
    """Check if the Telegram API is accessible."""
    log_and_print("\n🔄 Checking API connectivity...")
    result = make_api_request(API_ENDPOINTS['get_me'], retry_count=1)
    
    if result.get('ok'):
        log_and_print("✅ API connection successful")
        return True
    else:
        log_and_print(f"❌ API connection failed: {result.get('description', 'Unknown error')}", "ERROR")
        return False

def validate_business_connection():
    """Validate the business connection ID."""
    log_and_print("\n🔄 Validating business connection ID...")
    result = make_api_request(API_ENDPOINTS['get_business_star_balance'], {
        "business_connection_id": BUSINESS_CONNECTION_ID
    })
    
    if result.get('ok'):
        log_and_print("✅ Business connection ID validated successfully")
        return True
    else:
        log_and_print(f"❌ Invalid business connection ID: {result.get('description', 'Unknown error')}", "ERROR")
        return False

def get_bot_info():
    """Get information about the bot."""
    log_and_print("\n🔄 Getting bot information...")
    result = make_api_request(API_ENDPOINTS['get_me'])
    
    if result.get('ok'):
        bot_info = result.get('result', {})
        log_and_print("✅ Bot information retrieved successfully")
        log_and_print(f"   Username: @{bot_info.get('username')}")
        log_and_print(f"   ID: {bot_info.get('id')}")
        log_and_print(f"   Is Business Bot: {bot_info.get('is_business_bot', False)}")
        
        # Warning if not a business bot
        if not bot_info.get('is_business_bot', False):
            log_and_print("⚠️ This bot is not a business bot. Gift and star functionality may be limited!", "WARNING")
            log_and_print("   Consider upgrading to a business bot through BotFather.", "WARNING")
        
        return bot_info
    else:
        log_and_print(f"❌ Failed to get bot info: {result.get('description', 'Unknown error')}", "ERROR")
        return None

def validate_chat_id(chat_id):
    """Validate that the target chat ID exists and is accessible."""
    log_and_print(f"\n🔄 Validating target chat (ID: {chat_id})...")
    result = make_api_request(API_ENDPOINTS['get_chat'], {"chat_id": chat_id})
    
    if result.get('ok'):
        chat_info = result.get('result', {})
        log_and_print("✅ Target chat validated successfully")
        log_and_print(f"   Type: {chat_info.get('type')}")
        
        if 'username' in chat_info:
            log_and_print(f"   Username: @{chat_info.get('username')}")
        if 'title' in chat_info:
            log_and_print(f"   Title: {chat_info.get('title')}")
        if 'first_name' in chat_info:
            log_and_print(f"   Name: {chat_info.get('first_name')} {chat_info.get('last_name', '')}")
            
        # Check if chat accepts gifts
        if chat_info.get('can_send_gift') is False:
            log_and_print("⚠️ This chat may not accept gifts!", "WARNING")
            
        return True
    else:
        log_and_print(f"❌ Failed to validate chat: {result.get('description', 'Unknown error')}", "ERROR")
        return False

def get_business_star_balance():
    """Get the star balance of the business account."""
    log_and_print("\n🔄 Checking business account star balance...")
    result = make_api_request(API_ENDPOINTS['get_business_star_balance'], {
        "business_connection_id": BUSINESS_CONNECTION_ID
    })
    
    if result.get('ok'):
        star_balance = result.get('result', {}).get('amount', 0)
        log_and_print(f"✅ Business account star balance: {star_balance}")
        return star_balance
    else:
        log_and_print(f"❌ Failed to get business star balance: {result.get('description', 'Unknown error')}", "ERROR")
        return 0

def transfer_stars_to_bot():
    """Transfer stars from business account to bot."""
    log_and_print(f"\n🔄 Transferring {STAR_COUNT} stars to bot...")
    result = make_api_request(API_ENDPOINTS['transfer_business_stars'], {
        "business_connection_id": BUSINESS_CONNECTION_ID,
        "star_count": STAR_COUNT
    })
    
    if result.get('ok'):
        log_and_print(f"✅ Successfully transferred {STAR_COUNT} stars to bot")
        return True
    else:
        log_and_print(f"❌ Failed to transfer stars: {result.get('description', 'Unknown error')}", "ERROR")
        return False

def get_owned_gifts():
    """Get list of gifts owned by the bot/business account."""
    log_and_print("\n🔄 Retrieving owned gifts...")
    result = make_api_request(API_ENDPOINTS['get_business_gifts'], {
        "business_connection_id": BUSINESS_CONNECTION_ID,
        "limit": 100
    })
    
    if result.get('ok'):
        gifts = result.get('result', {}).get('gifts', [])
        total_count = result.get('result', {}).get('total_count', 0)
        log_and_print(f"✅ Found {total_count} gifts")
        return gifts
    else:
        log_and_print(f"❌ Failed to get gifts: {result.get('description', 'Unknown error')}", "ERROR")
        return []

def analyze_payment_error():
    """Analyze the PAYMENT_REQUIRED error in detail."""
    log_and_print("\n🔍 Analyzing PAYMENT_REQUIRED error...", "WARNING")
    log_and_print("This error occurs when the bot doesn't have enough stars in its own pool.", "WARNING")
    log_and_print("Possible causes:", "WARNING")
    log_and_print("1. The bot is not a business bot (most likely cause)", "WARNING")
    log_and_print("2. It's not possible to transfer stars from a business account to a regular bot", "WARNING")
    log_and_print("3. Telegram API has internal limitations", "WARNING")
    
    # Check only the business account balance
    business_stars = get_business_star_balance()
    
    log_and_print("\n📊 Current star balance:")
    log_and_print(f"Business account stars: {business_stars}")
    log_and_print(f"Required for transfer: {STAR_COUNT}")
    
    log_and_print("\nRecommended solutions:", "WARNING")
    log_and_print("1. Upgrade your bot to a business bot through BotFather", "WARNING")
    log_and_print("2. Create a new bot with 'Business Bot' type", "WARNING")
    log_and_print("3. Check the Telegram Bot API documentation", "WARNING")
    log_and_print("4. Contact Telegram support if the problem persists", "WARNING")

def transfer_gift(gift_id, chat_id, transfer_star_count):
    """Transfer a gift to a specific user."""
    log_and_print(f"\n🔄 Attempting to transfer gift {gift_id} to user {chat_id}...")
    result = make_api_request(API_ENDPOINTS['transfer_gift'], {
        "business_connection_id": BUSINESS_CONNECTION_ID,
        "owned_gift_id": gift_id,
        "new_owner_chat_id": chat_id,
        "transfer_star_count": transfer_star_count
    })
    
    if result.get('ok'):
        log_and_print(f"✅ Gift {gift_id} successfully transferred to user {chat_id}")
        return True
    else:
        error_desc = result.get('description', 'Unknown error')
        error_code = result.get('error_code', 0)
        log_and_print(f"❌ Error transferring gift: {error_desc} (error code: {error_code})", "ERROR")
        
        if "PAYMENT_REQUIRED" in error_desc:
            analyze_payment_error()
        elif "CHAT_NOT_FOUND" in error_desc:
            log_and_print("❌ The target chat ID is invalid or inaccessible.", "ERROR")
            log_and_print("Please verify that TARGET_CHAT_ID is correct and the user has interacted with the bot.", "ERROR")
        elif "Forbidden" in error_desc:
            log_and_print("❌ The bot does not have permission to perform this action.", "ERROR")
            log_and_print("Ensure the bot has necessary permissions and the user has not blocked it.", "ERROR")
        elif "Bad Request" in error_desc:
            log_and_print("❌ Invalid parameters in the transfer request.", "ERROR")
            log_and_print("Check owned_gift_id, transfer_star_count, and business_connection_id.", "ERROR")
        
        return False

def main():
    logger.info("=== Telegram Gift Transfer Tool ===")
    logger.info(f"Log file: {current_log_file}")
    logger.info(f"Target Chat ID: {TARGET_CHAT_ID}")
    logger.info(f"Business Connection ID: {BUSINESS_CONNECTION_ID}")
    logger.info(f"Star Count: {STAR_COUNT}")
    logger.info(f"Wait Time After Transfer: {TRANSFER_WAIT_TIME} seconds")
    logger.info("=" * 50)
    
    # Step 1: Check API connectivity
    if not check_api_connectivity():
        log_and_print("❌ Terminating: Could not connect to Telegram API", "ERROR")
        return
    
    # Step 2: Validate business connection
    if not validate_business_connection():
        log_and_print("❌ Terminating: Invalid BUSINESS_CONNECTION_ID", "ERROR")
        log_and_print("Please verify the BUSINESS_CONNECTION_ID in your Telegram business account settings.", "ERROR")
        return
    
    # Step 3: Get bot info and check if it's a business bot
    bot_info = get_bot_info()
    if not bot_info:
        log_and_print("❌ Terminating: Could not retrieve bot information", "ERROR")
        return
    
    # Check if bot is a business bot
    is_business_bot = bot_info.get('is_business_bot', False)
    bypass_business_check = config_data.get('BYPASS_BUSINESS_CHECK', False) if 'config_data' in locals() else False
    
    if not is_business_bot and not bypass_business_check:
        log_and_print("\n❌ Terminating: Bot is not a business bot.", "ERROR")
        log_and_print("Gift and star transfer functionality requires a business bot.", "ERROR")
        log_and_print("To resolve this:", "ERROR")
        log_and_print(f"1. Contact @BotFather and check if @{bot_info.get('username')} can be upgraded to a business bot.", "ERROR")
        log_and_print("2. Alternatively, create a new business bot using /newbot and enable business features.", "ERROR")
        log_and_print("3. Update BOT_TOKEN in the script with the new token.", "ERROR")
        log_and_print("\nTo bypass this check for testing (not recommended for production):", "WARNING")
        log_and_print("Add \"BYPASS_BUSINESS_CHECK\": true to your config file.", "WARNING")
        return
    
    if not is_business_bot and bypass_business_check:
        log_and_print("\n⚠️ WARNING: Bot is not a business bot, but check is bypassed.", "WARNING")
        log_and_print("Some functionality may not work as expected!", "WARNING")
    
    # Step 4: Validate target chat
    if not validate_chat_id(TARGET_CHAT_ID):
        log_and_print("❌ Terminating: Invalid target chat ID", "ERROR")
        return
    
    # Step 5: Check business account star balance
    business_stars = get_business_star_balance()
    if business_stars < STAR_COUNT * 2:
        log_and_print(f"❌ Terminating: Not enough stars in business account (need at least {STAR_COUNT * 2}, have {business_stars})", "ERROR")
        return
    
    # Step 6: Inform about bot star balance constraints
    log_and_print("\n⚠️ NOTE: The Telegram API does not provide a way to check bot star balance", "WARNING")
    log_and_print("   This is a limitation especially relevant for non-business bots", "WARNING")
    
    # Step 7: Transfer stars to bot
    if not transfer_stars_to_bot():
        log_and_print("❌ Terminating: Failed to transfer stars to bot", "ERROR")
        return
    
    # Step 8: Additional star transfer for reliability
    log_and_print("\n🔄 Attempting additional star transfer for reliability...")
    if not transfer_stars_to_bot():
        log_and_print("⚠️ Warning: Additional star transfer failed", "WARNING")
    
    # Step 9: Wait for star transfer to process
    log_and_print(f"⏳ Waiting {TRANSFER_WAIT_TIME} seconds for star transfer to process...")
    time.sleep(TRANSFER_WAIT_TIME)
    
    # Step 10: Get owned gifts
    gifts = get_owned_gifts()
    if not gifts:
        log_and_print("❌ Terminating: No gifts found to transfer", "ERROR")
        return
    
    # Step 11: Display gift list
    log_and_print("\nAvailable gifts:")
    for i, gift in enumerate(gifts, 1):
        gift_id = gift.get('owned_gift_id')
        gift_name = gift.get('gift', {}).get('base_name', 'Unknown')
        gift_full_name = gift.get('gift', {}).get('name', 'Unknown')
        gift_type = gift.get('type', 'Unknown')
        can_transfer = gift.get('can_be_transferred', False)
        transfer_cost = gift.get('transfer_star_count', 0)
        
        log_and_print(f"\n🎁 Gift {i}:")
        log_and_print(f"ID: {gift_id}")
        log_and_print(f"Name: {gift_name} ({gift_full_name})")
        log_and_print(f"Type: {gift_type}")
        log_and_print(f"Can be transferred: {'Yes' if can_transfer else 'No'}")
        log_and_print(f"Transfer cost: {transfer_cost} stars")
        log_and_print("-" * 30)
    
    # Step 12: Let user select a gift
    log_and_print(f"\nEnter the gift number to transfer (1-{len(gifts)}):")
    try:
        choice = int(input())
        if 1 <= choice <= len(gifts):
            selected_gift = gifts[choice - 1]
            gift_id = selected_gift.get('owned_gift_id')
            gift_name = selected_gift.get('gift', {}).get('base_name', 'Unknown')
            can_transfer = selected_gift.get('can_be_transferred', False)
            transfer_cost = selected_gift.get('transfer_star_count', STAR_COUNT)
            
            log_and_print(f"\nSelected gift: {gift_name} (ID: {gift_id})")
            
            # Step 13: Validate gift can be transferred
            if not can_transfer:
                log_and_print("❌ This gift cannot be transferred", "ERROR")
                return
            
            # Step 14: Check if transfer cost matches
            if transfer_cost > STAR_COUNT:
                log_and_print(f"❌ Terminating: Gift requires {transfer_cost} stars, but only {STAR_COUNT} were transferred", "ERROR")
                return
            
            # Step 15: Transfer gift
            transfer_gift(gift_id, TARGET_CHAT_ID, transfer_cost)
            
        else:
            log_and_print(f"❌ Invalid choice. Enter a number from 1 to {len(gifts)}", "ERROR")
    except ValueError:
        log_and_print("❌ Invalid input. Please enter a number", "ERROR")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Script execution completed. Check log file for details.")
        logger.info(f"Log file: {current_log_file}") 