from flask_sqlalchemy import SQLAlchemy
import uuid
import datetime
from sqlalchemy import event

db = SQLAlchemy()

class CAPTCHA(db.Model):
    """Model to represent a CAPTCHA instance."""
    id = db.Column(db.String(36), primary_key=True)
    correct_x = db.Column(db.Integer, nullable=False)
    correct_y = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)

class CAPTCHA_Attempt(db.Model):
    """Model to store CAPTCHA solving attempts."""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False)
    captcha_id = db.Column(db.String(36), nullable=False)
    presented_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    time_taken = db.Column(db.Float, default=0.0)
    success = db.Column(db.Boolean, default=False)
    mouse_movements = db.Column(db.JSON, nullable=True)

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
