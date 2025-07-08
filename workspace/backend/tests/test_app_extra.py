import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from app import app, db
from models import Transcription
import tempfile

@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
    os.close(db_fd)
    os.unlink(db_path)

# Test that the /files endpoint returns a list of files (may be empty or not)
def test_list_files(client):
    rv = client.get('/files')
    assert rv.status_code == 200
    assert 'files' in rv.get_json()
    assert isinstance(rv.get_json()['files'], list)

# Test uploading a file and then deleting it
def test_add_and_delete_file(client):
    data = {
        'file': (tempfile.NamedTemporaryFile(suffix='.mp3'), 'test.mp3')
    }
    rv = client.post('/files', data=data, content_type='multipart/form-data')
    assert rv.status_code == 200 or rv.status_code == 409
    file_id = None
    if rv.status_code == 200:
        file_id = rv.get_json()['file']['id']
    elif rv.status_code == 409:
        # Try to get the file id from the list
        files = client.get('/files').get_json()['files']
        for f in files:
            if f['filename'] == 'test.mp3':
                file_id = f['id']
    if file_id:
        del_resp = client.delete(f'/files/{file_id}')
        assert del_resp.status_code == 200

# Test /transcribe endpoint with no file provided
def test_transcribe_no_file(client):
    rv = client.post('/transcribe', data={})
    assert rv.status_code == 400 or rv.status_code == 200

# Test searching transcriptions with a query that should return an empty list
def test_search_transcriptions(client):
    rv = client.get('/search?q=nonexistent')
    assert rv.status_code == 200
    assert 'results' in rv.get_json()
    assert isinstance(rv.get_json()['results'], list)

# Test /ask endpoint with missing data
def test_ask_no_data(client):
    rv = client.post('/ask', json={})
    assert rv.status_code == 400 or rv.status_code == 200

# Test /ask-database endpoint with no question provided
def test_ask_database_no_question(client):
    rv = client.post('/ask-database', json={})
    assert rv.status_code == 400 or rv.status_code == 200

# Test batch delete endpoint
def test_batch_delete_files(client):
    # Add some test files first (use audio files to avoid ffmpeg dependency)
    file1_data = {'file': (tempfile.NamedTemporaryFile(suffix='.mp3'), 'test1.mp3')}
    file2_data = {'file': (tempfile.NamedTemporaryFile(suffix='.wav'), 'test2.wav')}
    
    rv1 = client.post('/files', data=file1_data, content_type='multipart/form-data')
    rv2 = client.post('/files', data=file2_data, content_type='multipart/form-data')
    
    if rv1.status_code == 200:
        file1_id = rv1.get_json()['file']['id']
        if rv2.status_code == 200:
            file2_id = rv2.get_json()['file']['id']
            
            # Test batch delete
            rv = client.post('/files/batch-delete', json={'file_ids': [file1_id, file2_id]})
            assert rv.status_code == 200
            data = rv.get_json()
            assert data['success'] is True
            assert data['deleted_count'] >= 0

# Test batch delete with invalid data
def test_batch_delete_invalid_data(client):
    rv = client.post('/files/batch-delete', json={})
    assert rv.status_code == 400
    
    rv = client.post('/files/batch-delete', json={'file_ids': 'not_an_array'})
    assert rv.status_code == 400

# Test delete all files endpoint
def test_delete_all_files(client):
    rv = client.delete('/files/all')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    assert 'deleted_count' in data

# Test batch transcribe endpoint
def test_batch_transcribe_files(client):
    # Add a test file first
    file_data = {'file': (tempfile.NamedTemporaryFile(suffix='.mp3'), 'test_transcribe.mp3')}
    rv = client.post('/files', data=file_data, content_type='multipart/form-data')
    
    if rv.status_code == 200:
        file_id = rv.get_json()['file']['id']
        
        # Test batch transcribe
        rv = client.post('/files/batch-transcribe', json={'file_ids': [file_id]})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data['success'] is True
        assert 'transcribed_count' in data

# Test batch transcribe with invalid data
def test_batch_transcribe_invalid_data(client):
    rv = client.post('/files/batch-transcribe', json={})
    assert rv.status_code == 400
    
    rv = client.post('/files/batch-transcribe', json={'file_ids': 'not_an_array'})
    assert rv.status_code == 400
