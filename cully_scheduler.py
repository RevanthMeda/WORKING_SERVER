#!/usr/bin/env python3
"""
Scheduler for automatic Cully statistics synchronization
"""
import schedule
import time
import logging
import sys
import os
from datetime import datetime

# Add the server directory to Python path
server_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, server_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/cully_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def sync_cully_statistics():
    """Run the Cully statistics synchronization"""
    try:
        from flask import Flask
        from models import db, CullyStatistics, init_db
        
        # Create a minimal Flask app for the sync task
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/database.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SECRET_KEY'] = 'sync_task_key'
        app.config['BASE_DIR'] = server_dir
        
        # Initialize database within app context
        with app.app_context():
            db.init_app(app)
            
            logger.info("🔄 Starting Cully statistics synchronization...")
            
            # Fetch and update statistics
            success = CullyStatistics.fetch_and_update_from_cully()
            
            if success:
                # Get updated statistics
                stats = CullyStatistics.get_current_statistics()
                logger.info(f"✅ Successfully synced Cully statistics:")
                logger.info(f"   📊 Instruments: {stats['instruments']}")
                logger.info(f"   👷 Engineers: {stats['engineers']}")
                logger.info(f"   🎓 Experience: {stats['experience']} years")
                logger.info(f"   🏭 Water Plants: {stats['plants']}")
                logger.info(f"   🕒 Last Updated: {stats['last_updated']}")
            else:
                logger.warning("⚠️ Failed to sync Cully statistics, using cached data")
                stats = CullyStatistics.get_current_statistics()
                logger.info(f"📊 Current cached stats: {stats}")
                
    except Exception as e:
        logger.error(f"❌ Error during Cully statistics sync: {e}")
        import traceback
        logger.error(traceback.format_exc())

def run_scheduler():
    """Run the background scheduler"""
    logger.info("🚀 Starting Cully Statistics Scheduler...")
    
    # Schedule daily sync at 6 AM
    schedule.every().day.at("06:00").do(sync_cully_statistics)
    
    # Schedule sync every 6 hours for more frequent updates
    schedule.every(6).hours.do(sync_cully_statistics)
    
    # Run initial sync
    logger.info("🔄 Running initial sync...")
    sync_cully_statistics()
    
    logger.info("⏰ Scheduler started. Next sync times:")
    for job in schedule.jobs:
        logger.info(f"   📅 {job}")
    
    # Keep the scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("⚠️ Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Run the scheduler
    run_scheduler()