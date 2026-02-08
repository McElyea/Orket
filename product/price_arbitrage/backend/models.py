from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Target(Base):
    __tablename__ = "targets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    url = Column(String)
    selector_type = Column(String) # 'xpath', 'css', 'id', 'aria'
    selector_value = Column(String)
    
    # Arbitrage Logic
    market_baseline = Column(Float, nullable=True) # Manually set or locked from first poll
    threshold_percent = Column(Float, default=20.0) # e.g. 20%
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_polled_at = Column(DateTime, nullable=True)
    
    history = relationship("PriceHistory", back_populates="target")

class PriceHistory(Base):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id"))
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    raw_value = Column(String) # Original string before cleaning
    
    target = relationship("Target", back_populates="history")

class GlobalSettings(Base):
    __tablename__ = "global_settings"
    id = Column(Integer, primary_key=True, index=True)
    poll_interval_min = Column(Integer, default=5)
    jitter_min = Column(Integer, default=2)
    user_agent_rotation = Column(JSON) # List of UAs
    proxy_url = Column(String, nullable=True)
