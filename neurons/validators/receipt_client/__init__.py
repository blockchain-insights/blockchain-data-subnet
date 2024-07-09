import requests
from neurons import logger

class ReceiptClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def get_token_usages(self, hotkey: str = None):
        try:
            url = f'{self.base_url}/api/v1/receipts'
            if hotkey is not None:
                url += f'/{hotkey}'
            response = requests.get(url, timeout = 60)
            response.raise_for_status()
            return response.json()
        except requests.ConnectionError as e:
            logger.error(f"Connection error: {e}")
        except requests.Timeout as e:
            logger.error(f"Request timeout: {e}")
        except requests.RequestException as e:
            logger.error(f"Failed to query: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        return None