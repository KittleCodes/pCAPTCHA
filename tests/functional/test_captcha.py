import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from main import app

def test_index_page():
    with app.test_client() as test_client:
        response = test_client.get('/')
        
        assert response.status_code == 200
        assert b'/pCaptcha.js' in response.data
        assert b'captchaContainer' in response.data
  
def test_javascript_file():
    with app.test_client() as test_client:
        response = test_client.get('/pCaptcha.js')
        
        assert response.status_code == 200
        assert b'captchaContainer' in response.data

def test_captcha_generation():
    with app.test_client() as test_client:
        response = test_client.get('/generate_puzzle_piece')
        
        assert response.status_code == 200
        assert b'"success":true' in response.data
        assert b'captcha_id' in response.data
        assert b'image' in response.data

def test_position_check():
    with app.test_client() as test_client:
        response = test_client.post('/check_position', json={'captcha_id':'captchaId','x':'20','y':'30','mouse_movements':{}})
        
        assert response.status_code == 404
        assert b'"success":false' in response.data
        assert b'"message":"CAPTCHA not found"' in response.data

def test_captcha_verification():
    with app.test_client() as test_client:
        response = test_client.post('/verify_captcha', json={'token':'0','ip_address':'0.0.0.0','user_agent':''})
        
        assert response.status_code == 200
        assert b'"success":false' in response.data
        assert b'"message":"Invalid token!"' in response.data