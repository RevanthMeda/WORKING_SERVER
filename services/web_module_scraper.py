"""
Web-based Module Specification Scraper
Automatically fetches module details from manufacturer websites and technical databases
when AI lookup fails. Eliminates need for manual entry.
"""

from flask import current_app
import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class WebModuleScraper:
    """Automatically fetch module specs from internet sources"""
    
    def __init__(self):
        self.timeout = 10
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_module_specs(self, company: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Try multiple internet sources to fetch module specifications
        Returns module specs dict or None if all sources fail
        """
        logger.info(f"Starting web scrape for {company} {model}")
        
        # Try sources in order
        sources = [
            self._fetch_from_datasheets,
            self._fetch_from_alibaba,
            self._fetch_from_product_pages,
            self._fetch_from_automation_sites
        ]
        
        for source_func in sources:
            try:
                result = source_func(company, model)
                if result:
                    logger.info(f"Successfully fetched specs from {source_func.__name__}: {company} {model}")
                    return result
            except Exception as e:
                logger.debug(f"{source_func.__name__} failed: {e}")
        
        logger.warning(f"Web scrape failed for {company} {model} - all sources exhausted")
        return None
    
    def _fetch_from_datasheets(self, company: str, model: str) -> Optional[Dict]:
        """Fetch from datasheet sites like datasheetspdf.com"""
        try:
            search_query = f"{company} {model} datasheet"
            url = f"https://www.datasheetspdf.com/search.php?q={search_query}"
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                specs = self._parse_datasheet_page(soup, company, model)
                if specs:
                    return specs
        except Exception as e:
            logger.debug(f"Datasheet fetch failed: {e}")
        return None
    
    def _fetch_from_alibaba(self, company: str, model: str) -> Optional[Dict]:
        """Fetch from Alibaba product listings"""
        try:
            search_query = f"{company}+{model}+module+specification"
            url = f"https://www.alibaba.com/trade/search?SearchText={search_query}"
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                specs = self._parse_alibaba_product(soup, company, model)
                if specs:
                    return specs
        except Exception as e:
            logger.debug(f"Alibaba fetch failed: {e}")
        return None
    
    def _fetch_from_product_pages(self, company: str, model: str) -> Optional[Dict]:
        """Fetch from manufacturer product pages"""
        try:
            # Common patterns for manufacturer websites
            urls_to_try = [
                f"https://www.{company.lower()}.com/products/{model.lower()}",
                f"https://www.{company.lower()}.com/en/products/{model.lower()}",
                f"https://products.{company.lower()}.com/{model.lower()}",
            ]
            
            for url in urls_to_try:
                try:
                    response = requests.get(url, headers=self.headers, timeout=self.timeout)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        specs = self._parse_product_page(soup, company, model)
                        if specs:
                            return specs
                except:
                    continue
        except Exception as e:
            logger.debug(f"Product page fetch failed: {e}")
        return None
    
    def _fetch_from_automation_sites(self, company: str, model: str) -> Optional[Dict]:
        """Fetch from industrial automation resource sites"""
        try:
            urls = [
                f"https://www.alliedelec.com/search/products/{company}-{model}",
                f"https://www.mouser.com/ProductDetail/{model}",
                f"https://industrial.baseddb.com/search/{company}/{model}",
            ]
            
            for url in urls:
                try:
                    response = requests.get(url, headers=self.headers, timeout=self.timeout)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        specs = self._extract_io_specs(soup)
                        if specs:
                            specs['description'] = f"{company} {model}"
                            return specs
                except:
                    continue
        except Exception as e:
            logger.debug(f"Automation site fetch failed: {e}")
        return None
    
    def _parse_datasheet_page(self, soup: BeautifulSoup, company: str, model: str) -> Optional[Dict]:
        """Parse datasheet page to extract I/O specs"""
        specs = self._extract_io_specs(soup)
        if specs:
            specs['description'] = f"{company} {model} - from datasheet"
            return specs
        return None
    
    def _parse_alibaba_product(self, soup: BeautifulSoup, company: str, model: str) -> Optional[Dict]:
        """Parse Alibaba product page"""
        specs = self._extract_io_specs(soup)
        if specs:
            specs['description'] = f"{company} {model} - from Alibaba"
            return specs
        return None
    
    def _parse_product_page(self, soup: BeautifulSoup, company: str, model: str) -> Optional[Dict]:
        """Parse manufacturer product page"""
        specs = self._extract_io_specs(soup)
        if specs:
            specs['description'] = f"{company} {model} - from manufacturer"
            return specs
        return None
    
    def _extract_io_specs(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract I/O specifications from any HTML page
        Looks for patterns like "8 Digital Inputs", "16 Outputs", etc.
        """
        try:
            text = soup.get_text().lower()
            
            # Extract I/O counts using regex patterns
            di_patterns = [
                r'(\d+)\s*(?:channel)?\s*digital\s*input',
                r'di[:\s]+(\d+)',
                r'(\d+)\s*(?:ch)?\s*(?:di|din)',
            ]
            
            do_patterns = [
                r'(\d+)\s*(?:channel)?\s*digital\s*output',
                r'do[:\s]+(\d+)',
                r'(\d+)\s*(?:ch)?\s*(?:do|dout)',
            ]
            
            ai_patterns = [
                r'(\d+)\s*(?:channel)?\s*analog\s*input',
                r'ai[:\s]+(\d+)',
                r'(\d+)\s*(?:ch)?\s*(?:ai|ain)',
            ]
            
            ao_patterns = [
                r'(\d+)\s*(?:channel)?\s*analog\s*output',
                r'ao[:\s]+(\d+)',
                r'(\d+)\s*(?:ch)?\s*(?:ao|aout)',
            ]
            
            digital_inputs = self._extract_count(text, di_patterns)
            digital_outputs = self._extract_count(text, do_patterns)
            analog_inputs = self._extract_count(text, ai_patterns)
            analog_outputs = self._extract_count(text, ao_patterns)
            
            # Only return if we found at least one I/O type
            if digital_inputs + digital_outputs + analog_inputs + analog_outputs > 0:
                return {
                    'digital_inputs': digital_inputs,
                    'digital_outputs': digital_outputs,
                    'analog_inputs': analog_inputs,
                    'analog_outputs': analog_outputs,
                    'voltage_range': self._extract_voltage(text),
                    'current_range': self._extract_current(text),
                    'description': 'Auto-discovered from web'
                }
        except Exception as e:
            logger.debug(f"IO extraction failed: {e}")
        
        return None
    
    def _extract_count(self, text: str, patterns: list) -> int:
        """Extract count from text using multiple patterns"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except:
                    pass
        return 0
    
    def _extract_voltage(self, text: str) -> Optional[str]:
        """Extract voltage rating from text"""
        patterns = [
            r'(24\s*vdc)',
            r'(12\s*vdc)',
            r'(110\s*vac)',
            r'(220\s*vac)',
            r'(\d+\s*(?:vdc|vac|v))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_current(self, text: str) -> Optional[str]:
        """Extract current rating from text"""
        patterns = [
            r'(4[- ]?20\s*ma)',
            r'(0[- ]?10\s*v)',
            r'(\d+\s*ma)',
            r'(\d+\.\d+\s*a)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


def get_module_from_web(company: str, model: str) -> Optional[Dict[str, Any]]:
    """
    Public function to fetch module specs from web
    Used when AI fails and automatic internet fallback is needed
    """
    scraper = WebModuleScraper()
    return scraper.fetch_module_specs(company, model)
