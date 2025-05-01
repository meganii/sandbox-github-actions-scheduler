import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

scopes = ["https://www.googleapis.com/auth/drive"]

crds, prj = google.auth.default(scopes)
service = build("drive", "v3", credentials=crds)

file_id = '1PiukFFc-Jgwst5lGzhmy-Fvg1yLyghi9'
file_name = 'data/data.json'
file = service.files().get(fileId=file_id).execute()
media_body = MediaFileUpload(file_name, mimetype=file['mimeType'], resumable=True)
updated_file = service.files().update(
        fileId=file_id,
        media_body=media_body).execute()
print(updated_file)