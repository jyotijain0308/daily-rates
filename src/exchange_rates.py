"""
Exchange Rate Service - Fetch and cache currency exchange rates
"""
import requests
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Fetch and cache exchange rates from API"""
    
    CACHE_FILE = "data/.exchange_rate_cache.json"
    DEFAULT_CACHE_DURATION = timedelta(hours=24)
    
    def __init__(self, api_url: str = "https://api.exchangerate-api.com/v4/latest",
                 cache_duration: timedelta = None):
        self.api_url = api_url
        self.cache_duration = cache_duration or self.DEFAULT_CACHE_DURATION
        Path(self.CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    def get_exchange_rates(self, base_currency: str = "USD", 
                          target_currencies: Optional[list] = None) -> Dict[str, float]:
        """
        Get exchange rates for target currencies
        Returns dict like {'INR': 83.5, 'EUR': 0.92, ...}
        """
        if target_currencies is None:
            target_currencies = ['INR']
        
        # Try to use cached data first
        cached_rates = self._get_cached_rates(base_currency, target_currencies)
        if cached_rates:
            logger.info(f"Using cached exchange rates for {base_currency}")
            return cached_rates
        
        # Fetch from API if cache miss
        try:
            rates = self._fetch_from_api(base_currency, target_currencies)
            self._cache_rates(base_currency, rates)
            return rates
        except Exception as e:
            logger.error(f"Error fetching exchange rates: {str(e)}")
            # Return cached rates even if expired, or raise if no cache
            cached_rates = self._get_cached_rates(base_currency, target_currencies, ignore_expiry=True)
            if cached_rates:
                logger.warning("Using expired cached rates due to API error")
                return cached_rates
            raise
    
    def _fetch_from_api(self, base_currency: str, target_currencies: list) -> Dict[str, float]:
        """Fetch exchange rates from the API"""
        try:
            url = f"{self.api_url}/{base_currency}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            rates = data.get('rates', {})
            
            # Filter to only requested currencies
            result = {curr: rates.get(curr) for curr in target_currencies if curr in rates}
            logger.info(f"Fetched exchange rates from API: {result}")
            return result
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    def _get_cached_rates(self, base_currency: str, target_currencies: list,
                         ignore_expiry: bool = False) -> Optional[Dict[str, float]]:
        """Retrieve cached exchange rates if valid"""
        try:
            if not Path(self.CACHE_FILE).exists():
                return None
            
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)
            
            cache_key = f"{base_currency}_rates"
            if cache_key not in cache:
                return None
            
            cache_entry = cache[cache_key]
            
            # Check cache expiry
            if not ignore_expiry:
                cached_time = datetime.fromisoformat(cache_entry['timestamp'])
                if datetime.now() - cached_time > self.cache_duration:
                    logger.debug(f"Cache expired for {base_currency}")
                    return None
            
            rates = cache_entry['rates']
            result = {curr: rates.get(curr) for curr in target_currencies if curr in rates}
            return result if result else None
        except Exception as e:
            logger.debug(f"Error reading cache: {str(e)}")
            return None
    
    def _cache_rates(self, base_currency: str, rates: Dict[str, float]):
        """Store exchange rates in cache"""
        try:
            cache = {}
            if Path(self.CACHE_FILE).exists():
                with open(self.CACHE_FILE, 'r') as f:
                    cache = json.load(f)
            
            cache_key = f"{base_currency}_rates"
            cache[cache_key] = {
                'timestamp': datetime.now().isoformat(),
                'rates': rates
            }
            
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)
            logger.debug(f"Cached exchange rates for {base_currency}")
        except Exception as e:
            logger.warning(f"Error caching rates: {str(e)}")
    
    def get_inr_rates(self, currencies: Optional[list] = None) -> Dict[str, float]:
        """Get exchange rates to INR (convenience method)"""
        if currencies is None:
            currencies = ['USD', 'EUR', 'GBP', 'JPY']
        
        result = {}
        for currency in currencies:
            try:
                rates = self.get_exchange_rates(base_currency=currency, 
                                               target_currencies=['INR'])
                if rates.get('INR'):
                    result[currency] = rates['INR']
            except Exception as e:
                logger.warning(f"Could not fetch rate for {currency}: {str(e)}")
        
        return result
    
    def clear_cache(self):
        """Clear the exchange rate cache"""
        try:
            if Path(self.CACHE_FILE).exists():
                Path(self.CACHE_FILE).unlink()
                logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
