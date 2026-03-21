import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            flow.redirect_uri = 'http://localhost:8080/'
            auth_url, _ = flow.authorization_url(prompt='consent')
            print("【初回のみ】URLを開いて許可し、エラー画面のURLをコピーしてください:")
            print(auth_url)
            redirect_response = input('\nここにコピーしたURLを貼り付けてEnter: ')
            flow.fetch_token(authorization_response=redirect_response.strip())
            creds = flow.credentials
            
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # 最新10件を取得
        response = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = response.get('messages', [])

        if not messages:
            print("メッセージが見つかりません。")
            return

        print("\n最新10件のメール:\n" + "="*40)
        for i, msg in enumerate(messages, 1):
            msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            
            headers = msg_detail.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "件名なし")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "不明")
            date = next((h['value'] for h in headers if h['name'] == 'Date'), "不明")
            snippet = msg_detail.get('snippet', '')
            
            print(f"[{i}件目]")
            print(f"日付: {date}")
            print(f"送信元: {sender}")
            print(f"件名: {subject}")
            print(f"本文一部: {snippet}")
            print("-" * 40)

    except Exception as error:
        print(f'エラーが発生しました: {error}')

if __name__ == '__main__':
    main()