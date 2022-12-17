import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

scopes = ["https://www.googleapis.com/auth/drive"]

crds, prj = google.auth.default(scopes)
service = build("drive", "v3", credentials=crds)

parents_id = '1p1sw8iPuKMGpSY4B-kiJ0wpkCgRgQ8rI'
file_name = 'test.json'
file_metadata = {'name': file_name, 'parents': [parents_id]}
media = MediaFileUpload(file_name, mimetype='application/json', resumable=True)
file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

result = service.files().list().execute()
print(result)