from flask_sqlalchemy import SQLAlchemy
import uuid
import datetime
from sqlalchemy import event
from sqlalchemy_json import mutable_json_type
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class CAPTCHA(db.Model):
    """Model to represent a CAPTCHA instance."""
    id = db.Column(db.String(36), primary_key=True)
    correct_x = db.Column(db.Integer, nullable=False)
    correct_y = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, correct_x, correct_y):
        self.id = str(uuid.uuid4())
        self.correct_x = correct_x
        self.correct_y = correct_y 
        
class CAPTCHA_Analytics(db.Model):
    """Model to store analytics data for CAPTCHA generation and solving."""
    session_id = db.Column(db.String(36), primary_key=True)
    captchas_generated = db.Column(db.Integer, default=0)
    captchas_solved = db.Column(db.Integer, default=0)
    captchas_failed = db.Column(db.Integer, default=0)
    attempts = db.Column(mutable_json_type(dbtype=JSONB, nested=True), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

def delete_old_captchas(session):
    """Delete CAPTCHAs older than a certain cutoff time."""
    # Define the cutoff time to be older than 5 minutes
    cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    # Delete records older than the cutoff time
    session.query(CAPTCHA).filter(CAPTCHA.created_at < cutoff_time).delete(synchronize_session=False)

# Use the event listener to trigger the cleanup before flushing
@event.listens_for(db.Session, 'before_flush')
def before_flush(session, flush_context, instances):
    delete_old_captchas(session)
