# Telegram Gift Transfer Tool

This tool provides a web interface for transferring gifts using the Telegram Bot API. The application allows transferring stars from a business account to a bot and then using these stars to transfer gifts to users.

## Features

- Web interface for easy configuration
- Real-time console output
- Log management system
- Support for business bots and gift transfers

## Requirements

- Python 3.6+
- Flask
- Requests

## Local Development

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Run the application:
```
python app.py
```

3. Open your browser and navigate to: http://localhost:5000

## Deployment

### Deploying to Dokploy

1. Make sure your repository contains:
   - `requirements.txt` - Lists all Python dependencies
   - `Procfile` - Defines the startup command (`web: python app.py`)

2. Set up your Dokploy project and connect to this repository

3. The application will automatically use the PORT environment variable provided by the hosting platform

### Environment Settings

The application uses the following environment variables:

- `PORT` - The port on which the application will run (default: 5000)
- `DEBUG` - Set to "True" to enable debug mode (default: False)
- `LOG_LEVEL` - Set the logging level (default: INFO)

For production deployment, you can configure these in your hosting platform's environment settings.

### Using the Web Interface

1. Fill in the required fields:
   - Bot Token (from BotFather)
   - Business Connection ID
   - Target Chat ID
   - Star Count (default: 25)

2. Click "Run Script" to start the process

3. Monitor the console output in real-time

4. Download logs for record-keeping

## Important Notes

- The application requires a business bot to function properly
- Star transfers can only be performed by business bots
- The Telegram API does not provide a way to check bot star balance
- Logs are stored in the `logs` folder

## How It Works

1. User enters configuration details in the web form
2. The application creates a temporary configuration file
3. The Telegram gift transfer script is executed with this configuration
4. Real-time output is streamed to the web interface
5. Logs are saved for later reference

## Configuration

All settings are stored directly in the `telegram_gift_transfer.py` file or can be provided via a JSON configuration file. You can modify the following parameters:

```python
# Bot and API settings
BOT_TOKEN = 'YOUR_BOT_TOKEN'  # Your bot token from BotFather
BUSINESS_CONNECTION_ID = 'YOUR_BUSINESS_CONNECTION_ID'  # Business connection ID
TARGET_CHAT_ID = 123456789  # Chat ID to transfer gifts to

# Gift and star settings
STAR_COUNT = 25  # Number of stars to transfer

# API request settings
MAX_RETRIES = 3  # Maximum number of retries for API requests
RETRY_DELAY = 5  # Delay between retries in seconds
TRANSFER_WAIT_TIME = 60  # Wait time after star transfer in seconds
```

## Logging Configuration

The script uses a centralized logging system based on Python's built-in `logging` module. The logging configuration is defined in `logging_config.json`, which allows for easy customization of log levels, formats, and handlers.

### Default Configuration

The default logging configuration:
- Creates timestamped log files in the `logs` directory
- Displays informational messages in the console
- Logs detailed information (including debug messages) to the log file
- Uses appropriate color formatting for different message levels

### Customizing Logging

You can modify the `logging_config.json` file to:
- Change log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Adjust log formats
- Configure log rotation (size, backups)
- Add additional handlers (e.g., email notifications for errors)

```json
{
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "level": "INFO"  # Change to DEBUG for more verbose console output
        },
        "file": {
            "level": "DEBUG"  # Change to INFO to reduce log file size
        }
    }
}
```

## Script Process

The script will perform the following actions:
1. Check connection to the Telegram API
2. Validate the business connection ID
3. Verify that the bot is a business bot (terminates if not)
4. Validate the target chat
5. Check business account star balance (requires at least 2x the STAR_COUNT)
6. Transfer stars to the bot
7. Perform an additional star transfer for reliability
8. Wait for star transfers to process
9. Get a list of available gifts
10. Let you choose a gift to transfer
11. Validate gift transfer requirements
12. Attempt to transfer the selected gift

All actions and results will be recorded in a log file in the `logs` folder.

## Important Requirements

### Business Bot Requirement

This script strictly requires a business bot to function. If the bot is not a business bot, the script will terminate with detailed instructions on how to upgrade your bot. This is because:

- Gift transfers and star usage are only available for business bots
- In the API response to the `getMe` request, the `is_business_bot` parameter must be `true`
- Non-business bots cannot use stars for gift transfers, resulting in PAYMENT_REQUIRED errors

### Star Balance Requirements

The script now requires at least twice the amount of stars specified in `STAR_COUNT` to be available in your business account. This ensures there are enough stars for both the initial and additional star transfer operations.

## Known Issues

### No Endpoint for Checking Bot Star Balance

It's important to note that the Telegram Bot API does **not have** a way to check the bot's star balance. This makes it impossible to programmatically determine how many stars are available to the bot after a transfer.

The `transferBusinessAccountStars` request successfully debits stars from the business account, but it's unknown if they actually go into the bot's pool if it's not a business bot.

### Solving Common Problems

If you encounter errors when using the script:

1. **PAYMENT_REQUIRED Error**
   - Ensure your bot is a business bot through @BotFather
   - Create a new bot with the "Business Bot" type if necessary
   - Update BOT_TOKEN in the script with the new token

2. **Invalid Business Connection ID**
   - Verify your BUSINESS_CONNECTION_ID in your Telegram business account settings
   - Make sure the business connection is properly linked to your bot

3. **Chat Not Found Error**
   - Verify that TARGET_CHAT_ID is correct
   - Ensure the user has interacted with the bot at least once

4. **Permission Errors**
   - Make sure the bot has all necessary permissions
   - Check that the user hasn't blocked the bot

## Logging

The script creates detailed logs of all actions and API requests in the `logs` folder. These logs can be useful for diagnosing problems and sending to Telegram support.

Log files follow the naming pattern `gift_transfer_log_YYYYMMDD_HHMMSS.log` with a timestamp to prevent overwriting. The log includes:

- Information messages about script execution
- Warnings about potential issues
- Error messages with detailed explanations
- Debug information including API request/response data

## Enhanced Reliability Features

The latest version includes several reliability enhancements:

1. **Automatic Double Star Transfer** - Automatically performs a second star transfer to increase reliability
2. **Extended Wait Time** - Waits 60 seconds after transfers to ensure stars are processed
3. **Strict Validation** - Validates the business connection, business bot status, and gift transfer requirements
4. **Detailed Error Handling** - Provides specific guidance for different types of errors
5. **Gift Cost Validation** - Ensures the gift's transfer cost doesn't exceed the transferred stars
6. **Centralized Logging** - Uses Python's logging module for more flexible and consistent logging
7. **Web Interface** - Provides a user-friendly interface for running the script and managing logs

## Author

This script is an improved version with enhanced diagnostic and error handling capabilities for working with the Telegram Gift API. 