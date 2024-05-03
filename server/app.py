from flask import Flask, send_from_directory
from flask import request
from flask_cors import CORS
from backend import Backend_Api  # Ensure this path is correct

app = Flask(__name__)
CORS(app)

backend_api = Backend_Api(app, {})  # Make sure this is instantiated at the right place

@app.route('/sensitive-words')
def serve_sensitive_words():
    return send_from_directory('server', 'sensitive_words.txt')

# Dynamically add the routes from Backend_Api
for endpoint, endpoint_config in backend_api.routes.items():
    app.add_url_rule(endpoint, endpoint_config['function'].__name__, endpoint_config['function'], methods=endpoint_config['methods'])

if __name__ == '__main__':
    app.run(debug=True)
