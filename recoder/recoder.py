import __builtin__
import sys
import httplib2
import os
import json
import logging
from datetime import datetime as dt

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/sheets.googleapis.com-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'CHUNI-LOG'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.chuni-log')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'credential.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def getSpreadsheetId():
    home_dir = os.path.expanduser('~')
    config_dir = os.path.join(home_dir, '.chuni-log')
    if not os.path.exists(config_dir):
        raise AssertionError
    config_path = os.path.join(config_dir, 'config.json')

    with open(config_path, 'r') as f:
        config = json.load(f)

    spreadsheet_id = config['spreadsheet id']
    if not isinstance(spreadsheet_id, unicode):
        raise AssertionError

    return spreadsheet_id.encode()

def getTracks(last_date):
    with open('tracks.json', 'r') as f:
        tracks = json.load(f)
    values = []
    for track in tracks:
        date = track['date']
        date = dt.strptime(date, '%Y-%m-%d %H:%M')
        if date <= last_date:
            continue
        value = [
            track['date'],
            track['track number'],
            track['track level'],
            track['title'],
            track['score'],
            track['new record'],
            track['store'],
            track['character name'],
            track['skill name'],
            track['skill value'],
            track['skill effect'],
            track['max combo'],
            track['justice critical'],
            track['justice'],
            track['attack'],
            track['miss'],
            track['tap'],
            track['hold'],
            track['slide'],
            track['air'],
            track['flick'],
            track['player level'],
            track['rating'],
            track['mile'],
            track['total mile'],
            track['play count']
        ]
        values.append(value)
    return values

def main():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    spreadsheet_id = getSpreadsheetId()

    range = 'Sheet1!A:A'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range,
        majorDimension='ROWS',
        dateTimeRenderOption='FORMATTED_STRING').execute()
    dates = result.get('values', [])
    if not dates:
        last_date = dt.strptime('2000/1/1 0:00:00', '%Y/%m/%d %H:%M:%S')
    else:
        if len(dates) == 0:
            raise AssertionError
        for i in __builtin__.range(len(dates)):
            if len(dates[i]) != 1:
                raise AssertionError
            dates[i] = dates[i][0]
            dates[i] = dt.strptime(dates[i], '%Y/%m/%d %H:%M:%S')
        dates.sort(reverse=True)
        last_date = dates[0]

    range = 'Sheet1!A1'
    value_input_option = 'USER_ENTERED'
    insert_data_option = 'INSERT_ROWS'
    values = getTracks(last_date)
    body = {
        'values': values
    }
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range,
        valueInputOption=value_input_option,
        insertDataOption=insert_data_option,
        body=body).execute()

if __name__ == '__main__':
    try:
        main()
        logging.info(u'Finish recording.')
    except:
        logging.exception(u'A fatal exception is thrown.')
        raise
    sys.exit(0)
