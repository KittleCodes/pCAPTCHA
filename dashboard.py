import base64
import io
import multiprocessing
from flask import Flask, render_template_string
from models import db, CAPTCHA_Analytics, CAPTCHA_Attempt
from sqlalchemy import func, desc
from PIL import Image, ImageDraw

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///captchas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def analyze_captcha_data():
    """Retrieve captcha data from the database and calculate analytics for the dashboard."""
    # Query for total analytics data
    total_data = db.session.query(
        func.sum(CAPTCHA_Analytics.captchas_generated).label('total_generated'),
        func.sum(CAPTCHA_Analytics.captchas_solved).label('total_solved'),
        func.sum(CAPTCHA_Analytics.captchas_failed).label('total_failed'),
        func.count(CAPTCHA_Analytics.session_id).label('total_sessions')
    ).first()

    total_generated = total_data.total_generated or 0
    total_solved = total_data.total_solved or 0
    total_failed = total_data.total_failed or 0
    total_sessions = total_data.total_sessions or 1  # Prevent division by zero

    # Calculate average generations, solves, and fails per session
    avg_generations_per_session = total_generated / total_sessions
    avg_regenerations_per_session = (total_generated - (total_solved + total_failed)) / total_sessions
    avg_solves_per_session = total_solved / total_sessions
    avg_fails_per_session = total_failed / total_sessions

    # Find the most common generation time
    most_common_generation_time_hour = (
        db.session.query(func.extract('hour', CAPTCHA_Attempt.presented_at).label('hour'), 
                func.count(func.extract('hour', CAPTCHA_Attempt.presented_at)).label('count'))
            .group_by(func.extract('hour', CAPTCHA_Attempt.presented_at))
            .order_by(desc('count'))
            .first()
    )
    
    most_common_generation_time_hour = most_common_generation_time_hour[0] if most_common_generation_time_hour is not None else None

    # Find the most common regeneration time
    most_common_regeneration_time_hour = (
        db.session.query(func.extract('hour', CAPTCHA_Attempt.presented_at).label('hour'), 
                func.count(func.extract('hour', CAPTCHA_Attempt.presented_at)).label('count'))
            .filter(CAPTCHA_Attempt.completed_at is None)
            .group_by(func.extract('hour', CAPTCHA_Attempt.presented_at))
            .order_by(desc('count'))
            .first()
    )
    
    most_common_regeneration_time_hour = most_common_regeneration_time_hour[0] if most_common_regeneration_time_hour is not None else None

    # Find the most common solving time
    most_common_solve_time_hour = (
        db.session.query(func.extract('hour', CAPTCHA_Attempt.completed_at).label('hour'), 
                func.count(func.extract('hour', CAPTCHA_Attempt.completed_at)).label('count'))
            .filter(CAPTCHA_Attempt.completed_at is not None, CAPTCHA_Attempt.success is True)
            .group_by(func.extract('hour', CAPTCHA_Attempt.presented_at))
            .order_by(desc('count'))
            .first()
    )
    
    most_common_solve_time_hour = most_common_solve_time_hour[0] if most_common_solve_time_hour is not None else None
    
    # Find the most common failing time
    most_common_fail_time_hour = (
        db.session.query(func.extract('hour', CAPTCHA_Attempt.completed_at).label('hour'), 
                func.count(func.extract('hour', CAPTCHA_Attempt.completed_at)).label('count'))
            .filter(CAPTCHA_Attempt.completed_at is not None, CAPTCHA_Attempt.success is False)
            .group_by(func.extract('hour', CAPTCHA_Attempt.presented_at))
            .order_by(desc('count'))
            .first()
    )
    
    most_common_fail_time_hour = most_common_fail_time_hour[0] if most_common_fail_time_hour is not None else None

    # Calculate average time to solve
    avg_time_to_solve = db.session.query(func.avg(CAPTCHA_Attempt.time_taken).label('average')).filter(CAPTCHA_Attempt.success == True).scalar()

    # Calculate average time to fail
    avg_time_to_fail = db.session.query(func.avg(CAPTCHA_Attempt.time_taken).label('average')).filter(CAPTCHA_Attempt.success == False).scalar()

    # Constructing results
    results = {
        "pCAPTCHAs Generated": {
            "Average Generations Per Session": avg_generations_per_session,
            "Most Common Time Of Generation": most_common_generation_time_hour,
        },
        "pCAPTCHAs Regenerated": {
            "Average Regenerations Per Session": avg_regenerations_per_session,
            "Most Common Time Of Regeneration": most_common_regeneration_time_hour
        },
        "pCAPTCHAs Solved": {
            "Average Solves Per Session": avg_solves_per_session,
            "Most Common Time Of Solve": most_common_solve_time_hour,
            "Average Time To Solve": avg_time_to_solve,
        },
        "pCAPTCHAs Failed": {
            "Average Fails Per Session": avg_fails_per_session,
            "Most Common Time Of Fail": most_common_fail_time_hour,
            "Average Time To Fail": avg_time_to_fail,
        },
    }

    return results

def process_mouse_movement(data):
    """Check if data is there and then create image from it."""
    mouse_movement, success = data
    if mouse_movement is not None:
        image_base64 = create_base64_image(mouse_movement, success)
        return image_base64 if image_base64 else None
    return None

def create_base64_image(mouse_movements, success):
    """Create an image showing the mouse path on the captcha, and changing the background color depending on success."""
    # Check if mouse_movements is empty
    if not mouse_movements:
        return None  # Handle empty input gracefully

    # Extract x, y coordinates from the list
    x, y = zip(*[(m['x'], m['y']) for m in mouse_movements])
    
    # Create a new image with a green background if success, red otherwise
    background_color = (0, 255, 0) if success else (255, 0, 0)  # Green or Red
    img = Image.new('RGB', (250, 250), background_color)

    # Create a draw object
    draw = ImageDraw.Draw(img)

    # Draw the mouse movements
    for x_coord, y_coord in zip(x, y):
        if 0 <= x_coord < 250 and 0 <= y_coord < 250:  # Ensure coordinates are within bounds
            draw.ellipse((x_coord-2, y_coord-2, x_coord+2, y_coord+2), fill='blue')  # Small circles

    # Save to a BytesIO object
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Encode to Base64
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return image_base64

@app.route('/')
def index():
    """Returns an overview of data from the analytics table."""
    total_pcaptchas_generated = db.session.query(func.sum(CAPTCHA_Analytics.captchas_generated)).scalar() or 0
    total_pcaptchas_solved = db.session.query(func.sum(CAPTCHA_Analytics.captchas_solved)).scalar() or 0
    total_pcaptchas_failed = db.session.query(func.sum(CAPTCHA_Analytics.captchas_failed)).scalar() or 0
    total_pcaptchas_regenerated = total_pcaptchas_generated - (total_pcaptchas_solved + total_pcaptchas_failed)

    captcha_analysis = analyze_captcha_data()

    return f'''
<!DOCTYPE html>
<html data-bs-theme="light" lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
    <title>pCAPTCHA</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
</head>

<body style="background: var(--bs-secondary-text-emphasis);">
    <nav class="navbar navbar-expand-md bg-dark py-3" data-bs-theme="dark">
        <div class="container"><a class="navbar-brand d-flex align-items-center" href="/"><span class="bs-icon-sm bs-icon-rounded bs-icon-primary d-flex justify-content-center align-items-center me-2 bs-icon"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-robot">
                        <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.58 26.58 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.933.933 0 0 1-.765.935c-.845.147-2.34.346-4.235.346-1.895 0-3.39-.2-4.235-.346A.933.933 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a24.767 24.767 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25.286 25.286 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135Z"></path>
                        <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"></path>
                    </svg></span><span>pCAPTCHA Dashboard</span></a><button data-bs-toggle="collapse" class="navbar-toggler" data-bs-target="#navcol-5"><span class="visually-hidden">Toggle navigation</span><span class="navbar-toggler-icon"></span></button>
            <div class="collapse navbar-collapse" id="navcol-5">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link active" href="/">Overview</a></li>
                    <li class="nav-item"><a class="nav-link" href="/sessions">Sessions</a></li>
                    <li class="nav-item"><a class="nav-link" href="/mouse-movement">Mouse Movement</a></li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container py-4 py-xl-5" style="color: var(--bs-body-bg);background: var(--bs-gray-800);margin-top: 30px;border-radius: 12px;border: 0.8px solid var(--bs-body-color);">
        <div class="row gy-4 row-cols-2 row-cols-md-4">
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-indigo);"><i class="fa fa-image"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{total_pcaptchas_generated}</h2>
                        <p class="mb-0">pCAPTCHAs Generated</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-yellow);"><i class="fa fa-rotate-right"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{total_pcaptchas_regenerated}</h2>
                        <p class="mb-0">pCAPTCHAs Regenerated</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-teal);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-lg">
                            <path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425a.247.247 0 0 1 .02-.022"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{total_pcaptchas_solved}</h2>
                        <p class="mb-0">pCAPTCHAs Solved</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-form-invalid-color);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-x">
                            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{total_pcaptchas_failed}</h2>
                        <p class="mb-0">pCAPTCHAs Failed</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="container" style="margin-top: 30px;">
    <div class="card" style="background: var(--bs-body-color);color: var(--bs-body-bg);margin-bottom: 30px;">
        <div class="card-body">
            <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-indigo);"><i class="fa fa-image"></i></div>
            <h4 class="card-title">pCAPTCHAs Generated</h4>
            <h6 class="text-secondary card-subtitle mb-2">Data about generated pCAPTCHAs</h6>
            <p class="card-text"><strong>Average Generations Per Session:</strong> {captcha_analysis["pCAPTCHAs Generated"]["Average Generations Per Session"]}</p>
            <p class="card-text"><strong>Most Common Time Of Generation:</strong> {captcha_analysis["pCAPTCHAs Generated"]["Most Common Time Of Generation"]} GMT</p>
        </div>
    </div>
    <div class="card" style="background: var(--bs-body-color);color: var(--bs-body-bg);margin-bottom: 30px;">
        <div class="card-body">
            <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-yellow);"><i class="fa fa-rotate-right"></i></div>
            <h4 class="card-title">pCAPTCHAs Regenerated</h4>
            <h6 class="text-secondary card-subtitle mb-2">Data about regenerated pCAPTCHAs</h6>
            <p class="card-text"><strong>Average Regenerations Per Session:</strong> {captcha_analysis["pCAPTCHAs Regenerated"]["Average Regenerations Per Session"]}</p>
            <p class="card-text"><strong>Most Common Time Of Regeneration:</strong> {captcha_analysis["pCAPTCHAs Regenerated"]["Most Common Time Of Regeneration"]} GMT</p>
        </div>
    </div>
    <div class="card" style="background: var(--bs-body-color);color: var(--bs-body-bg);margin-bottom: 30px;">
        <div class="card-body">
            <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-teal);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-lg">
                    <path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425a.247.247 0 0 1 .02-.022"></path>
                </svg></div>
            <h4 class="card-title">pCAPTCHAs Solved</h4>
            <h6 class="text-secondary card-subtitle mb-2">Data about solved pCAPTCHAs</h6>
            <p class="card-text"><strong>Average Solves Per Session:</strong> {captcha_analysis["pCAPTCHAs Solved"]["Average Solves Per Session"]}</p>
            <p class="card-text"><strong>Most Common Time Of Solve:</strong> {captcha_analysis["pCAPTCHAs Solved"]["Most Common Time Of Solve"]} GMT</p>
            <p class="card-text"><strong>Average Time To Solve:</strong> {captcha_analysis["pCAPTCHAs Solved"]["Average Time To Solve"]}</p>
        </div>
    </div>
    <div class="card" style="background: var(--bs-body-color);color: var(--bs-body-bg);margin-bottom: 30px;">
        <div class="card-body">
            <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-form-invalid-color);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-x">
                    <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"></path>
                </svg></div>
            <h4 class="card-title">pCAPTCHAs Failed</h4>
            <h6 class="text-secondary card-subtitle mb-2">Data about failed pCAPTCHAs</h6>
            <p class="card-text"><strong>Average Fails Per Session:</strong> {captcha_analysis["pCAPTCHAs Failed"]["Average Fails Per Session"]}</p>
            <p class="card-text"><strong>Most Common Time Of Fail:</strong> {captcha_analysis["pCAPTCHAs Failed"]["Most Common Time Of Fail"]} GMT</p>
            <p class="card-text"><strong>Average Time To Fail:</strong> {captcha_analysis["pCAPTCHAs Failed"]["Average Time To Fail"]}</p>
        </div>
    </div>
</div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>

</html>
'''

@app.route('/sessions')
def sessions():
    """Display a list of sessions and their statics."""
    total_pcaptchas_generated = db.session.query(func.sum(CAPTCHA_Analytics.captchas_generated)).scalar() or 0
    total_pcaptchas_solved = db.session.query(func.sum(CAPTCHA_Analytics.captchas_solved)).scalar() or 0
    total_pcaptchas_failed = db.session.query(func.sum(CAPTCHA_Analytics.captchas_failed)).scalar() or 0
    total_pcaptchas_regenerated = total_pcaptchas_generated - (total_pcaptchas_solved + total_pcaptchas_failed)

    session_records = db.session.query(CAPTCHA_Analytics).all()

    session_stats = {
        'total_session_count': len(session_records),
        'total_pcaptchas_generated': total_pcaptchas_generated,
        'total_pcaptchas_solved': total_pcaptchas_solved,
        'total_pcaptchas_failed': total_pcaptchas_failed,
        'total_pcaptchas_regenerated': total_pcaptchas_regenerated,
    }

    return render_template_string('''
<!DOCTYPE html>
<html data-bs-theme="light" lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
    <title>pCAPTCHA</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
</head>

<body style="background: var(--bs-secondary-text-emphasis);">
    <nav class="navbar navbar-expand-md bg-dark py-3" data-bs-theme="dark">
        <div class="container"><a class="navbar-brand d-flex align-items-center" href="/"><span class="bs-icon-sm bs-icon-rounded bs-icon-primary d-flex justify-content-center align-items-center me-2 bs-icon"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-robot">
                        <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.58 26.58 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.933.933 0 0 1-.765.935c-.845.147-2.34.346-4.235.346-1.895 0-3.39-.2-4.235-.346A.933.933 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a24.767 24.767 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25.286 25.286 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135Z"></path>
                        <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"></path>
                    </svg></span><span>pCAPTCHA Dashboard</span></a><button data-bs-toggle="collapse" class="navbar-toggler" data-bs-target="#navcol-5"><span class="visually-hidden">Toggle navigation</span><span class="navbar-toggler-icon"></span></button>
            <div class="collapse navbar-collapse" id="navcol-5">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Overview</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/sessions">Sessions</a></li>
                    <li class="nav-item"><a class="nav-link" href="/mouse-movement">Mouse Movement</a></li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container py-4 py-xl-5" style="color: var(--bs-body-bg);background: var(--bs-gray-800);margin-top: 30px;border-radius: 12px;border: 0.8px solid var(--bs-body-color);">
        <div class="row gy-4 row-cols-2 row-cols-md-4 text-center d-xl-flex justify-content-xl-center">
            <div class="col text-center">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-indigo);"><i class="fa fa-database"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{{stats.total_session_count}}</h2>
                        <p class="mb-0">Sessions</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="row gy-4 row-cols-2 row-cols-md-4">
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-indigo);"><i class="fa fa-image"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{{stats.total_pcaptchas_generated}}</h2>
                        <p class="mb-0">pCAPTCHAs Generated</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-yellow);"><i class="fa fa-rotate-right"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{{stats.total_pcaptchas_regenerated}}</h2>
                        <p class="mb-0">pCAPTCHAs Regenerated</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-teal);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-lg">
                            <path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425a.247.247 0 0 1 .02-.022"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{{stats.total_pcaptchas_solved}}</h2>
                        <p class="mb-0">pCAPTCHAs Solved</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-form-invalid-color);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-x">
                            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">{{stats.total_pcaptchas_failed}}</h2>
                        <p class="mb-0">pCAPTCHAs Failed</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="container" style="margin-top: 30px;">
        <div class="table-responsive" style="background: var(--bs-body-color);border-radius: 10px;border: 0.8px solid var(--bs-emphasis-color) ;">
            <table class="table">
                <thead>
                    <tr>
                        <th style="background: var(--bs-primary-text-emphasis);color: var(--bs-table-bg);border-color: var(--bs-table-color);">Session ID</th>
                        <th style="background: var(--bs-warning-text-emphasis);color: var(--bs-table-bg);border-color: var(--bs-table-color);">pCAPTCHAs Generated</th>
                        <th style="background: var(--bs-success-text-emphasis);color: var(--bs-table-bg);border-color: var(--bs-table-color);">pCAPTCHAs Solved</th>
                        <th style="background: var(--bs-danger-text-emphasis);color: var(--bs-table-bg);border-color: var(--bs-table-color);">pCAPTCHAs Failed</th>
                        <th style="background: var(--bs-info-text-emphasis);color: var(--bs-table-bg);border-color: var(--bs-table-color);">Created At</th>
                    </tr>
                </thead>
                <tbody style="background: var(--bs-body-color);">
                    {% for record in records %}
                        <tr>
                            <td style="background: var(--bs-body-color);color: var(--bs-table-bg);border-color: var(--bs-table-color);">{{record.session_id}}</td>
                            <td style="background: var(--bs-body-color);color: var(--bs-table-bg);border-color: var(--bs-table-color);">{{record.captchas_generated}}</td>
                            <td style="background: var(--bs-body-color);color: var(--bs-table-bg);border-color: var(--bs-table-color);">{{record.captchas_solved}}</td>
                            <td style="background: var(--bs-body-color);color: var(--bs-table-bg);border-color: var(--bs-table-color);">{{record.captchas_failed}}</td>
                            <td style="background: var(--bs-body-color);color: var(--bs-table-bg);border-color: var(--bs-table-color);">{{record.created_at}} GMT</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>

</html>
''', stats=session_stats, records=session_records)

@app.route('/mouse-movement')
def mouse_movement():
    """Show the mouse path of attempts."""
    # Fetch attempt data from the database
    results = db.session.execute(
        db.select(
            func.sum(CAPTCHA_Analytics.captchas_generated),
            func.sum(CAPTCHA_Analytics.captchas_solved),
            func.sum(CAPTCHA_Analytics.captchas_failed)
        )
    ).first()

    total_pcaptchas_generated, total_pcaptchas_solved, total_pcaptchas_failed = results
    total_pcaptchas_regenerated = total_pcaptchas_generated - (total_pcaptchas_solved + total_pcaptchas_failed)

    # Fetch mouse movement data
    mouse_and_success_data = db.session.execute(db.select(CAPTCHA_Attempt.mouse_movements, CAPTCHA_Attempt.success)).all()
    
    # Loop through mouse
    images = []

    # Create a pool of workers
    with multiprocessing.Pool() as pool:
        # Process the data in parallel
        results = pool.map(process_mouse_movement, mouse_and_success_data)

    # Filter out None results and append valid images
    images = [image for image in results if image is not None]

    return render_template_string('''
<!DOCTYPE html>
<html data-bs-theme="light" lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
    <title>pCAPTCHA</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    <link rel="stylesheet" href="assets/css/Navbar-Right-Links-Dark-icons.css">
</head>

<body style="background: var(--bs-secondary-text-emphasis);">
    <nav class="navbar navbar-expand-md bg-dark py-3" data-bs-theme="dark">
        <div class="container"><a class="navbar-brand d-flex align-items-center" href="/"><span class="bs-icon-sm bs-icon-rounded bs-icon-primary d-flex justify-content-center align-items-center me-2 bs-icon"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-robot">
                        <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5M3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.58 26.58 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.933.933 0 0 1-.765.935c-.845.147-2.34.346-4.235.346-1.895 0-3.39-.2-4.235-.346A.933.933 0 0 1 3 9.219zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a24.767 24.767 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25.286 25.286 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.076l-.754.785-.842-1.7a.25.25 0 0 0-.182-.135Z"></path>
                        <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2zM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5"></path>
                    </svg></span><span>pCAPTCHA Dashboard</span></a><button data-bs-toggle="collapse" class="navbar-toggler" data-bs-target="#navcol-5"><span class="visually-hidden">Toggle navigation</span><span class="navbar-toggler-icon"></span></button>
            <div class="collapse navbar-collapse" id="navcol-5">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="/">Overview</a></li>
                    <li class="nav-item"><a class="nav-link" href="/sessions">Sessions</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/mouse-movement">Mouse Movement</a></li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container py-4 py-xl-5" style="color: var(--bs-body-bg);background: var(--bs-gray-800);margin-top: 30px;border-radius: 12px;border: 0.8px solid var(--bs-body-color);">
        <div class="row gy-4 row-cols-2 row-cols-md-4 text-center d-xl-flex justify-content-xl-center">
            <div class="col text-center d-xl-flex justify-content-xl-center">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-indigo);"><i class="fa fa-database"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">'''+ str(total_pcaptchas_failed + total_pcaptchas_solved) + '''</h2>
                        <p class="mb-0">Attempts</p>
                    </div>
                </div>
            </div>
            <div class="col text-center d-xl-flex justify-content-xl-center">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-teal);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-lg">
                            <path d="M12.736 3.97a.733.733 0 0 1 1.047 0c.286.289.29.756.01 1.05L7.88 12.01a.733.733 0 0 1-1.065.02L3.217 8.384a.757.757 0 0 1 0-1.06.733.733 0 0 1 1.047 0l3.052 3.093 5.4-6.425a.247.247 0 0 1 .02-.022"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">'''+ str(total_pcaptchas_solved) + '''</h2>
                        <p class="mb-0">pCAPTCHAs Solved</p>
                    </div>
                </div>
            </div>
            <div class="col text-center d-xl-flex justify-content-xl-center">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-form-invalid-color);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="currentColor" viewBox="0 0 16 16" class="bi bi-x">
                            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708"></path>
                        </svg></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">'''+ str(total_pcaptchas_failed) + '''</h2>
                        <p class="mb-0">pCAPTCHAs Failed</p>
                    </div>
                </div>
            </div>
            <div class="col">
                <div class="text-center d-flex flex-column justify-content-center align-items-center py-3">
                    <div class="bs-icon-xl bs-icon-circle bs-icon-primary d-flex flex-shrink-0 justify-content-center align-items-center d-inline-block mb-2 bs-icon lg" style="background: var(--bs-yellow);"><i class="fa fa-rotate-right"></i></div>
                    <div class="px-3">
                        <h2 class="fw-bold mb-0">'''+ str(total_pcaptchas_regenerated) + '''</h2>
                        <p class="mb-0">pCAPTCHAs Regenerated</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="container">
        <div class="row" style="margin-top: 30px;">
            {% for image in images %}
                <div class="col-md-4">
                    <div class="card" style="background-color: var(--bs-body-color);">
                        <div class="card-body text-center">
                            <img src="data:image/png;base64,{{ image }}" style="width: 100%; height: auto;">
                        </div>
                    </div>
                </div>
                {% if loop.index % 3 == 0 %}
                    </div><div class="row" style="margin-top: 30px;">
                {% endif %}
            {% endfor %}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>

</html>
''', images=images)

if __name__ == '__main__':
    # Create the database tables
    with app.app_context():
        db.create_all()
    # Run the Flask app
    app.run(host='0.0.0.0', port=5010, debug=True)