# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import re
import time
import datetime
import hashlib
import logging
import getpass
import json

import gflags

from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from common import createConfigFileIfNeeded
from common import UserInputRequiredError
from common import StaleCredentialsError


PAGE_TRANSITION_TIMEOUT = 60
XHR_TIMEOUT = 10

MAX_NUM_TRACKS = 50

FLAGS = gflags.FLAGS
gflags.DEFINE_boolean(u'non_interactive', False,
                      u'Run without asking user input.')
gflags.DEFINE_boolean(u'always_interactive', False,
                      u'Always ask for user input.')
gflags.DEFINE_boolean(u'verbose', False, u'Run with verbose output.')

class MultipleElementsFoundException(WebDriverException):
    pass

class PageTransitionFailure(WebDriverException):
    pass

def setLogging():
    logging.basicConfig(
        filename='src/scraper.log',
        encoding='UTF-8',
        format='%(asctime)s.%(msecs)03d %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO)

def getWebDriver():
    return webdriver.Remote(
        u'http://127.0.0.1:4444/wd/hub', DesiredCapabilities.HTMLUNITWITHJS)

def getSegaIdAndPassword():
    config_path = createConfigFileIfNeeded()

    with open(config_path, 'r') as f:
        config = json.load(f)

    if 'sega_id' not in config:
        if 'sega_id_password' in config:
            os.remove(config_path)
            raise IOError('{0} の内容に不整合が発見されたため削除されました。'
                          .format(config_path))
        if FLAGS.non_interactive:
            raise UserInputRequiredError(
                '非対話モードですが SEGA ID とパスワードの入力が必要です。')
        sega_id = raw_input('SEGA ID: ')
        password = getpass.getpass('パスワード: ')
        is_stored = False
    elif FLAGS.always_interactive:
        if 'sega_id_password' not in config:
            os.remove(config_path)
            raise IOError('{0} の内容に不整合が発見されたため削除されました。'
                          .format(config_path))
        sega_id = raw_input('SEGA ID ({0}):'.format(config['sega_id']))
        if not sega_id:
            sega_id = config['sega_id']
        password = getpass.getpass('パスワード（省略可能）: ')
        if not password:
            password = config['sega_id_password']
        is_stored = True
    else:
        if 'sega_id_password' not in config:
            raise IOError('{0} の内容に不整合が発見されたため削除されました。'
                          .format(config_path))
        sega_id = config['sega_id']
        password = config['sega_id_password']
        is_stored = True

    return sega_id, password, is_stored

def storeSegaIdAndPassword(sega_id, password):
    config_path = createConfigFileIfNeeded()
    with open(config_path, 'r') as f:
        config = json.load(f)
    if FLAGS.non_interactive:
        if sega_id != config['sega_id']:
            raise AssertionError
        if sega_id_password != config['sega_id_password']:
            raise AssertionError
    config['sega_id'] = sega_id
    config['sega_id_password'] = password
    with open(config_path, 'w') as f:
        json.dump(config, f)

def invalidateStoredSegaIdAndPassword():
    config_path = createConfigFileIfNeeded()
    with open(config_path, 'r') as f:
        config = json.load(f)

    result = 'sega_id' in config

    if 'sega_id' in config:
        if 'sega_id_password' not in config:
            raise IOError('{0} の内容に不整合が発見されたため削除されました。'.format(config_path))
        config.pop('sega_id')
        config.pop('sega_id_password')

    with open(config_path, 'w') as f:
        json.dump(config, f)

    return result

def findUniqueElementById(element, id):
    found_elements = element.find_elements_by_id(id)
    if len(found_elements) == 0:
        raise NoSuchElementException
    if len(found_elements) >= 2:
        raise MultipleElementsFoundException
    return found_elements[0]

def findUniqueElementByName(element, name):
    found_elements = element.find_elements_by_name(name)
    if len(found_elements) == 0:
        raise NoSuchElementException
    if len(found_elements) >= 2:
        raise MultipleElementsFoundException
    return found_elements[0]

def findUniqueElementByTagName(element, tag_name):
    found_elements = element.find_elements_by_tag_name(tag_name)
    if len(found_elements) == 0:
        raise NoSuchElementException
    if len(found_elements) >= 2:
        raise MultipleElementsFoundException
    return found_elements[0]

def findUniqueElementByClassName(element, class_name):
    found_elements = element.find_elements_by_class_name(class_name)
    if len(found_elements) == 0:
        raise NoSuchElementException
    if len(found_elements) >= 2:
        raise MultipleElementsFoundException
    return found_elements[0]

def waitForPageTransition(driver, transition_executor,
                          expected_url=None,
                          timeout=PAGE_TRANSITION_TIMEOUT):
    old_url = driver.current_url
    old_html = findUniqueElementByTagName(driver, u'html')
    transition_executor()
    time_limit = datetime.datetime.today() +\
                     datetime.timedelta(seconds=timeout)
    WebDriverWait(driver, timeout).until(EC.staleness_of(old_html))
    while True:
        if driver.current_url != old_url:
            break
        if datetime.datetime.today() > time_limit:
            raise TimeoutException
        time.sleep(0.5)

    if expected_url:
        current_url = driver.current_url
        if current_url != expected_url:
            raise PageTransitionFailure(
                u'{0} から'
                u' {1} への'
                u'ページ遷移に失敗しました。'
                u'現在のページの URL は {2} です。'
                .format(old_url, expected_url, current_url).encode('UTF-8'))

def waitForVisibilityOfElementById(driver, id, timeout=XHR_TIMEOUT):
    WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.ID, id)))

def logIn(driver):
    if FLAGS.verbose:
        print('CHUNITHM-NET へのログインを開始します。')

    driver.get(u'https://chunithm-net.com/mobile/')

    sega_id, password, is_credentials_stored = getSegaIdAndPassword()

    login_form = findUniqueElementByTagName(driver, u'form')
    sega_id_input = findUniqueElementByName(login_form, u'segaId')
    sega_id_input.clear()
    sega_id_input.send_keys(sega_id)
    password_input = findUniqueElementByName(login_form, u'password')
    password_input.clear()
    password_input.send_keys(password)

    login_button = findUniqueElementByClassName(login_form, u'btn_login')
    waitForPageTransition(driver, lambda: login_button.click())

    current_url = driver.current_url
    if not isinstance(current_url, unicode):
        raise AssertionError
    if current_url == u'https://chunithm-net.com/mobile/AimeList.html':
        storeSegaIdAndPassword(sega_id, password)
    elif current_url == u'https://chunithm-net.com/mobile/Error.html':
        # TODO: このページにエラー番号が出力されているので取得。
        print('CHUNITHM-NET へのログインに失敗しました。')
        if is_credentials_stored:
            print('SEGA ID とパスワードを再入力するには'\
                  ' --force_interactive オプションを指定してください。')
        return False
    else:
        raise PageTransitionFailure(
            'https://chunithm-net.com/mobile/ から'
            ' https://chunithm-net.com/mobile/AimeList.html への'
            'ページ遷移に失敗しました。'
            '現在のページの URL は {0} です。'.format(current_url.encode('UTF-8')))

    return True

def findElementByXpath(element, xpath):
    found_elements = element.find_elements_by_xpath(xpath)
    if len(found_elements) == 0:
        return None
    if len(found_elements) >= 2:
        raise MultipleElementsFoundException
    return found_elements[0]

def findUniqueElementByXpath(element, xpath):
    found_element = findElementByXpath(element, xpath)
    if not found_element:
        raise NoSuchElementException
    return found_element

def waitUntil(condition_callback, timeout, polling_interval=0.5):
    time_limit = datetime.datetime.today() + datetime.timedelta(seconds=timeout)
    while not condition_callback():
        time.sleep(polling_interval)
        if datetime.datetime.today() > time_limit:
            raise TimeoutException

def selectAime(driver):
    if FLAGS.verbose:
        print('Aime の選択を実行します。')

    waitForVisibilityOfElementById(driver, u'userInfo_result')
    user_info_result = findUniqueElementById(driver, u'userInfo_result')

    # Aime が複数登録されている場合、
    # https://chunithm-net.com/mobile/AimeList.html では Ajax によって
    # 非同期かつインクリメンタルに各 Aime を選択させる HTML 要素を
    # 追加していく。このため，全ての Aime 選択要素が表示され終わるのを
    # 待機する必要がある。しかしながら、 Selenium （より一般に
    # WebDriver https://www.w3.org/TR/webdriver/）にはこれを直接実現する
    # 機能が存在しない。従って、何らかの workaround を講じる必要がある。
    #
    # 以下の workaround は、下記に記述する事項を根拠として極めて頑健に
    # 動作するものと期待される。
    #
    # 各 Aime 選択要素がページコンテンツに動的かつインクリメンタルに追加される
    # 動作は、 body 要素の onload 属性から実行される一続きの
    # スクリプト実行によって実現されている。
    #
    # 加えて、 HTML では複数のスクリプトが並列に実行されることがないことも
    # 利用している。これについては Web Hypertext Application Technology Working
    # Group (WHATWG) の記述
    # https://html.spec.whatwg.org/#serialisability-of-script-execution を
    # 参照すること。すなわち、あらゆる browsing contexts
    # (https://html.spec.whatwg.org/#browsing-context) において、全ての
    # スクリプトの実行が完全に直列化されていると考えることができる。
    #
    # 最後に、 Selenium は current browsing context
    # (https://www.w3.org/TR/webdriver/#dfn-current-browsing-context) において
    # 指定した JavaScript を実行する機能を実装している。
    time_limit = datetime.datetime.today() +\
                     datetime.timedelta(seconds=XHR_TIMEOUT)
    while True:
        select_aimes = user_info_result.find_elements_by_xpath(
            u'descendant::div[@id="SelectAime"]')
        if len(select_aimes) > 0:
            # len(select_aimes) が1以上であるため、直前の
            # find_elements_by_xpath は、スクリプトによるページコンテンツの
            # 動的更新の最中か、スクリプトが終了した後に実行されている。
            driver.execute_script(u'void(0);')
            # 上に述べた通り、 execute_script で指定したスクリプトの実行は
            # ページコンテンツを更新していたスクリプトの終了後に実行される。
            # 従って、直前の find_elements_by_xpath の呼び出しがスクリプトの
            # 実行の最中であったとしても、 execute_script の呼び出しが
            # 完了した時点ではスクリプトの実行が終了していることが保証される。
            break
        if datetime.datetime.today() > time_limit:
            raise TimeoutException
        time.sleep(0.5)
    select_aimes = user_info_result.find_elements_by_xpath(
        u'descendant::div[@id="SelectAime"]')

    # 登録されている Aime の数
    num_aimes = len(select_aimes)
    if num_aimes == 0:
        raise AssertionError

    # 各 Aime のユーザの輪廻転生の回数
    reborns = user_info_result.find_elements_by_xpath(
        u'descendant::div[@id="UserReborn"]')
    if len(reborns) != num_aimes:
        raise AssertionError
    reborns = map(lambda user_reborn: user_reborn.text, reborns)

    # 各 Aime のユーザレベル
    lvs = user_info_result.find_elements_by_xpath(
        u'descendant::span[@id="UserLv"]')
    if len(lvs) != num_aimes:
        raise AssertionError
    lvs = map(lambda user_lv: user_lv.text, lvs)

    # 各 Aime のユーザ名
    names = user_info_result.find_elements_by_xpath(
        u'descendant::span[@id="UserName"]')
    if len(names) != num_aimes:
        raise AssertionError
    names = map(lambda user_name: user_name.text, names)

    # 各 Aime のユーザのレーティング
    ratings = user_info_result.find_elements_by_xpath(
        u'descendant::div[@class="player_rating"]/child::span[@id="UserRating"][1]')
    if len(ratings) != num_aimes:
        raise AssertionError
    ratings = map(lambda user_rating: user_rating.text, ratings)

    # 各 Aime のユーザの最大レーティング
    max_ratings = user_info_result.find_elements_by_xpath(
        u'descendant::div[@class="player_rating"]/child::span[@id="UserRating"][2]')
    if len(max_ratings) != num_aimes:
        raise AssertionError
    max_ratings = map(lambda max_rating: max_rating.text, max_ratings)

    if num_aimes >= 2:
        print
        print('複数のAimeが登録されています。ログインするAimeを選んでください。')
        for i, reborn, lv, name, ratings, max_rating in\
                zip(range(num_aimes), reborns, lvs, names, ratings, max_ratings):
            text = u'{0}: '.format(unicode(i + 1))
            text += u'Lv.' + (u'' if not reborn else reborn + u'-') + lv.rjust(2)
            text += u' ' + name
            text += u' (RATING: ' + ratings.rjust(5) + u' / ' + max_rating.rjust(5) + u')\n'
            print(text.encode('UTF-8'))
        while True:
            aime_index = raw_input('番号: ')
            if re.compile('[1-{0}]$'.format(num_aimes)).match(aime_index):
                aime_index = int(aime_index)
                if 1 <= aime_index and aime_index <= num_aimes:
                    break
            print('1から{0}までの番号を入力してください。'.format(num_aimes))
    else:
        aime_index = 1

    select_aime = findUniqueElementByXpath(
        user_info_result,
        u'descendant::div[@id="SelectAime"][{0}]'.format(aime_index))
    waitForPageTransition(driver, lambda: select_aime.click(),
                          u'https://chunithm-net.com/mobile/Home.html')

def getAimeId(driver):
    if FLAGS.verbose:
        print('選択された Aime の ID を取得します。')

    # CHUNITHM-NET において複数の Aime を識別するおそらく唯一の方法は
    # フレンドコードの取得である。この関数は、フレンドコードを取得し、
    # それに SHA-256 を適用した結果得られるハッシュ値を16進数表記のテキストで
    # 表記したものを出力する。このハッシュ値を Aime の ID として利用する。
    main_menu = findUniqueElementById(driver, u'main_menu')
    btn_friend = findUniqueElementByXpath(
        main_menu,
        "child::div[@onclick=\"location.href='./Friendlist.html';\"]")
    waitForPageTransition(driver, lambda: btn_friend.click(),
                          u'https://chunithm-net.com/mobile/Friendlist.html')

    submenu = findUniqueElementById(driver, u'submenu')
    friend_candidate = findUniqueElementByXpath(
        submenu,
        u"child::div[@onclick=\"location.href='./FriendSearch.html';\"]")
    waitForPageTransition(driver, lambda: friend_candidate.click(),
                          u'https://chunithm-net.com/mobile/FriendSearch.html')

    friend_code = findUniqueElementById(driver, u'userFriendCode_result')
    waitUntil(lambda: friend_code.text, XHR_TIMEOUT)
    return hashlib.sha256(friend_code.text).hexdigest()

def waitForAllTrackSummaries(driver, timeout=XHR_TIMEOUT):
    # selectAime 関数で複数の Aime が登録されている場合の処理と同様。
    # 詳しくは当該のコメントを参照のこと。
    playlog_result = findUniqueElementById(driver, u'userPlaylog_result')
    time_limit = datetime.datetime.today() + datetime.timedelta(seconds=timeout)
    while True:
        track_summaries = playlog_result.find_elements_by_xpath(u'child::div')
        if len(track_summaries) > 0:
            driver.execute_script(u'void(0);')
            break
        if datetime.datetime.today() > time_limit:
            raise TimeoutException
        time.sleep(0.5)
    return playlog_result

def popTrackElements(track_elements, id, validation_pattern=None):
    result = track_elements.pop(0)
    if result.get_attribute(u'id') != id:
        raise AssertionError
    result = result.text
    if validation_pattern:
        if not re.compile(validation_pattern).match(result):
            raise AssertionError(
                u'トラックデータのパースに失敗しました。'
                u' (id = `{0}`, text = `{1}`, pattern = `{2}`)'
                .format(id, result, validation_pattern).encode('UTF-8'))
    return result

def getTracks(driver):
    main_menu = findUniqueElementById(driver, u'main_menu')
    btn_record = findUniqueElementByXpath(
        main_menu,
        u"child::div[@onclick=\"location.href='./MapInfo.html';\"]")
    waitForPageTransition(driver, lambda: btn_record.click(),
                          u'https://chunithm-net.com/mobile/MapInfo.html')

    submenu = findUniqueElementById(driver, u'submenu')
    play = findUniqueElementByXpath(
        submenu,
        u"child::div[@onclick=\"location.href='./Playlog.html';\"]")

    waitForPageTransition(driver, lambda: play.click(),
                          u'https://chunithm-net.com/mobile/Playlog.html')
    playlog_result = waitForAllTrackSummaries(driver)

    track_summaries = playlog_result.find_elements_by_xpath(u'child::div')
    num_tracks = len(track_summaries)

    if FLAGS.verbose:
        print('プレイ履歴の曲数: {0}'.format(num_tracks))
        print('各トラックの詳細を抽出します。')

    tracks = []
    for i in range(num_tracks):
        track = {}

        anchor = findUniqueElementByXpath(
            playlog_result,
            u'child::div[{0}]/'
            u'descendant::a[@href="JavaScript:void(0);"][text()="詳細を見る"]'
            .format(i + 1))
        waitForPageTransition(
            driver, lambda: anchor.click(),
            u'https://chunithm-net.com/mobile/PlaylogDetail.html')

        waitForVisibilityOfElementById(driver, u'Flick')
        driver.execute_script(u'void(0);')

        detail_result = findUniqueElementById(driver,
                                              u'userPlaylogDetail_result')
        track_elems = detail_result.find_elements_by_xpath(
            u'descendant::node()[name()="div" or name()="span"]'
            u'[@id="Date" or @id="Track" or @id="TrackLevel" or'
            u' @id="MusicTitle" or @id="Score" or'
            u' @id="NewScoreIcon" or @id="Store" or'
            u' @id="CharacterName" or @id="SkillName" or'
            u' @id="SkillValue" or @id="SkillEffectNum" or'
            u' @id="MaxCombo" or @id="JusticeCritical" or'
            u' @id="Justice" or @id="Attack" or @id="Miss" or'
            u' @id="Tap" or @id="Hold" or @id="Slice" or'
            u' @id="Air" or @id="Flick"]')
        if len(track_elems) not in (19, 20, 21):
            raise AssertionError

        # 日時
        track['date'] = popTrackElements(
            track_elems, u'Date',
            u'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$')

        # トラック番号（1クレジット内の何番目の演奏かを表す番号）
        track_number = track_elems.pop(0)
        if track_number.get_attribute(u'id') != u'Track':
            raise AssertionError
        track_number = track_number.text
        m = re.compile(u'Track ([1-4])$').match(track_number)
        if not m:
            ValueError
        track_number = int(m.group(1))
        track['track_number'] = track_number

        # トラックレベル（BASIC/ADVANCED/EXPERT/MASTER）
        track_level = track_elems.pop(0)
        if track_level.get_attribute(u'id') != u'TrackLevel':
            raise AssertionError
        track_level = findUniqueElementByXpath(track_level, u'child::img')
        track_level = track_level.get_attribute('src')
        if track_level == u'https://chunithm-net.com/mobile/'\
                          u'common/images/icon_basic.png':
            track_level = u'BASIC'
        elif track_level == u'https://chunithm-net.com/mobile/'\
                            u'common/images/icon_advance.png':
            track_level = u'ADVANCED'
        elif track_level == u'https://chunithm-net.com/mobile/'\
                            u'common/images/icon_expert.png':
            track_level = u'EXPERT'
        elif track_level == u'https://chunithm-net.com/mobile/'\
                            u'common/images/icon_master.png':
            track_level = u'MASTER'
        else:
            raise AssertionError(track_level)
        track['track_level'] = track_level

        # 曲名
        track['title'] = popTrackElements(track_elems, u'MusicTitle')

        # スコア
        score = popTrackElements(
            track_elems, u'Score', u'((1,)?[0-9]{1,3},)?[0-9]{1,3}$')
        score = re.sub(',', '', score)
        track['score'] = int(score)

        # NEW RECORD か否か（NEW RECORD の時のみ HTML 要素が存在）
        if track_elems[0].get_attribute(u'id') != u'NewScoreIcon':
            if len(track_elems) not in (14, 15):
                raise AssertionError
            if track_elems[0].get_attribute(u'id') != u'Store':
                raise AssertionError
            track['new_record'] = 0
        else:
            if len(track_elems) not in (15, 16):
                raise AssertionError
            # NEW RECORD
            new_record = track_elems.pop(0)
            new_record = findUniqueElementByXpath(new_record, u'child::img')
            new_record = new_record.get_attribute(u'src')
            if new_record != u'https://chunithm-net.com/mobile/'\
                             u'common/images/icon_newrecord.jpg':
                raise AssertionError
            track['new_record'] = 1

        # 店名
        track['store_name'] = popTrackElements(track_elems, u'Store')

        # キャラクタ名
        track['character_name'] = popTrackElements(track_elems,
                                                   u'CharacterName')

        # スキル名
        track['skill_name'] = popTrackElements(track_elems, u'SkillName')

        # スキルグレード（初期値の場合は HTML 要素が存在しない）
        if track_elems[0].get_attribute(u'id') == u'SkillValue':
            if len(track_elems) != 12:
                raise AssertionError
            track['skill_grade'] = popTrackElements(
                track_elems, u'SkillValue', u'\+([1-9][0-9]|[1-9])$')
        else:
            if len(track_elems) != 11:
                raise AssertionError
            track['skill_grade'] = u''

        # スキルリザルト
        skill_result = popTrackElements(
            track_elems, u'SkillEffectNum',
            u'([+-]([1-9][0-9]{0,2},[0-9]{1,3}|[1-9][0-9]{0,2}))|0$')
        skill_result = re.sub(u'^\+', u'', skill_result)
        skill_result = re.sub(u',', u'', skill_result)
        track['skill_result'] = int(skill_result)

        # MAX COMBO
        max_combo = popTrackElements(
            track_elems, u'MaxCombo', u'[1-9][0-9]{0,3}|0$')
        track['max_combo'] = int(max_combo)

        # JUSTICE CRITICAL
        justice_critical = popTrackElements(
            track_elems, u'JusticeCritical', u'[1-9][0-9]{0,3}|0$')
        track['justice_critical'] = int(justice_critical)

        # JUSTICE
        justice = popTrackElements(
            track_elems, u'Justice', u'[1-9][0-9]{0,3}|0$')
        track['justice'] = int(justice)

        # ATTACK
        attack = popTrackElements(
            track_elems, u'Attack', u'[1-9][0-9]{0,3}|0$')
        track['attack'] = int(attack)

        # MISS
        miss = popTrackElements(
            track_elems, u'Miss', u'[1-9][0-9]{0,3}|0$')
        track['miss'] = int(miss)

        # TAP
        tap = popTrackElements(
            track_elems, u'Tap', u'(101|100(\.[0-9]{1,2})?|[1-9]?[0-9](\.[0-9]{1,2})?)%$')
        tap = re.sub(u'%$', '', tap)
        track['tap'] = float(tap) / 100

        # HOLD
        hold = popTrackElements(
            track_elems, u'Hold', u'(101|100(\.[0-9]{1,2})?|[1-9]?[0-9](\.[0-9]{1,2})?)%$')
        hold = re.sub(u'%$', '', hold)
        track['hold'] = float(hold) / 100

        # SLIDE
        slide = popTrackElements(
            track_elems, u'Slice', u'(101|100(\.[0-9]{1,2})?|[1-9]?[0-9](\.[0-9]{1,2})?)%$')
        slide = re.sub(u'%$', '', slide)
        track['slide'] = float(slide) / 100

        # AIR
        air = popTrackElements(
            track_elems, u'Air', u'(101|100(\.[0-9]{1,2})?|[1-9]?[0-9](\.[0-9]{1,2})?)%$')
        air = re.sub(u'%$', '', air)
        track['air'] = float(air) / 100

        # FLICK
        flick = popTrackElements(
            track_elems, u'Flick', u'(101|100(\.[0-9]{1,2})?|[1-9]?[0-9](\.[0-9]{1,2})?)%$')
        flick = re.sub(u'%$', '', flick)
        track['flick'] = float(flick) / 100

        if FLAGS.verbose:
            print(u'  {0} {1}'.format(track['date'], track['title'])\
                              .encode('UTF-8'))

        tracks.append(track)

        waitForPageTransition(driver, lambda: driver.back(),
                              u'https://chunithm-net.com/mobile/Playlog.html')
        playlog_result = waitForAllTrackSummaries(driver)

    return tracks

def getUserData(driver):
    if FLAGS.verbose:
        print('ユーザデータを取得します。')

    main_menu = findUniqueElementById(driver, u'main_menu')
    btn_home = findUniqueElementByXpath(
        main_menu,
        u"child::div[@onclick=\"location.href='./Home.html';\"]")
    waitForPageTransition(driver, lambda: btn_home.click(),
                          u'https://chunithm-net.com/mobile/Home.html')

    user_info_result = findUniqueElementById(driver, u'userInfo_result')
    time_limit = datetime.datetime.today() +\
                     datetime.timedelta(seconds=XHR_TIMEOUT)
    while True:
        user_info_detail = findElementByXpath(
            user_info_result,
            "descendant::div[@onclick=\"location.href='./UserInfoDetail.html';\"]")
        if user_info_detail:
            driver.execute_script('void(0);')
            break
        if datetime.datetime.today() > time_limit:
            raise TimeoutException

    waitForPageTransition(
        driver, lambda: user_info_detail.click(),
        u'https://chunithm-net.com/mobile/UserInfoDetail.html')

    user_info_result = findUniqueElementById(driver, u'userInfo_result')
    time_limit = datetime.datetime.today() +\
                     datetime.timedelta(seconds=XHR_TIMEOUT)
    while True:
        play_count = findElementByXpath(
            user_info_result,
            'descendant::div[@id="PlayCount"]')
        if play_count:
            driver.execute_script('void(0);')
            break
        if datetime.datetime.today() > time_limit:
            raise TimeoutException

    # https://chunithm-net.com/mobile/UserInfoDetail.html で取得できる
    # ユーザデータのうち、以下は取得しない。
    #
    #   * 称号タイプ
    #   * 称号
    #   * ユーザ名
    #   * 最大レーティング
    #   * キャラクタ画像
    #   * フレンド数
    #   * CHUNITHM-NET利用権の残日数
    #   * コメント

    # 現在のレーティングと最大レーティングは、どちらも
    # UserRating という id の要素に表示される。
    user_info_elems = user_info_result.find_elements_by_xpath(
        u'descendant::node()[name()="div" or name()="span"]'
        u'[@id="UserReborn" or @id="UserLv" or @id="UserRating" or'
        u' @id="Dolce" or @id="TotalDolce" or @id="PlayCount"]')
    if len(user_info_elems) != 7:
        raise AssertionError

    user_data = {}

    # 輪廻転生の回数（0の場合は空文字列）
    num_lv_wraparound = popTrackElements(
        user_info_elems, u'UserReborn', u'([1-9][0-9]*)?$')
    if not num_lv_wraparound:
        user_data['num_lv_wraparound'] = 0
    else:
        user_data['num_lv_wraparound'] = int(num_lv_wraparound)

    # レベル
    lv = popTrackElements(user_info_elems, u'UserLv', u'[1-9][0-9]?$')
    user_data['lv'] = int(lv)

    # レーティング
    rating = popTrackElements(
        user_info_elems, u'UserRating', u'1?[0-9]\.[0-9]{2}$')
    user_data['rating'] = float(rating)

    # 最大レーティング（記録しない）
    highest_rating = popTrackElements(
        user_info_elems, u'UserRating', u'1?[0-9]\.[0-9]{2}$')
    if user_data['rating'] > highest_rating:
        raise AssertionError

    # マイル
    mile = popTrackElements(
        user_info_elems, u'Dolce', u'[1-9][0-9]+|0$')
    user_data['mile'] = int(mile)

    # 総マイル
    total_mile = popTrackElements(
        user_info_elems, u'TotalDolce', u'[1-9][0-9]+|0$')
    user_data['total_mile'] = int(total_mile)

    # プレイ回数
    play_count = popTrackElements(
        user_info_elems, u'PlayCount', u'[1-9][0-9]+回$')
    m = re.compile(u'([1-9][0-9]+)回$').match(play_count)
    if not m:
        raise AssertionError
    play_count = m.group(1)
    user_data['play_count'] = int(play_count)

    if user_info_elems:
        raise AssertionError

    return user_data

def main(argv):
    setLogging()

    if FLAGS.non_interactive and FLAGS.always_interactive:
        raise ValueError('--non_interactive と'
                         ' --always_interactive は同時には指定できません。')

    driver = getWebDriver()
    try:
        if not logIn(driver):
            return 1
        selectAime(driver)
        aime_id = getAimeId(driver)
        if FLAGS.verbose:
            print('Aime ID: {0}'.format(aime_id.encode('UTF-8')))
        tracks = getTracks(driver)
        user_data = getUserData(driver)
        user_data['aime_id'] = aime_id

        with open('data.json', 'w') as f:
            json.dump({'tracks': tracks, 'user_data': user_data},
                      f, indent=2, separators=(',', ': '))
    except:
        time.sleep(3.0)
        attention_elements = driver.find_elements_by_class_name(u'riyouken_attention')
        if len(attention_elements) == 1:
            print(attention_elements[0].text, file=sys.stderr)
            raise RuntimeError
        raise
    finally:
        driver.quit()

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main(FLAGS(sys.argv)))
    except:
        logging.exception(u'A fatal exception is thrown.')
        raise
