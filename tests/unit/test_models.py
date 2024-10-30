import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
import datetime
from models import CAPTCHA, CAPTCHA_Analytics, CAPTCHA_Attempt

def test_new_captcha():
    """
    GIVEN a CAPTCHA model
    WHEN a new CAPTCHA is created
    THEN check the correct_x and correct_y fields are defined correctly
    """
    captcha = CAPTCHA(correct_x = 48, correct_y = 153)
    assert captcha.correct_x == 48
    assert captcha.correct_y == 153

def test_new_captcha_analytics():
    """
    GIVEN a CAPTCHA_Analytics model
    WHEN a new Session is created
    THEN check the captchas_generated, captchas_solved, and captchas_failed fields are defined correctly
    """
    captcha_analytics = CAPTCHA_Analytics(captchas_generated = 4, captchas_solved = 1, captchas_failed = 3)
    assert captcha_analytics.captchas_generated == 4
    assert captcha_analytics.captchas_solved == 1
    assert captcha_analytics.captchas_failed == 3

def test_new_captcha_attempt():
    """
    GIVEN a CAPTCHA_Attempt model
    WHEN a new Attempt is created
    THEN check the captcha_id, presented_at, completed_at, time_taken, success, and mouse_movements fields are defined correctly
    """
    captcha_id = "123e4567-e89b-12d3-a456-426614174111"
    presented_at = datetime.datetime.now(datetime.timezone.utc)
    completed_at = presented_at + datetime.timedelta(seconds=31.68)
    time_taken = (completed_at - presented_at).total_seconds()
    success = True
    mouse_movements = [{"x": 121, "y": 224}, {"x": 151, "y": 326}]

    captcha_attempt = CAPTCHA_Attempt(
        captcha_id=captcha_id,
        presented_at=presented_at,
        completed_at=completed_at,
        time_taken=time_taken,
        success=success,
        mouse_movements=mouse_movements
    )

    assert captcha_attempt.captcha_id == captcha_id
    assert captcha_attempt.presented_at == presented_at
    assert captcha_attempt.completed_at == completed_at
    assert captcha_attempt.time_taken == time_taken
    assert captcha_attempt.success == success
    assert captcha_attempt.mouse_movements == mouse_movements
