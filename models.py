from flask_sqlalchemy import SQLAlchemy
import uuid

db = SQLAlchemy()

class CAPTCHA(db.Model):
    """Model to represent a CAPTCHA instance."""
    id = db.Column(db.String(36), primary_key=True)
    correct_x = db.Column(db.Integer, nullable=False)
    correct_y = db.Column(db.Integer, nullable=False)

    def __init__(self, correct_x, correct_y):
        self.id = str(uuid.uuid4())
        self.correct_x = correct_x
        self.correct_y = correct_y
