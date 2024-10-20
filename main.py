import os
import random
import datetime
import jwt
import requests
import random
import uuid
from io import BytesIO
from flask import Flask, jsonify, request, Response, session
from PIL import Image, ImageDraw, ImageFilter
from models import db, CAPTCHA, CAPTCHA_Analytics

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///captchas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Change both of these and keep them secure
app.secret_key = 'your_secret_key' # Secret key for the Flask app
SECRET_KEY = 'your_secret_key' # Secret key for JWT encoding/decoding

# List of neon colors for the puzzle piece
neon_colors = [
    (255, 0, 0, 200),     # Neon Red
    (0, 255, 0, 200),     # Neon Green
    (0, 0, 255, 200),     # Neon Blue
    (255, 255, 0, 200),   # Neon Yellow
    (255, 0, 255, 200),   # Neon Pink
    (0, 255, 255, 200),   # Neon Cyan
    (255, 165, 0, 200),   # Neon Orange
    (255, 20, 147, 200),  # Neon Hot Pink
    (191, 255, 0, 200),   # Neon Lime
    (57, 255, 20, 200),   # Neon Green 2
    (255, 105, 180, 200), # Neon Hot Pink 2
    (127, 255, 0, 200),   # Neon Chartreuse
    (0, 191, 255, 200),   # Neon Sky Blue
    (255, 69, 0, 200),    # Neon Orange Red
    (255, 0, 127, 200),   # Neon Deep Pink
    (199, 21, 133, 200),  # Neon Medium Violet Red
    (32, 178, 170, 200),  # Neon Light Sea Green
    (173, 255, 47, 200),  # Neon Green Yellow
    (100, 149, 237, 200), # Neon Cornflower Blue
    (0, 255, 127, 200),   # Neon Spring Green
    (220, 20, 60, 200),   # Neon Crimson
    (148, 0, 211, 200),   # Neon Dark Violet
    (255, 215, 0, 200),   # Neon Gold
    (238, 130, 238, 200), # Neon Violet
    (64, 224, 208, 200),  # Neon Turquoise
    (144, 238, 144, 200), # Neon Light Green
    (186, 85, 211, 200),  # Neon Medium Orchid
    (0, 206, 209, 200),   # Neon Dark Turquoise
    (123, 104, 238, 200), # Neon Medium Slate Blue
    (255, 140, 0, 200)    # Neon Dark Orange
]

# Initialize CAPTCHA Analytics if the session is new
def init_captcha_analytics():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        analytics = CAPTCHA_Analytics(session_id=session['session_id'])
        db.session.add(analytics)
        db.session.commit()

# Example usage
@app.route('/')
def index():
    """Render the index page with the pCAPTCHA."""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>pCAPTCHA</title>
</head>
<body>
    <div id="captchaContainer"></div>
    <script src="/pCaptcha.js"></script>
</body>
</html>
'''

# Return the dynamic pCaptcha.js file
@app.route('/pCaptcha.js', methods=['GET'])
def pCaptcha_js():
    """Serve the dynamic pCaptcha.js file."""
    # Initialize analytics on script load
    init_captcha_analytics()
    base_url = request.url_root
    js_content = f'''
(function() {{
    const container = document.getElementById('captchaContainer');
    const button = document.createElement('button');
    button.innerText = 'Click to verify';
    button.style.backgroundColor = '#4285f4'; 
    button.style.color = 'white';
    button.style.border = 'none';
    button.style.padding = '10px 20px';
    button.style.cursor = 'pointer';
    button.style.borderRadius = '5px';
    container.appendChild(button);

    const canvas = document.createElement('canvas');
    canvas.id = 'captchaCanvas';
    canvas.width = 250;  
    canvas.height = 250; 
    canvas.style.border = '1px solid #ccc';
    canvas.style.display = 'none'; 
    container.appendChild(canvas);

    let captchaId = null;
    const pieceSize = 50; 
    let isDragging = false;
    let draggablePiecePosition = {{ x: 0, y: 0 }};
    let mouseMovement = [];  // Array to store mouse movements with timestamps
    let backgroundImage = new Image();

    async function generatePuzzlePiece() {{
        const response = await fetch('{base_url}generate_puzzle_piece', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }}
        }});
        const data = await response.json();
        if (data.success) {{
            captchaId = data.captcha_id;
            backgroundImage.src = data.image;
            backgroundImage.onload = drawCanvas;
            canvas.style.display = 'block'; 
        }} else {{
            console.error(data.message);
        }}
    }}

    function drawCanvas() {{
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(backgroundImage, 0, 0, canvas.width, canvas.height);
        drawDraggablePiece(draggablePiecePosition.x, draggablePiecePosition.y);
    }}

    function drawDraggablePiece(x, y) {{
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'rgba(0, 255, 0, 1)'; 
        ctx.fillRect(x, y, pieceSize, pieceSize);
        ctx.strokeStyle = 'black';
        ctx.strokeRect(x, y, pieceSize, pieceSize);
    }}

    button.onclick = function() {{
        generatePuzzlePiece(); 
    }};

    canvas.onmousedown = function(event) {{
        const mouseX = event.offsetX;
        const mouseY = event.offsetY;
        const isInPiece = (mouseX >= draggablePiecePosition.x && mouseX <= draggablePiecePosition.x + pieceSize &&
                           mouseY >= draggablePiecePosition.y && mouseY <= draggablePiecePosition.y + pieceSize);

        if (isInPiece) {{
            isDragging = true;
            canvas.style.cursor = 'grabbing';
            canvas.onmousemove = onMouseMove;
        }}
    }};

    function onMouseMove(event) {{
        if (isDragging) {{
            const mouseX = event.offsetX;
            const mouseY = event.offsetY;

            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(backgroundImage, 0, 0, canvas.width, canvas.height); 

            draggablePiecePosition.x = mouseX - pieceSize / 2;
            draggablePiecePosition.y = mouseY - pieceSize / 2;

            const timestamp = Date.now();
            mouseMovement.push({{ x: mouseX, y: mouseY, time: timestamp }});

            drawDraggablePiece(draggablePiecePosition.x, draggablePiecePosition.y);
        }}
    }}

    canvas.onmouseup = function(event) {{
        if (isDragging) {{
            const finalX = draggablePiecePosition.x;
            const finalY = draggablePiecePosition.y;
            checkPosition(finalX, finalY);
            isDragging = false;
            canvas.onmousemove = null;  
            canvas.style.cursor = 'default';
        }}
    }};

    async function checkPosition(finalX, finalY) {{
        const response = await fetch('{base_url}check_position', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                captcha_id: captchaId,
                x: finalX,
                y: finalY,
                mouse_movements: mouseMovement
            }})
        }});
        const data = await response.json();
        alert(data.message);
        if (data.success) {{
            console.log("Token:", data.token);
            document.cookie = "captcha_token=" + data.token;
        }}
    }}
}})();
'''
    return Response(js_content, mimetype='application/javascript')

@app.route('/generate_puzzle_piece', methods=['POST'])
def generate_puzzle_piece():
    """Generate a CAPTCHA puzzle piece."""
    # Ensure analytics is initialized for the session
    init_captcha_analytics()

    # Generate a random position for the puzzle piece
    correct_x = random.randint(25, 200)  
    correct_y = random.randint(25, 200)  

    # Save the CAPTCHA instance to the database to be later checked
    captcha = CAPTCHA(correct_x=correct_x, correct_y=correct_y)
    db.session.add(captcha)

    # Increment captchas_generated count for the analytics
    analytics = db.session.query(CAPTCHA_Analytics).filter_by(session_id=session['session_id']).first()
    analytics.captchas_generated += 1

    # Create a new attempt for the CAPTCHA
    new_attempt = {
        "presented_at": datetime.datetime.utcnow().isoformat(),
        "completed_at": None,
        "success": None,
        "time_taken": None,
        "mouse_movements": []
    }

    # Append the new attempt to the attempts list
    if analytics.attempts is None:
        analytics.attempts = []
    analytics.attempts.append(new_attempt)

    db.session.commit()

    # Retrieve a random background image for the puzzle with a size of 250x250
    response = requests.get("https://picsum.photos/250")
    background = Image.open(BytesIO(response.content)).convert('RGBA')

    # Piece data
    piece_size = 50
    outline_color = random.choice(neon_colors)
    fill = random.choice(neon_colors)[:3] + (15,)

    # Create the puzzle piece
    piece_layer = Image.new('RGBA', background.size, (0, 0, 0, 0))
    draw_piece = ImageDraw.Draw(piece_layer)

    # Draw the puzzle piece on the layer
    draw_piece.rectangle(
        [correct_x, correct_y,
         correct_x + piece_size,
         correct_y + piece_size],
        fill=fill,  
        outline=outline_color,
        width=5
    )

    # Apply a Gaussian blur to the piece layer to fight against sharp edges
    blurred_piece = piece_layer.filter(ImageFilter.GaussianBlur(radius=5))  

    # Combine the background and the blurred piece
    img = Image.alpha_composite(background, blurred_piece)

    # Save the image to the static folder
    img_path = os.path.join('static', f'puzzle_{captcha.id}.png')
    img.save(img_path)

    # Return the image path and the CAPTCHA ID to later be sent by the client
    return jsonify({
        'success': True,
        'captcha_id': captcha.id,
        'image': f'{request.url_root}{img_path}'
    })

@app.route('/check_position', methods=['POST'])
def check_position():
    """Check the position of the dragged puzzle piece."""
    # Get the data from the request
    data = request.get_json()
    captcha_id = data.get('captcha_id')
    x = data.get('x')
    y = data.get('y')
    mouse_movements = data.get('mouse_movements')

    # Retrieve the CAPTCHA from the database
    captcha = CAPTCHA.query.get(captcha_id)

    if not captcha:
        return jsonify({'success': False, 'message': 'CAPTCHA not found'}), 404

    tolerance = 10  # Allowable deviation for position
    correct_x = captcha.correct_x
    correct_y = captcha.correct_y

    # Check if the piece is within the allowed tolerance of the correct position
    if abs(x - correct_x) <= tolerance and abs(y - correct_y) <= tolerance:
        # Success! Generate a JWT token
        token = jwt.encode({'captcha_id': captcha_id, 'session_id': session['session_id']}, SECRET_KEY, algorithm='HS256')

        # Increment captchas_solved count for the analytics
        analytics = db.session.query(CAPTCHA_Analytics).filter_by(session_id=session['session_id']).first()

        if analytics is not None:
            analytics.captchas_solved += 1

            # Update the last attempt with the completion time and success status
            if analytics.attempts:  # Check if there are any attempts
                last_attempt_index = -1  # Get the last attempt
                last_attempt = analytics.attempts[last_attempt_index]

                # Update the last attempt details
                last_attempt["completed_at"] = datetime.datetime.utcnow().isoformat()
                last_attempt["success"] = False
                last_attempt["mouse_movements"] = mouse_movements

                # Calculate the time taken to solve the CAPTCHA
                presented_at = datetime.datetime.fromisoformat(last_attempt["presented_at"])
                completed_at = datetime.datetime.fromisoformat(last_attempt["completed_at"])
                last_attempt["time_taken"] = (completed_at - presented_at).total_seconds()

                # Reassign the modified attempts list back to analytics
                analytics.attempts[last_attempt_index] = last_attempt  # Ensure SQLAlchemy tracks this change

                print(last_attempt)

        db.session.commit()

        return jsonify({'success': True, 'message': 'CAPTCHA solved!', 'token': token})

    else:
        # Increment captchas_failed count for the analytics
        analytics = db.session.query(CAPTCHA_Analytics).filter_by(session_id=session['session_id']).first()
        analytics.captchas_failed += 1

        # Update the last attempt with the completion time and success status
        last_attempt = analytics.attempts[-1]  # Get the last attempt
        last_attempt["completed_at"] = datetime.datetime.utcnow().isoformat()
        last_attempt["success"] = False
        last_attempt["mouse_movements"] = mouse_movements
        print(last_attempt)
        
        # Calculate the time taken to solve the CAPTCHA
        presented_at = datetime.datetime.fromisoformat(last_attempt["presented_at"])
        completed_at = datetime.datetime.fromisoformat(last_attempt["completed_at"])
        last_attempt["time_taken"] = (completed_at - presented_at).total_seconds()
        print(last_attempt)

        db.session.commit()

        return jsonify({'success': False, 'message': 'CAPTCHA failed. Please try again.'})

@app.route('/verify_captcha', methods=['POST'])
def verify_captcha():
    """Verify the CAPTCHA token."""
    # Get the token, IP address, and user agent from the request
    token = request.json.get('token')
    ip_address = request.json.get('ip-address')
    user_agent = request.json.get('user-agent')
    
    # Check if the token is provided
    if not token:
        return jsonify({"success": False, "message": "No token provided!"})

    try:
        # Decode the JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        captcha_id = payload['captcha_id']
        user_ip = payload['user_ip']
        user_agent = payload['user_agent']

        # Check if the IP address and user agent match the ones in the token
        if user_ip != ip_address and user_agent != user_agent:
            return jsonify({"success": False, "message": "Identity mismatch!"})

        return jsonify({"success": True, "message": "CAPTCHA verified!", "captcha_id": captcha_id})

    except jwt.ExpiredSignatureError:
        return jsonify({"success": False, "message": "Token has expired!"})
    except jwt.InvalidTokenError:
        return jsonify({"success": False, "message": "Invalid token!"})

if __name__ == '__main__':
    # Create the database tables
    with app.app_context():
        db.create_all()
    # Run the Flask app
    app.run(host='0.0.0.0', port=5007, debug=True)