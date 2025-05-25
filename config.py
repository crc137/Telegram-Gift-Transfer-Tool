from pydantic import BaseModel, PositiveInt, validator
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

class AppConfig(BaseModel):
    BOT_TOKEN: str
    BUSINESS_CONNECTION_ID: str
    TARGET_CHAT_ID: PositiveInt
    STAR_COUNT: PositiveInt = 25
    MAX_RETRIES: PositiveInt = 3
    RETRY_DELAY: PositiveInt = 5
    TRANSFER_WAIT_TIME: PositiveInt = 60
    BYPASS_BUSINESS_CHECK: bool = False
    ENABLE_REDUNDANT_TRANSFER: bool = False  # Disabled by default to avoid unnecessary API calls
    LOG_DIR: str = "logs"
    API_KEY: Optional[str] = None

    @validator('BOT_TOKEN', 'BUSINESS_CONNECTION_ID')
    def check_non_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v

    @classmethod
    def load(cls, config_file: Optional[str] = None) -> 'AppConfig':
        """
        Load configuration from environment variables and config file.
        
        Args:
            config_file: Optional path to a JSON configuration file
            
        Returns:
            AppConfig: Validated configuration object
        """
        defaults = {
            "BOT_TOKEN": os.getenv("BOT_TOKEN", "0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"),
            "BUSINESS_CONNECTION_ID": os.getenv("BUSINESS_CONNECTION_ID", "0000000000"),
            "TARGET_CHAT_ID": int(os.getenv("TARGET_CHAT_ID", "0") or 0),
            "STAR_COUNT": int(os.getenv("STAR_COUNT", "25")),
            "MAX_RETRIES": int(os.getenv("MAX_RETRIES", "3")),
            "RETRY_DELAY": int(os.getenv("RETRY_DELAY", "5")),
            "TRANSFER_WAIT_TIME": int(os.getenv("TRANSFER_WAIT_TIME", "60")),
            "BYPASS_BUSINESS_CHECK": os.getenv("BYPASS_BUSINESS_CHECK", "False").lower() in ("true", "yes", "1"),
            "ENABLE_REDUNDANT_TRANSFER": os.getenv("ENABLE_REDUNDANT_TRANSFER", "False").lower() in ("true", "yes", "1"),
            "LOG_DIR": os.getenv("LOG_DIR", "logs"),
            "API_KEY": os.getenv("API_KEY")
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    defaults.update(file_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading configuration file: {e}")
                
        return cls(**defaults)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary, excluding None values and API_KEY"""
        result = self.dict(exclude_none=True)
        if 'API_KEY' in result:
            del result['API_KEY']  # Don't include API key in config files
        return result 