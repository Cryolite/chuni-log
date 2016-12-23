# -*- coding: utf-8 -*-

import os
import stat


CONFIG_DIR_BASENAME = '.chuni-log'
CONFIG_FILE_BASENAME = 'config.json'

class UserInputRequiredError(StandardError):
    pass

class StaleCredentialsError(StandardError):
    pass

def makeConfigDir():
    home_dir = os.path.expanduser('~')
    config_dir = os.path.join(home_dir, CONFIG_DIR_BASENAME)
    if os.path.isfile(config_dir):
        raise IOError('{0} はファイルです。'.format(config_dir))
    elif os.path.islink(config_dir):
        raise IOError('{0} はシンボリックリンクです。'.format(config_dir))
    elif os.path.isdir(config_dir):
        return config_dir
    elif os.path.exists(config_dir):
        raise IOError('未知の入出力エラーです。')
    os.makedirs(config_dir, 0700)
    return config_dir

def assertFilePermission(path, mode):
    if os.path.isdir(path):
        raise IOError('{0} はディレクトリです。'.format(path))
    elif os.path.islink(path):
        raise IOError('{0} はシンボリックリンクです。'.format(path))
    elif os.path.isfile(path):
        if stat.S_IMODE(os.stat(path).st_mode) != mode:
            os.remove(path)
            raise IOError(
                'ファイル {0} のアクセス権限が {1} に設定されていますが'
                'これは不正です。安全のため，ファイル {0} は削除されます。'
                .format(path, oct(mode)))
    else:
        raise IOError('未知の入出力エラーです。')

def createConfigFileIfNeeded():
    config_dir = makeConfigDir()
    config_path = os.path.join(config_dir, CONFIG_FILE_BASENAME)

    if os.path.isdir(config_path):
        raise IOError('{0} はディレクトリです。'.format(config_path))
    elif os.path.islink(config_path):
        raise IOError('{0} はシンボリックリンクです。'.format(config_path))

    if not os.path.exists(config_path):
        old_umask = os.umask(0o177)
        try:
            with open(config_path, 'w') as f:
                f.write('{}')
        finally:
            os.umask(old_umask)

    assertFilePermission(config_path, 0600)
    return config_path
