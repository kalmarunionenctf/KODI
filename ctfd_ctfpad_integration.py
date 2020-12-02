import os
from datetime import datetime
import requests
from threading import Thread, Event
from dotenv import load_dotenv
from requests_pkcs12 import Pkcs12Adapter

load_dotenv()
CTFPAD_URL = os.getenv('CTFPAD_URL')
ETHERPAD_URL = os.getenv('ETHERPAD_URL')
CTFPAD_API_KEY = os.getenv('CTFPAD_API_KEY')
ETHERPAD_API_KEY = os.getenv('ETHERPAD_API_KEY')
ETHERPAD_USER = os.getenv('ETHERPAD_USER')
ETHERPAD_PASS = os.getenv('ETHERPAD_PASS')
DELAY = 60


class InvalidAPIKey(Exception):
    pass


class CTFdCTFPadIntegration():
    ctf_name: str
    ctfd_api_key: str
    ctfd_url: str
    ctfpad_url: str
    etherpad_url: str
    ctfd_session: requests.Session
    ctfpad_session: requests.Session
    etherpad_session: requests.Session
    ctfpad_ctf: object
    discord_integration = None
    ctfd_ctfpad_thread: Thread
    refresh_interval: int
    refreshes_left = float('inf')
    start_time = datetime.max
    exit = Event()

    def __init__(self, discord_integration, ctf_name, ctfd_url=None, ctfd_api_key=None, refresh_interval=None, max_refresh=None, start_time=None):
        self.ctf_name = ctf_name
        self.ctfd_url = ctfd_url
        self.ctfd_api_key = ctfd_api_key
        if refresh_interval:
            self.refresh_interval = refresh_interval
        if max_refresh:
            self.refreshes_left = max_refresh
        if start_time:
            self.start_time = start_time

        if self.ctfd_url != None and self.ctfd_api_key != None:
            self.ctfd_session = requests.session()
            self.ctfd_session.headers = {
                'Content-Type': 'application/json',
                'Authorization': 'token ' + self.ctfd_api_key
            }

        self.ctfpad_session = requests.session()
        self.ctfpad_session.headers = {
            "X-Apikey": CTFPAD_API_KEY
        }

        self.ctfpad_url = CTFPAD_URL
        self.ctfpad_session.mount(self.ctfpad_url, Pkcs12Adapter(
            pkcs12_filename='user.pfx', pkcs12_password=''))

        try:
            ctfpad_ctfs = self.ctfpad_session.get(
                f'{self.ctfpad_url}/ctfs').json()['ctfs']
        except:
            raise ConnectionError(
                f'Could not connect to CTFPad on {self.ctfpad_url}. Please verify URL and token.')

        self.etherpad_session = requests.session()

        self.etherpad_url = ETHERPAD_URL
        self.etherpad_session.mount(self.ctfpad_url, Pkcs12Adapter(
            pkcs12_filename='user.pfx', pkcs12_password=''))
        self.etherpad_session.params['apikey'] = ETHERPAD_API_KEY

        try:
            self.etherpad_session.post(
                f'{self.ctfpad_url}/login', data={'name': ETHERPAD_USER, 'password': ETHERPAD_PASS})
        except:
            raise ConnectionError(
                f'Could not get session token from Etherpad-Lite on {self.etherpad_url}. Please verify bot credentials.')

        self.ctfpad_ctf = next((
            ctfd_challenge for ctfd_challenge in ctfpad_ctfs if ctfd_challenge['name'].lower() == self.ctf_name.lower()), None)

        if not self.ctfpad_ctf:
            try:
                self.ctfpad_ctf = self.ctfpad_session.post(
                    f'{self.ctfpad_url}/ctfs', json={"name": f"{self.ctf_name}"}).json()['ctf']
            except:
                raise ConnectionError(
                    f'Could not create pad with name "{self.ctf_name}" on {self.ctfpad_url}. Please verify token access rights.')

        self.discord_integration = discord_integration

        self.ctfd_ctfpad_thread = Thread(target=self.ctfd_ctfpad_integration)
        self.ctfd_ctfpad_thread.start()

    def __del__(self):
        self.exit.set()
        self.ctfd_ctfpad_thread.join()

    def get_ctfd_challenges(self):
        ctfd_response = self.ctfd_session.get(
            f"{self.ctfd_url}/api/v1/challenges").json()

        if 'message' in ctfd_response and ctfd_response['message'] == "The server could not verify that you are authorized to access the URL requested. You either supplied the wrong credentials (e.g. a bad password), or your browser doesn't understand how to supply the credentials required.":
            self.discord_integration.send_to_integration_channel(
                self, 'CTFd bot token not valid. Set credentials with `>ctf setcreds "token"`.')
            return None

        return ctfd_response['data']

    def submit_flag(self, flag, challenge_name):
        print(f'Looking for "{flag}" in "{challenge_name}"')
        ctfd_challenges = self.get_ctfd_challenges()

        filtered_ctfd_challenges = [
            c for c in ctfd_challenges if challenge_name == None or c['name'].lower() == challenge_name.lower()]

        challenge_responses = {}
        for challenge in filtered_ctfd_challenges:
            print(f'Trying "{flag}" against challenge "{challenge["name"]}"')
            body = {'challenge_id': challenge['id'], 'submission': flag}
            ctfd_attempt = self.ctfd_session.post(
                f'{self.ctfd_url}/api/v1/challenges/attempt', json=body).json()['data']
            challenge_responses[challenge['name']] = ctfd_attempt
            if ctfd_attempt['status'] == 'correct':
                return (True, challenge_responses)
        return (False, challenge_responses)

    def ctfpad_set_description(self, challenge_id, description):
        try:
            self.etherpad_session.get(
                f'{self.etherpad_url}/api/1/setText', params={'padID': challenge_id, 'text': description})
        except:
            raise requests.RequestException(
                f'Could not connect to Etherpad-Lite on {self.etherpad_url}. Please verify URL and token.')

    def ctfd_ctfpad_integration(self):
        if self.ctfd_session == None:
            return
        while not self.exit.is_set() and self.refreshes_left:
            if datetime.now() > self.start_time:
                self.refreshes_left -= 1
                ctfpad_challenges = self.ctfpad_session.get(
                    f'{self.ctfpad_url}/ctfs/{self.ctfpad_ctf["id"]}/challenges').json()['challenges']

                ctfd_challenges = self.get_ctfd_challenges()
                if ctfd_challenges == None:
                    break

                new_challenges = [challenge for challenge in ctfd_challenges if not any(
                    challenge['name'] == ctfpad_challenge['title'] for ctfpad_challenge in ctfpad_challenges)]
                if new_challenges:
                    self.discord_integration.send_to_integration_channel(
                        self, f'{len(new_challenges)} new CTFd challenges added!')
                    for new_challenge in new_challenges:
                        ctfd_challenge = self.ctfd_session.get(
                            f'{self.ctfd_url}/api/v1/challenges/{new_challenge["id"]}').json()

                        ctfd_challenge_data = ctfd_challenge['data']

                        body = {"challenge": {
                            "title": ctfd_challenge_data['name'], "category": ctfd_challenge_data['category'], "points": ctfd_challenge_data["value"]}}
                        ctfpad_challenge = self.ctfpad_session.post(
                            f'{self.ctfpad_url}/ctfs/{self.ctfpad_ctf["id"]}/challenges', json=body).json()['challenge']
                        self.ctfpad_set_description(
                            ctfpad_challenge.id, ctfd_challenge_data.description)

                        self.discord_integration.add_challenge_to_integration_ctf(
                            self, ctfd_challenge_data['name'], ctfd_challenge_data['category'])

                        if ctfd_challenge_data['files']:
                            files = {'files': self.ctfd_session.get(
                                f'{self.ctfd_url}/{ctfd_challenge_data["files"][0]}').content}
                            self.ctfpad_session.post(
                                f'{self.ctfpad_url}/challenges/{ctfpad_challenge["id"]}/files', files=files)

                team_solves = self.ctfd_session.get(
                    f"{self.ctfd_url}/api/v1/teams/me/solves").json()['data']

                for solved_challenge in team_solves:
                    if solved_challenge['type'] == 'correct':
                        for ctfpad_challenge in ctfpad_challenges:
                            if solved_challenge['challenge']['name'] == ctfpad_challenge['title']:
                                if not ctfpad_challenge["done"]:
                                    self.discord_integration.send_to_integration_channel(
                                        self, f'{solved_challenge["user"]} just finished "{solved_challenge["challenge"]["name"]}" in {solved_challenge["challenge"]["category"]}!')
                                    self.ctfpad_session.put(
                                        f'{self.ctfpad_url}/challenges/{ctfpad_challenge["id"]}/done')

            self.exit.wait(self.refresh_interval)


if __name__ == '__main__':
    test = CTFdCTFPadIntegration(None, 'test')
