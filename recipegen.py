import os
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import openai
from functools import wraps

# Load configuration from environment
API_KEY = os.getenv('APP_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'txt'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DEBUG'] = False  # Turn off debug mode in production

openai.api_key = OPENAI_API_KEY

# Authentication decorator using a simple API key
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.headers.get('X-API-KEY')
        if not key or key != API_KEY:
            abort(401, description='Unauthorized')
        return f(*args, **kwargs)
    return decorated_function

# Utility: validate file extension
def allowed_file(filename):
    return ('.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)

# Route to generate recipe
@app.route('/generate_recipe', methods=['POST'])
@require_api_key
def generate_recipe():
    data = request.get_json()
    if not data or 'ingredients' not in data:
        abort(400, description='Missing ingredients field')

    # Input validation: ensure ingredients is a list of strings
    ingredients = data['ingredients']
    if not isinstance(ingredients, list) or not all(isinstance(i, str) for i in ingredients):
        abort(400, description='Invalid ingredients format')

    # Sanitize and build prompt safely
    safe_ingredients = [i.strip() for i in ingredients]
    system_prompt = 'You are a helpful cooking assistant.'
    user_prompt = f"Create a recipe using only: {', '.join(safe_ingredients)}."

    try:
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        recipe = response.choices[0].message.content
        return jsonify({'recipe': recipe})
    except openai.error.OpenAIError as e:
        abort(502, description=f'AI service error: {e}')

# Route to upload files securely
@app.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    if 'file' not in request.files:
        abort(400, description='No file part')
    file = request.files['file']
    if file.filename == '':
        abort(400, description='No selected file')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(file_path)
        return jsonify({'message': 'File uploaded', 'filename': filename})
    else:
        abort(400, description='File type not allowed')

# Route to download files, restricted
@app.route('/files/<filename>', methods=['GET'])
@require_api_key
def get_file(filename):
    # Serve only files with allowed extensions
    if not allowed_file(filename):
        abort(403, description='Forbidden file type')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Use a production WSGI server instead of Flask built-in
    app.run(host='0.0.0.0', port=5000)
