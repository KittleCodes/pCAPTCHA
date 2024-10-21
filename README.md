# pCAPTCHA - A Puzzle CAPTCHA Implementation

pCAPTCHA is an interactive CAPTCHA solution that challenges users to drag a puzzle piece to its designated spot, protecting against bots.

## Features

- Dynamic puzzle generation: Each CAPTCHA instance creates a new puzzle piece on a background image.
- Interactive interface: Users can drag and drop a puzzle piece to verify their actions.
- Verify captchas have been completed using JWT
- Analytics gathering (sessions that include captchas made, solved, failed, regenerated, along with attempts to solve which include time created, time solved, if success or not, and mouse movements while dragging)
- Analytics dashboard

## Todo
- Add rate limits

## Technologies Used

- **Flask**: A lightweight web framework for Python.
- **SQLite**: A simple database to store CAPTCHA instances.
- **Pillow**: Python Imaging Library for creating and manipulating images.
- **JavaScript**: For dynamic interaction and handling user events.

## Installation

1. Clone the repository:

   ```
   git clone https://github.com/KittleCodes/pCAPTCHA.git
   ```

2. Navigate to the project directory:

   ```
   cd pCAPTCHA
   ```

3. Create a virtual environment (optional but recommended):

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

4. Install the required packages:

   ```
   pip install Flask requests Pillow
   ```

## Usage

1. Start the Flask application:

   ```
   python app.py
   ```

2. Add the required elements to website needed for a pCAPTCHA
    ```
    <div id="captchaContainer"></div>
    ```
    ```
    <script src="/pCaptcha.js"></script>
    ```

## Dashboard Usage

1. Start the Flask application:

   ```
   python dashboard.py
   ```

2. Visit the provided url
    ```
    127.0.0.1:5010
    ```

## API Endpoints

- **GET /**: Serves an example HTML page using pCAPTCHA.
- **GET /pCaptcha.js**: Serves the JavaScript file for handling CAPTCHA interactions.
- **POST /generate_puzzle_piece**: Generates a new puzzle piece and returns the image URL and CAPTCHA ID.
- **POST /check_position**: Checks if the dragged puzzle piece is in the correct position and returns the result.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you'd like to contribute to this project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [Picsum Photos](https://picsum.photos/) for random images.