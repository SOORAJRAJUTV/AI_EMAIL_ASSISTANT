from google_auth_oauthlib.flow import InstalledAppFlow
import webbrowser
import sys

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar"
]

def main():
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', 
            SCOPES,
            redirect_uri='http://localhost:8080'
        )
        
        # Force using the test email
        creds = flow.run_local_server(
            port=8080,
            authorization_prompt_message='Please visit this URL: {url}',
            success_message='Auth complete! You may close this window.',
            login_hint='emailfortest444@gmail.com'  # Force this email
        )

        print("\nAuthentication successful!")
        print("Access Token:", creds.token)
        print("Refresh Token:", creds.refresh_token)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Make sure 'emailfortest444@gmail.com' is added as a test user")
        print("2. Verify redirect_uri in Google Cloud Console matches http://localhost:8080")
        print("3. Try in incognito mode or clear browser cache")
        sys.exit(1)

if __name__ == "__main__":
    main()

