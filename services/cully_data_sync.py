"""
Cully Website Data Synchronization Service
Automatically fetches and updates statistics from Cully.ie website
"""

import re
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
from bs4 import BeautifulSoup
from flask import current_app
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from database import db


class CullyStatistics(db.Model):
    """Model to store Cully website statistics"""
    __tablename__ = 'cully_statistics'
    
    id = Column(Integer, primary_key=True)
    instruments_count = Column(String(10), default='22k')
    engineers_count = Column(String(10), default='46')
    experience_years = Column(String(10), default='600+')
    water_plants = Column(String(10), default='250')
    last_updated = Column(DateTime, default=datetime.utcnow)
    fetch_successful = Column(Boolean, default=True)
    error_message = Column(String(500), nullable=True)
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for easy template rendering"""
        return {
            'instruments': self.instruments_count,
            'engineers': self.engineers_count,
            'experience': self.experience_years,
            'plants': self.water_plants,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }


class CullyDataSyncService:
    """Service to synchronize data from Cully.ie website"""
    
    CULLY_URL = "https://www.cully.ie/"
    UPDATE_INTERVAL_HOURS = 24  # Update once per day
    
    @staticmethod
    def extract_statistics_from_content(html_content: str) -> Dict[str, str]:
        """Extract statistics from Cully website HTML content"""
        try:
            # Parse HTML content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Default values in case extraction fails
            stats = {
                'instruments': '22k',
                'engineers': '46', 
                'experience': '600+',
                'plants': '250'
            }
            
            # Look for statistics patterns in the text
            text_content = soup.get_text()
            
            # Extract numbers using regex patterns
            # Pattern for "22k" or "22K" followed by text about instruments
            instruments_match = re.search(r'(\d+k?)\s*(?:instruments|Instruments)', text_content, re.IGNORECASE)
            if instruments_match:
                stats['instruments'] = instruments_match.group(1)
            
            # Pattern for engineers
            engineers_match = re.search(r'(\d+)\s*(?:service engineers|Service engineers|engineers)', text_content, re.IGNORECASE)
            if engineers_match:
                stats['engineers'] = engineers_match.group(1)
                
            # Pattern for experience years  
            experience_match = re.search(r'(\d+\+?)\s*(?:years|Years).*(?:experience|Experience)', text_content, re.IGNORECASE)
            if experience_match:
                stats['experience'] = experience_match.group(1)
                
            # Pattern for water plants
            plants_match = re.search(r'(\d+)\s*(?:automated water plants|Automated Water plants|water plants)', text_content, re.IGNORECASE)
            if plants_match:
                stats['plants'] = plants_match.group(1)
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error extracting statistics: {str(e)}")
            # Return default values if extraction fails
            return {
                'instruments': '22k',
                'engineers': '46',
                'experience': '600+', 
                'plants': '250'
            }
    
    @staticmethod
    def fetch_cully_statistics() -> Optional[Dict[str, str]]:
        """Fetch current statistics from Cully.ie website"""
        try:
            response = requests.get(
                CullyDataSyncService.CULLY_URL,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            
            stats = CullyDataSyncService.extract_statistics_from_content(response.text)
            current_app.logger.info(f"Successfully fetched Cully statistics: {stats}")
            return stats
            
        except requests.RequestException as e:
            current_app.logger.error(f"Error fetching Cully website: {str(e)}")
            return None
        except Exception as e:
            current_app.logger.error(f"Unexpected error in fetch_cully_statistics: {str(e)}")
            return None
    
    @staticmethod
    def update_statistics() -> bool:
        """Update statistics in database from Cully website"""
        try:
            stats = CullyDataSyncService.fetch_cully_statistics()
            
            if stats is None:
                # Update with error status but keep existing data
                existing = CullyStatistics.query.first()
                if existing:
                    existing.fetch_successful = False
                    existing.error_message = "Failed to fetch from Cully.ie"
                    existing.last_updated = datetime.utcnow()
                else:
                    # Create with default values
                    new_stats = CullyStatistics(
                        fetch_successful=False,
                        error_message="Failed to fetch from Cully.ie"
                    )
                    db.session.add(new_stats)
                
                db.session.commit()
                return False
            
            # Update or create statistics record
            existing = CullyStatistics.query.first()
            if existing:
                existing.instruments_count = stats['instruments']
                existing.engineers_count = stats['engineers'] 
                existing.experience_years = stats['experience']
                existing.water_plants = stats['plants']
                existing.last_updated = datetime.utcnow()
                existing.fetch_successful = True
                existing.error_message = None
            else:
                new_stats = CullyStatistics(
                    instruments_count=stats['instruments'],
                    engineers_count=stats['engineers'],
                    experience_years=stats['experience'],
                    water_plants=stats['plants'],
                    fetch_successful=True
                )
                db.session.add(new_stats)
            
            db.session.commit()
            current_app.logger.info("Successfully updated Cully statistics in database")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error updating statistics: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_current_statistics() -> Dict[str, str]:
        """Get current statistics from database"""
        try:
            stats_record = CullyStatistics.query.first()
            if stats_record:
                return stats_record.to_dict()
            else:
                # Return defaults if no record exists
                return {
                    'instruments': '22k',
                    'engineers': '46',
                    'experience': '600+',
                    'plants': '250',
                    'last_updated': None
                }
        except Exception as e:
            current_app.logger.error(f"Error getting statistics: {str(e)}")
            return {
                'instruments': '22k',
                'engineers': '46', 
                'experience': '600+',
                'plants': '250',
                'last_updated': None
            }
    
    @staticmethod
    def should_update() -> bool:
        """Check if statistics should be updated based on last update time"""
        try:
            stats_record = CullyStatistics.query.first()
            if not stats_record or not stats_record.last_updated:
                return True
                
            time_since_update = datetime.utcnow() - stats_record.last_updated
            return time_since_update > timedelta(hours=CullyDataSyncService.UPDATE_INTERVAL_HOURS)
            
        except Exception:
            return True


def init_cully_statistics():
    """Initialize Cully statistics on first run"""
    try:
        if not CullyStatistics.query.first():
            initial_stats = CullyStatistics()
            db.session.add(initial_stats)
            db.session.commit()
            current_app.logger.info("Initialized Cully statistics with default values")
    except Exception as e:
        current_app.logger.error(f"Error initializing Cully statistics: {str(e)}")
        db.session.rollback()