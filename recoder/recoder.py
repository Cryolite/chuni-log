# -*- coding: utf-8 -*-

import __builtin__
import os
import sys
import stat
import re
import httplib2
import json
import logging
from datetime import datetime as dt

from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from apiclient import discovery

CONFIG_DIR_BASENAME = '.chuni-log'
CLIENT_ID = '210659263154-b4o2ugo23l2dg4u13aet6tc4qf6dhkdr.apps.googleusercontent.com'
CLIENT_SECRET = 'dE5k3LNLjfQTlLi_nyTd5bd8'
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
CREDENTIALS_PATH_BASENAME = 'credentials.json'
CONFIG_FILE_BASENAME = 'config.json'


def verifyFilePermission(path, octal_notation):
    if os.path.isdir(path):
        raise IOError('{0} is a directory.'.format(path))
    elif os.path.islink(path):
        raise IOError('{0} is a symbolic link.'.format(path))
    elif os.path.isfile(path):
        if oct(stat.S_IMODE(os.stat(path).st_mode)) != octal_notation:
            raise AssertionError
    else:
        raise AssertionError

def makeConfigDir():
    home_dir = os.path.expanduser('~')
    config_dir = os.path.join(home_dir, CONFIG_DIR_BASENAME)
    if os.path.isfile(config_dir):
        raise IOError('{0} is a file.'.format(config_dir))
    elif os.path.islink(config_dir):
        raise IOError('{0} is a symbolic link.'.format(config_dir))
    elif os.path.isdir(config_dir):
        return config_dir
    elif os.path.exists(config_dir):
        raise IOError('An unknown IO error.')
    os.makedirs(config_dir)
    return config_dir

def createConfigFileIfNeeded():
    config_dir = makeConfigDir()
    config_path = os.path.join(config_dir, CONFIG_FILE_BASENAME)

    if os.path.isdir(config_path):
        raise IOError('{0} is a directory.'.format(config_path))
    elif os.path.islink(config_path):
        raise IOError('{0} is a symbolic link.'.format(config_path))

    if not os.path.exists(config_path):
        old_umask = os.umask(0o177)
        try:
            with open(config_path, 'w') as f:
                f.write('{}')
        finally:
            os.umask(old_umask)

    verifyFilePermission(config_path, '0600')
    return config_path

def getCredentials():
    config_dir = makeConfigDir()
    credentials_path = os.path.join(config_dir, CREDENTIALS_PATH_BASENAME)

    storage = Storage(credentials_path)
    # `credentials_path` にファイルが無い場合，
    # `oauth2client.file.Storage.get` は None を返す．
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        flow = OAuth2WebServerFlow(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scope=SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob')
        url = flow.step1_get_authorize_url('urn:ietf:wg:oauth:2.0:oob')

        print
        print '以下の URL から許可コードを取得して入力してください。'
        print url
        print
        auth_code = raw_input('許可コード: ').strip()

        credentials = flow.step2_exchange(auth_code)
        storage.put(credentials)
        print
        print '認証情報が {0} に保存されました。'.format(credentials_path)
        print 'このファイルに含まれる情報は他人に知られないようにしてください。'
        print

    verifyFilePermission(credentials_path, '0600')

    return credentials

def verifySpreadsheetId(service, spreadsheet_id):
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

def getSpreadsheetId(service):
    config_path = createConfigFileIfNeeded()

    with open(config_path, 'r') as f:
        config = json.load(f)

    if 'spreadsheetId' not in config:
        yes_or_no = ''
        while len(yes_or_no) == 0 or yes_or_no[0] not in ('y', 'n'):
            yes_or_no = raw_input('スプレッドシートを新規作成しますか？ [y/n]: ').strip()
        if yes_or_no[0] == 'y':
            title = raw_input('作成するスプレッドシートのタイトルを入力してください。(CHUNI-LOG): ').strip()
            if not title:
                title = 'CHUNI-LOG'
            spreadsheet = service.spreadsheets().create(
                body={
                       'properties': {
                         'title': title,
                         'locale': 'ja',
                         'timeZone': 'Asia/Tokyo',
                       }
                     }).execute()
            spreadsheet_id = spreadsheet['spreadsheetId']
        elif yes_or_no[0] == 'n':
            spreadsheet_id = raw_input('スプレッドシート ID を入力してください。: ').strip()
        else:
            raise AssertionError
        config['spreadsheetId'] = spreadsheet_id
        with open(config_path, 'w') as f:
            json.dump(config, f)
        with open(config_path, 'r') as f:
            config = json.load(f)

    spreadsheet_id = config['spreadsheetId']
    if not isinstance(spreadsheet_id, unicode):
        raise AssertionError

    verifySpreadsheetId(service, spreadsheet_id)
    return spreadsheet_id

def verifySheetIdOrName(service, spreadsheet_id, sheet_id_or_name):
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet['sheets']:
        properties = sheet['properties']
        if re.compile(u'[0-9]+$').match(sheet_id_or_name) and properties['sheetId'] == int(sheet_id_or_name):
            return properties['title']
        if properties['title'] == sheet_id_or_name:
            return properties['title']
    raise AssertionError

def verifySheetName(service, spreadsheet_id, sheet_name):
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet['sheets']:
        properties = sheet['properties']
        if properties['title'] == sheet_name:
            return
    raise AssertionError

def getSheetName(service, spreadsheet_id):
    config_path = createConfigFileIfNeeded()

    with open(config_path, 'r') as f:
        config = json.load(f)

    if 'sheetName' not in config:
        sheet_id_or_name = raw_input('シート ID またはシート名を入力してください。(0): ' ).strip()
        if sheet_id_or_name:
            sheet_name = verifySheetIdOrName(service, spreadsheet_id, sheet_id_or_name)
        else:
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = spreadsheet['sheets']
            if len(sheets) == 0:
                raise AssertionError
            sheet = sheets[0]
            sheet_properties = sheet['properties']
            sheet_name = sheet_properties['title']
        config['sheetName'] = sheet_name
        with open(config_path, 'w') as f:
            json.dump(config, f)
        with open(config_path, 'r') as f:
            config = json.load(f)

    sheet_name = config['sheetName']
    if not isinstance(sheet_name, unicode):
        raise AssertionError

    verifySheetName(service, spreadsheet_id, sheet_name)
    return sheet_name

def getSheetIdByName(service, spreadsheet_id, sheet_name):
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in spreadsheet['sheets']:
        properties = sheet['properties']
        if properties['title'] == sheet_name:
            return properties['sheetId']
    raise AssertionError

def getTracks(last_date):
    with open(u'data.json', u'r') as f:
        data = json.load(f)
    tracks = data[u'tracks']
    tracks.sort(
        key=lambda track: dt.strptime(track[u'date'], u'%Y-%m-%d %H:%M'),
        reverse=True)
    track = tracks.pop(0)
    date = track[u'date']
    date = dt.strptime(date, u'%Y-%m-%d %H:%M')
    if date <= last_date:
        return []
    user_data = data[u'user_data']
    values = [
        [
            date.strftime(u'%Y/%m/%d %H:%M:%S'),
            track[u'track_number'],
            track[u'track_level'],
            track[u'title'],
            track[u'score'],
            track[u'new_record'],
            track[u'store_name'],
            track[u'character_name'],
            track[u'skill_name'],
            track[u'skill_grade'],
            track[u'skill_result'],
            track[u'max_combo'],
            track[u'justice_critical'],
            track[u'justice'],
            track[u'attack'],
            track[u'miss'],
            track[u'tap'],
            track[u'hold'],
            track[u'slide'],
            track[u'air'],
            track[u'flick'],
            user_data[u'lv'],
            user_data[u'rating'],
            user_data[u'mile'],
            user_data[u'total_mile'],
            user_data[u'play_count']
        ]
    ]
    for track in tracks:
        date = track[u'date']
        date = dt.strptime(date, u'%Y-%m-%d %H:%M')
        if date <= last_date:
            break
        value = [
            date.strftime(u'%Y/%m/%d %H:%M:%S'),
            track[u'track_number'],
            track[u'track_level'],
            track[u'title'],
            track[u'score'],
            track[u'new_record'],
            track[u'store_name'],
            track[u'character_name'],
            track[u'skill_name'],
            track[u'skill_grade'],
            track[u'skill_result'],
            track[u'max_combo'],
            track[u'justice_critical'],
            track[u'justice'],
            track[u'attack'],
            track[u'miss'],
            track[u'tap'],
            track[u'hold'],
            track[u'slide'],
            track[u'air'],
            track[u'flick'],
            u'', # level
            u'', # rating
            u'', # mile
            u'', # total_mile
            u''  # play_count
        ]
        values.append(value)
    return values

def setColumnFormats(service, spreadsheet_id, sheet_id, column_formats):
    requests = []
    for column_format in column_formats:
        if len(column_format) != 3:
            raise ValueError
        column_index = column_format[0]
        if not isinstance(column_index, int):
            raise TypeError
        if column_index < 0:
            raise ValueError
        format_type = column_format[1]
        if not isinstance(format_type, (str, unicode)):
            raise TypeError
        if format_type not in ('NUMBER', u'NUMBER', 'PERCENT', u'PERCENT', 'DATE_TIME', u'DATE_TIME'):
            raise ValueError
        pattern = column_format[2]
        if not isinstance(pattern, (str, unicode)):
            raise TypeError
        if pattern:
            requests.append(
                {
                  'repeatCell': {
                    'range': {
                      'sheetId': sheet_id,
                      'startRowIndex': 0,
                      'startColumnIndex': column_index,
                      'endColumnIndex': column_index + 1
                    },
                    'cell': {
                      'userEnteredFormat': {
                        'numberFormat': {
                          'type': format_type,
                          'pattern': pattern
                        }
                      }
                    },
                    'fields': 'userEnteredFormat.numberFormat'
                  }
                })
        else:
            requests.append(
                {
                  'repeatCell': {
                    'range': {
                      'sheetId': sheet_id,
                      'startRowIndex': 0,
                      'startColumnIndex': column_index,
                      'endColumnIndex': column_index + 1
                    },
                    'cell': {
                      'userEnteredFormat': {
                        'numberFormat': {
                          'type': format_type
                        }
                      }
                    },
                    'fields': 'userEnteredFormat.numberFormat'
                  }
                })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': requests}).execute()

def main():
    credentials = getCredentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    spreadsheet_id = getSpreadsheetId(service)

    sheet_name = getSheetName(service, spreadsheet_id)
    sheet_id = getSheetIdByName(service, spreadsheet_id, sheet_name)

    setColumnFormats(
        service,
        spreadsheet_id,
        sheet_id,
        [(0, 'DATE_TIME', 'yyyy/mm/dd hh:mm:ss'),
         (1, 'NUMBER', '0'),
         (4, 'NUMBER', '####,##0'),
         (5, 'NUMBER', '0'),
         (9, 'NUMBER', '#0'),
         (10, 'NUMBER', '##,##0'),
         (11, 'NUMBER', '#,##0'),
         (12, 'NUMBER', '#,##0'),
         (13, 'NUMBER', '#,##0'),
         (14, 'NUMBER', '#,##0'),
         (15, 'NUMBER', '#,##0'),
         (16, 'PERCENT', '##0.00%'),
         (17, 'PERCENT', '##0.00%'),
         (18, 'PERCENT', '##0.00%'),
         (19, 'PERCENT', '##0.00%'),
         (20, 'PERCENT', '##0.00%'),
         (21, 'NUMBER', '##0'),
         (22, 'NUMBER', '#0.00'),
         (23, 'NUMBER', '#####,##0'),
         (24, 'NUMBER', '#####,##0'),
         (25, 'NUMBER', '####0')])

    range = u'{0}!A:A'.format(sheet_name)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range,
        majorDimension=u'ROWS',
        dateTimeRenderOption=u'FORMATTED_STRING').execute()
    dates = result.get('values', [])
    if not dates:
        last_date = dt.strptime('2000/01/01 00:00:00', '%Y/%m/%d %H:%M:%S')
    else:
        for i in __builtin__.range(len(dates)):
            if len(dates[i]) != 1:
                raise AssertionError
            dates[i] = dates[i][0]
            dates[i] = dt.strptime(dates[i], '%Y/%m/%d %H:%M:%S')
        dates.sort(reverse=True)
        last_date = dates[0]

    range = u'{0}!A1'.format(sheet_name)
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

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
               'requests': [
                 # {
                 #   'autoResizeDimensions': {
                 #     'dimensions': {
                 #       'sheetId': sheet_id,
                 #       'dimension': 'COLUMNS',
                 #     }
                 #   }
                 # },
                 {
                   'sortRange': {
                     'range': {
                       'sheetId': sheet_id
                     },
                     'sortSpecs': [
                       {
                         'dimensionIndex': 0,
                         'sortOrder': 'DESCENDING'
                       }
                     ]
                   }
                 }
               ]
             }).execute()

if __name__ == '__main__':
    try:
        main()
        logging.info(u'Finish recording.')
    except:
        logging.exception(u'A fatal exception is thrown.')
        raise
    sys.exit(0)
