from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from geopy.distance import geodesic
from inference_sdk import InferenceHTTPClient

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Roboflow Configuration (set these as environment variables or update directly)
ROBOFLOW_API_KEY = os.getenv('ROBOFLOW_API_KEY', 'mnmeGlS90Or7kmyM7X5M')  # Replace with your actual API key
ROBOFLOW_WORKSPACE = os.getenv('ROBOFLOW_WORKSPACE', 'coderspace')
ROBOFLOW_WORKFLOW_ID = os.getenv('ROBOFLOW_WORKFLOW_ID', 'custom-workflow')

# Initialize Roboflow client
roboflow_client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=ROBOFLOW_API_KEY
)

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='nitya',
        database='Mini'
    )

# Database initialization
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS hazards (
            id INT AUTO_INCREMENT PRIMARY KEY,
            description VARCHAR(1024) NOT NULL,
            lat DOUBLE NOT NULL,
            lng DOUBLE NOT NULL,
            image_path VARCHAR(512),
            reported_by CHAR(22),
            verified TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    # Ensure users table exists for auth flows used by the frontend tabs
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            uname CHAR(22) NOT NULL,
            password CHAR(20) NOT NULL,
            email VARCHAR(50) NOT NULL,
            admins TINYINT(1) DEFAULT 0,
            hazards INT DEFAULT 0,
            verified INT DEFAULT 0
        )
        '''
    )
    conn.commit()

    # Helper to safely add columns if they already exist in older databases
    def safe_add_column(table: str, column_definition: str):
        try:
            c.execute(f'ALTER TABLE {table} ADD COLUMN {column_definition}')
            conn.commit()
        except mysql.connector.Error as e:
            if e.errno != 1060:  # 1060 = Duplicate column name
                print(f"Warning: Could not add column {column_definition} to {table}: {e}")
            conn.rollback()

    # Ensure legacy databases have the new columns
    safe_add_column('hazards', 'reported_by CHAR(22)')
    safe_add_column('users', 'admins TINYINT(1) DEFAULT 0')
    safe_add_column('users', 'hazards INT DEFAULT 0')
    safe_add_column('users', 'verified INT DEFAULT 0')

    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_hazard_with_roboflow(image_path):
    """
    Verify if an image contains a hazard using Roboflow workflow API
    Returns: (is_hazard: bool, is_road: bool, prediction_class: str, confidence: float, details: dict)
    """
    try:
        full_image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
        
        if not os.path.exists(full_image_path):
            print(f"Error: Image file not found at {full_image_path}")
            return False, False, None, 0.0, {'error': 'Image file not found'}
        
        print(f"Calling Roboflow API for image: {image_path}")
        
        # Run workflow on the image
        result = roboflow_client.run_workflow(
            workspace_name=ROBOFLOW_WORKSPACE,
            workflow_id=ROBOFLOW_WORKFLOW_ID,
            images={
                "image": full_image_path
            },
            use_cache=True
        )
        
        # Debug: Print the full response to understand the structure
        print(f"Roboflow API Response: {result}")
        print(f"Response type: {type(result)}")
        
        # Parse the result to determine if it's a hazard and check for "road" class
        is_hazard = False
        is_road = False
        prediction_class = None
        confidence = 0.0
        
        # Convert result to dict if it's a string (JSON)
        if isinstance(result, str):
            try:
                import json
                result = json.loads(result)
            except:
                print(f"Warning: Could not parse result as JSON: {result}")
        
        # Common workflow response formats:
        if isinstance(result, dict):
            print(f"Processing dict result with keys: {result.keys()}")
            
            # Option 1: Check for workflow output structure (common in Roboflow workflows)
            # Workflows often return results nested under step names or output keys
            if 'output' in result:
                output = result['output']
                print(f"Found 'output' key: {output}")
                if isinstance(output, dict):
                    result = output  # Use output as the main result
                elif isinstance(output, str):
                    try:
                        import json
                        result = json.loads(output)
                    except:
                        pass
            
            # Option 1: If result contains predictions/detections
            if 'predictions' in result:
                predictions = result['predictions']
                print(f"Found predictions: {predictions}")
                if predictions and len(predictions) > 0:
                    # Get the top prediction
                    top_prediction = predictions[0]
                    if isinstance(top_prediction, dict):
                        # Check for class name in various possible fields
                        pred_class = (top_prediction.get('class') or 
                                    top_prediction.get('predicted_class') or 
                                    top_prediction.get('label') or
                                    top_prediction.get('class_name') or
                                    top_prediction.get('name'))
                        if pred_class:
                            prediction_class = str(pred_class).lower().strip()
                            print(f"Predicted class: {prediction_class}")
                            # Check if it's "road" (case-insensitive, handle variations)
                            if prediction_class == 'road' or 'road' in prediction_class:
                                is_road = True
                                print("Detected as ROAD - will reject")
                            else:
                                is_hazard = True
                                print(f"Detected as hazard: {prediction_class}")
                        
                        # Get confidence if available
                        if 'confidence' in top_prediction:
                            confidence = float(top_prediction['confidence'])
                        elif 'score' in top_prediction:
                            confidence = float(top_prediction['score'])
                        elif 'probability' in top_prediction:
                            confidence = float(top_prediction['probability'])
            
            # Option 2: If result has a direct class/prediction field
            elif 'class' in result or 'predicted_class' in result or 'label' in result:
                pred_class = (result.get('class') or 
                            result.get('predicted_class') or 
                            result.get('label') or
                            result.get('class_name'))
                print(f"Found direct class field: {pred_class}")
                if pred_class:
                    prediction_class = str(pred_class).lower().strip()
                    if prediction_class == 'road' or 'road' in prediction_class:
                        is_road = True
                        print("Detected as ROAD - will reject")
                    else:
                        is_hazard = True
                        print(f"Detected as hazard: {prediction_class}")
                confidence = float(result.get('confidence', result.get('score', result.get('probability', 0.0))))
            
            # Option 3: If result has classes or labels array
            elif 'classes' in result or 'labels' in result:
                classes = result.get('classes') or result.get('labels', [])
                print(f"Found classes/labels array: {classes}")
                if classes and len(classes) > 0:
                    top_class = classes[0]
                    if isinstance(top_class, dict):
                        pred_class = (top_class.get('class', '') or 
                                    top_class.get('name', '') or 
                                    top_class.get('label', '') or
                                    top_class.get('class_name', ''))
                        if pred_class:
                            prediction_class = str(pred_class).lower().strip()
                            if prediction_class == 'road' or 'road' in prediction_class:
                                is_road = True
                                print("Detected as ROAD - will reject")
                            else:
                                is_hazard = True
                                print(f"Detected as hazard: {prediction_class}")
                        confidence = float(top_class.get('confidence', top_class.get('score', top_class.get('probability', 0.0))))
                    elif isinstance(top_class, str):
                        prediction_class = top_class.lower().strip()
                        if prediction_class == 'road' or 'road' in prediction_class:
                            is_road = True
                            print("Detected as ROAD - will reject")
                        else:
                            is_hazard = True
                            print(f"Detected as hazard: {prediction_class}")
            
            # Option 4: Check for nested result structure
            elif 'result' in result:
                nested_result = result['result']
                print(f"Found nested 'result': {nested_result}")
                if isinstance(nested_result, dict):
                    pred_class = (nested_result.get('class', '') or 
                                nested_result.get('predicted_class', '') or 
                                nested_result.get('label', '') or
                                nested_result.get('class_name', ''))
                    if pred_class:
                        prediction_class = str(pred_class).lower().strip()
                        if prediction_class == 'road' or 'road' in prediction_class:
                            is_road = True
                            print("Detected as ROAD - will reject")
                        else:
                            is_hazard = True
                            print(f"Detected as hazard: {prediction_class}")
                    confidence = float(nested_result.get('confidence', nested_result.get('score', nested_result.get('probability', 0.0))))
            
            # If no prediction class found in dict, check the entire result structure
            if prediction_class is None:
                print("Warning: No prediction class found in response. Checking all string values...")
                # Search for 'road' in the entire result structure
                result_str = str(result).lower()
                if 'road' in result_str and ('hazard' not in result_str or result_str.find('road') < result_str.find('hazard')):
                    is_road = True
                    prediction_class = 'road'
                    print("Found 'road' in response - will reject")
                else:
                    is_hazard = True
                    prediction_class = 'unknown'
                    print("No clear 'road' detection - accepting as hazard")
        
        # Handle list results (if result is a list, not a dict)
        elif isinstance(result, list) and len(result) > 0:
            first_item = result[0]
            if isinstance(first_item, dict):
                pred_class = (first_item.get('class', '') or 
                            first_item.get('predicted_class', '') or 
                            first_item.get('label', '') or
                            first_item.get('class_name', ''))
                if pred_class:
                    prediction_class = str(pred_class).lower().strip()
                    if prediction_class == 'road' or 'road' in prediction_class:
                        is_road = True
                        print("Detected as ROAD - will reject")
                    else:
                        is_hazard = True
                        print(f"Detected as hazard: {prediction_class}")
        
        # If still no prediction found after all checks
        if prediction_class is None:
            print(f"Warning: Unexpected result type: {type(result)}, value: {result}")
            # If we can't parse it, assume it's a hazard (fail-open approach)
            is_hazard = True
            prediction_class = 'unknown'
            print("Could not determine class - accepting as hazard by default")
        
        print(f"Final decision - is_road: {is_road}, is_hazard: {is_hazard}, class: {prediction_class}")
        
        return is_hazard, is_road, prediction_class, confidence, result
        
    except Exception as e:
        print(f"Error verifying hazard with Roboflow: {str(e)}")
        import traceback
        traceback.print_exc()
        # On error, assume it's NOT a road (fail-open: accept as hazard if we can't verify)
        return True, False, None, 0.0, {'error': str(e)}

def check_nearby_hazards(lat, lng, radius_meters=100):
    """Check if there are hazards within specified radius"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, lat, lng, verified FROM hazards')
    hazards = c.fetchall()
    conn.close()

    nearby_ids = []
    current_location = (lat, lng)

    for hazard_id, h_lat, h_lng, verified in hazards:
        hazard_location = (h_lat, h_lng)
        distance = geodesic(current_location, hazard_location).meters

        if distance <= radius_meters:
            nearby_ids.append(hazard_id)

    return nearby_ids

def mark_as_verified(hazard_ids):
    """Mark multiple hazards as verified"""
    if not hazard_ids:
        return

    conn = get_db_connection()
    c = conn.cursor()

    placeholders = ','.join(['%s'] * len(hazard_ids))
    c.execute(
        f'SELECT id, reported_by, verified FROM hazards WHERE id IN ({placeholders})',
        tuple(hazard_ids)
    )
    rows = c.fetchall()

    # Filter hazards that are not yet verified
    ids_to_update = [row[0] for row in rows if not row[2]]
    reporters_to_increment = [row[1] for row in rows if not row[2] and row[1]]

    if ids_to_update:
        placeholders_update = ','.join(['%s'] * len(ids_to_update))
        c.execute(
            f'UPDATE hazards SET verified = 1 WHERE id IN ({placeholders_update})',
            tuple(ids_to_update)
        )

    for reporter in reporters_to_increment:
        c.execute('UPDATE users SET verified = verified + 1 WHERE uname = %s', (reporter,))

    conn.commit()
    conn.close()

def delete_hazard_record(hazard_id):
    """Delete a hazard record from the database"""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM hazards WHERE id = %s', (hazard_id,))
    conn.commit()
    conn.close()

def delete_uploaded_image(image_path):
    """Delete an uploaded image file"""
    try:
        if image_path:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
    except Exception as e:
        print(f"Error deleting image file: {str(e)}")
    return False

@app.route('/report', methods=['POST'])
def report_hazard():
    try:
        description = request.form.get('description')
        lat = float(request.form.get('lat'))
        lng = float(request.form.get('lng'))
        reporter = request.form.get('username') or request.form.get('uname')

        # Handle image upload
        image_path = None
        roboflow_verified = False
        is_road = False
        prediction_class = None
        roboflow_confidence = 0.0
        roboflow_details = {}

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_path = filename
                
                # Verify hazard using Roboflow API - REQUIRED for all images
                print(f"Verifying image: {image_path} for user: {reporter}")
                roboflow_verified, is_road, prediction_class, roboflow_confidence, roboflow_details = verify_hazard_with_roboflow(image_path)
                
                # If prediction is "road", delete the image and reject the report
                if is_road:
                    print(f"Image {image_path} rejected: Detected as road")
                    delete_uploaded_image(image_path)
                    return jsonify({
                        'error': 'Invalid image: This appears to be a regular road image without a hazard. Please upload an image showing an actual hazard (pothole, flood, debris, etc.).',
                        'rejected': True,
                        'prediction_class': prediction_class,
                        'roboflow_verification': {
                            'is_hazard': False,
                            'is_road': True,
                            'prediction_class': prediction_class,
                            'confidence': roboflow_confidence,
                            'details': roboflow_details
                        }
                    }), 400
                else:
                    print(f"Image {image_path} accepted: Not detected as road (class: {prediction_class})")
        else:
            # No image provided - accept the report but mark as unverified
            print("Warning: No image provided with hazard report")

        # Determine if hazard should be verified
        # Verified if Roboflow confirms it's a hazard OR if there are nearby hazards
        verified = roboflow_verified

        # Insert new hazard with verification status
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            '''
            INSERT INTO hazards (description, lat, lng, image_path, reported_by, verified)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''',
            (description, lat, lng, image_path, reporter, 1 if verified else 0)
        )
        new_hazard_id = c.lastrowid

        # Update reporter hazard count
        if reporter:
            c.execute('UPDATE users SET hazards = hazards + 1 WHERE uname = %s', (reporter,))
            if verified:
                c.execute('UPDATE users SET verified = verified + 1 WHERE uname = %s', (reporter,))

        conn.commit()
        conn.close()

        # Check for nearby hazards (additional verification method)
        nearby_hazards = check_nearby_hazards(lat, lng)

        # Also verify if there are multiple nearby hazards
        if len(nearby_hazards) > 1:  # More than just the current hazard
            mark_as_verified(nearby_hazards)
            verified = True

        return jsonify({
            'message': 'Hazard reported successfully!',
            'verified': verified,
            'id': new_hazard_id,
            'roboflow_verification': {
                'is_hazard': roboflow_verified,
                'is_road': is_road,
                'prediction_class': prediction_class,
                'confidence': roboflow_confidence,
                'details': roboflow_details
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/hazards', methods=['GET'])
def get_hazards():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT id, description, lat, lng, image_path, verified FROM hazards WHERE verified = 1')
        hazards = c.fetchall()
        conn.close()

        result = []
        for hazard in hazards:
            hazard_dict = {
                'id': hazard[0],
                'description': hazard[1],
                'lat': hazard[2],
                'lng': hazard[3],
                'image_url': f'http://127.0.0.1:5000/uploads/{hazard[4]}' if hazard[4] else None,
                'verified': bool(hazard[5])
            }
            result.append(hazard_dict)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/admin/stats', methods=['GET'])
def get_admin_stats():
    """
    Get statistics for admin dashboard
    Returns stats for: 1 day, 1 week, 1 month, 1 year
    Shows total reports and verified vs unverified counts
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()

        stats = {}
        time_periods = {
            'day': 1,
            'week': 7,
            'month': 30,
            'year': 365
        }

        for period_name, days in time_periods.items():
            # Get total reports in the period
            c.execute(
                '''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified,
                    SUM(CASE WHEN verified = 0 THEN 1 ELSE 0 END) as unverified
                FROM hazards
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                ''',
                (days,)
            )
            result = c.fetchone()

            stats[period_name] = {
                'total': result[0] or 0,
                'verified': result[1] or 0,
                'unverified': result[2] or 0,
                'days': days
            }

        # Get overall statistics (all time)
        c.execute(
            '''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified,
                SUM(CASE WHEN verified = 0 THEN 1 ELSE 0 END) as unverified
            FROM hazards
            '''
        )
        overall = c.fetchone()
        stats['all_time'] = {
            'total': overall[0] or 0,
            'verified': overall[1] or 0,
            'unverified': overall[2] or 0
        }

        conn.close()

        return jsonify(stats), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400

# ============== AUTH ENDPOINTS ==============
# Register a new user: expects uname, password, email (form or JSON)
@app.route('/register', methods=['POST'])
def register():
    try:
        payload = request.get_json(silent=True) or request.form
        uname = payload.get('uname') or payload.get('username')
        password = payload.get('password')
        email = payload.get('email')

        if not uname or not password or not email:
            return jsonify({'error': 'uname, password and email are required'}), 400

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'INSERT INTO users (uname, password, email, admins) VALUES (%s, %s, %s, %s)',
            (uname, password, email, 0)
        )
        conn.commit()
        conn.close()
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Login: expects uname and password (form or JSON)
@app.route('/login', methods=['POST'])
def login():
    try:
        payload = request.get_json(silent=True) or request.form
        uname = payload.get('uname')
        password = payload.get('password')

        if not uname or not password:
            return jsonify({'error': 'uname and password are required'}), 400

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'SELECT uname, admins FROM users WHERE uname = %s AND password = %s LIMIT 1',
            (uname, password)
        )
        row = c.fetchone()
        conn.close()

        if row:
            is_admin = bool(row[1] if len(row) > 1 else 0)
            return jsonify({
                'message': 'Login successful',
                'uname': row[0],
                'is_admin': is_admin
            }), 200
        return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/test-roboflow', methods=['POST'])
def test_roboflow():
    """Test endpoint to debug Roboflow API response"""
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Test the verification
            is_hazard, is_road, pred_class, confidence, details = verify_hazard_with_roboflow(filename)
            
            # Clean up test file
            try:
                os.remove(filepath)
            except:
                pass
            
            return jsonify({
                'is_hazard': is_hazard,
                'is_road': is_road,
                'prediction_class': pred_class,
                'confidence': confidence,
                'raw_response': details
            }), 200
        else:
            return jsonify({'error': 'Invalid file'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)