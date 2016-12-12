# -*- coding: utf-8 -*-

import sys
import re
import time
import getpass
import logging
import json
from selenium.webdriver.remote.webdriver import WebDriver
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement

LOGIN_TIMEOUT = 60
RESPONCE_TIMEOUT = 10

def waitForPresenceOfElementById(driver, id, timeout=RESPONCE_TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, id)))

def waitForPresenceOfAllElementsByClassName(driver, class_name, timeout=RESPONCE_TIMEOUT):
    return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((By.CLASS_NAME, class_name)))

def findElementById(element, id, timeout=RESPONCE_TIMEOUT):
    if isinstance(element, WebElement):
        driver = element.parent
    elif isinstance(element, WebDriver):
        driver = element
    else:
        raise AssertionError
    waitForPresenceOfElementById(driver, id, timeout)
    return element.find_element_by_id(id)

def findAllElementsByClassName(element, class_name, timeout=RESPONCE_TIMEOUT):
    if isinstance(element, WebElement):
        driver = element.parent
    elif isinstance(element, WebDriver):
        driver = element
    else:
        raise AssertionError
    waitForPresenceOfAllElementsByClassName(driver, class_name, timeout)
    return element.find_elements_by_class_name(class_name)

def findUniqueElementByClassName(element, class_name, timeout=RESPONCE_TIMEOUT):
    if isinstance(element, WebElement):
        driver = element.parent
    elif isinstance(element, WebDriver):
        driver = element
    else:
        raise AssertionError
    waitForPresenceOfAllElementsByClassName(driver, class_name, timeout)
    found_elems = element.find_elements_by_class_name(class_name)
    if len(found_elems) == 0:
        raise AssertionError
    if len(found_elems) >= 2:
        raise AssertionError
    return found_elems[0]

def findElementByLinkText(element, link_text):
    return element.find_element_by_link_text(link_text)

def main(driver):
    driver.get('https://chunithm-net.com/mobile/')

    # ユーザがブラウザ上で SEGA ID とパスワードを入力してログインするのを待機

    select_aime_elem = waitForPresenceOfElementById(driver, 'SelectAime', LOGIN_TIMEOUT)

    select_aime_elem.click()
    main_menu_elem = waitForPresenceOfElementById(driver, 'main_menu')
    btn_record_elem = findUniqueElementByClassName(main_menu_elem, 'btn_record')

    btn_record_elem.click()
    try:
        submenu_elem = waitForPresenceOfElementById(driver, 'submenu')
    except:
        # おそらく CHUNITHM-NET 利用権がない場合
        raise AssertionError
    submenu_play_elem = findUniqueElementByClassName(submenu_elem, 'submenu_play')

    submenu_play_elem.click()
    frame01_inside_elem = findUniqueElementByClassName(driver, 'frame01_inside')
    user_play_log_result_elem = findElementById(frame01_inside_elem, 'userPlaylog_result')
    play_elems = findAllElementsByClassName(user_play_log_result_elem, 'frame02')

    tracks = []

    for i in range(len(play_elems)):
        frame01_inside_elem = findUniqueElementByClassName(driver, 'frame01_inside')

        user_play_log_result_elem = findElementById(frame01_inside_elem, 'userPlaylog_result')
        play_elems = findAllElementsByClassName(user_play_log_result_elem, 'frame02')
        if i >= len(play_elems):
            raise AssertionError
        play_elem = play_elems[i]
        # 'SeeDetail' という id attribute の値が重複している。このような場合、
        # 以下のように element を指定しても selenium はドキュメントの最初の
        # element を返す模様。
        #see_detail_elem = waitForPresenceOfElementById(play_elem, 'SeeDetail', RESPONCE_TIMEOUT)
        see_detail_anchor = findElementByLinkText(play_elem, '詳細を見る')

        track = {}

        see_detail_anchor.click()
        user_play_log_detail_result_elem = waitForPresenceOfElementById(driver, 'userPlaylogDetail_result')
        box01_elem = findUniqueElementByClassName(user_play_log_detail_result_elem, 'box01')

        # 日時の抽出
        date_elem = findElementById(box01_elem, 'Date')
        date_text = date_elem.text
        track['date'] = date_text

        frame02_elems = findAllElementsByClassName(box01_elem, 'frame02')
        if len(frame02_elems) != 2:
            raise AssertionError
        music_elem = frame02_elems[0]
        misc_elem = frame02_elems[1]

        music_elem = findUniqueElementByClassName(music_elem, 'play_data_side01')

        track_elem = findUniqueElementByClassName(music_elem, 'play_track_block')

        # トラック番号（1クレジット内の何番目の演奏かを表す番号）の抽出
        track_number_elem = findElementById(track_elem, 'Track')
        track_number_text = track_number_elem.text
        m = re.compile('^Track ([1234])$').match(track_number_text)
        if not m:
            raise AssertionError
        track_number = int(m.group(1))
        track['track number'] = track_number

        # トラックレベル（BASIC/ADVANCED/EXPERT/MASTER）の抽出
        track_level_elem = findElementById(track_elem, 'TrackLevel')
        track_level_img = track_level_elem.find_elements_by_tag_name('img')
        if len(track_level_img) != 1:
            raise AssertionError
        track_level_img = track_level_img[0]
        track_level_img_src = track_level_img.get_attribute('src')
        if re.compile('/icon_basic\.png$').search(track_level_img_src):
            track_level = 'BASIC'
        elif re.compile('/icon_advance\.png$').search(track_level_img_src):
            track_level = 'ADVANCED'
        elif re.compile('/icon_expert\.png$').search(track_level_img_src):
            track_level = 'EXPERT'
        elif re.compile('/icon_master\.png$').search(track_level_img_src):
            track_level = 'MASTER'
        else:
            raise AssertionError
        track['track level'] = track_level

        title_score_elem = findUniqueElementByClassName(music_elem, 'play_musicdata_block')

        # 曲名の抽出
        music_title_elem = findElementById(title_score_elem, 'MusicTitle')
        title = music_title_elem.text
        track['title'] = title

        score_elem = findUniqueElementByClassName(title_score_elem, 'play_musicdata_score')

        # プレイスコアの抽出
        score_text_elem = findElementById(score_elem, 'Score')
        score_text = score_text_elem.text
        if not re.compile('((1,)?\d{1,3},)?\d{1,3}$').match(score_text):
            raise AssertionError
        score_text = re.sub(',', '', score_text)
        score = int(score_text)
        track['score'] = score

        # プレイスコアが NEW RECORD か否かの抽出
        try:
            new_record_elem = score_elem.find_element_by_id('NewScoreIcon')
            track['new record'] = 1
        except NoSuchElementException:
            track['new record'] = 0

        frame01_inside_elem = findUniqueElementByClassName(driver, 'frame01_inside')
        mb_20_elem = findUniqueElementByClassName(frame01_inside_elem, 'mb_20')
        btn_back_elem = findUniqueElementByClassName(mb_20_elem, 'btn_back')

        box02_elems = misc_elem.find_elements_by_class_name('box02')
        if len(box02_elems) != 2:
            raise AssertionError
        store_elem = box02_elems[0]
        character_skill_elem = box02_elems[1]

        # 
        store_elem = findElementById(store_elem, 'Store')
        store_text = store_elem.text
        track['store'] = store_text

        # 
        character_name_elem = findElementById(character_skill_elem, 'CharacterName')
        character_name = character_name_elem.text
        track['character name'] = character_name

        # 
        skill_name_elem = findElementById(character_skill_elem, 'SkillName')
        skill_name = skill_name_elem.text
        track['skill name'] = skill_name

        # 
        try:
            skill_value_elem = driver.find_element_by_id('SkillValue')
            skill_value = skill_value_elem.text
            track['skill value'] = skill_value
        except NoSuchElementException:
            track['skill value'] = None

        # 
        skill_effect_elem = findElementById(character_skill_elem, 'SkillEffectNum')
        skill_effect = skill_effect_elem.text
        if not re.compile('([+-](\d{1,3},)?\d{1,3})|0$').match(skill_effect):
            raise AssertionError
        skill_effect = re.sub('^\+', '', skill_effect)
        skill_effect = re.sub(',', '', skill_effect)
        skill_effect = int(skill_effect)
        track['skill effect'] = skill_effect

        # 
        max_combo_elem = driver.find_element_by_id('MaxCombo')
        max_combo = max_combo_elem.text
        if not re.compile('\d+$').match(max_combo):
            raise AssertionError
        max_combo = int(max_combo)
        track['max combo'] = max_combo

        # 
        justice_critical_elem = driver.find_element_by_id('JusticeCritical')
        justice_critical = justice_critical_elem.text
        if not re.compile('\d+$').match(justice_critical):
            raise AssertionError
        justice_critical = int(justice_critical)
        track['justice critical'] = justice_critical

        # 
        justice_elem = driver.find_element_by_id('Justice')
        justice = justice_elem.text
        if not re.compile('\d+$').match(justice):
            raise AssertionError
        justice = int(justice)
        track['justice'] = justice

        # 
        attack_elem = driver.find_element_by_id('Attack')
        attack = attack_elem.text
        if not re.compile('\d+$').match(attack):
            raise AssertionError
        attack = int(attack)
        track['attack'] = attack

        # 
        miss_elem = driver.find_element_by_id('Miss')
        miss = miss_elem.text
        if not re.compile('\d+$').match(miss):
            raise AssertionError
        miss = int(miss)
        track['miss'] = miss

        # 
        tap_elem = driver.find_element_by_id('Tap')
        tap = tap_elem.text
        tap = re.sub('%$', '', tap)
        tap = float(tap)
        track['tap'] = tap / 100

        # 
        hold_elem = driver.find_element_by_id('Hold')
        hold = hold_elem.text
        hold = re.sub('%$', '', hold)
        hold = float(hold)
        track['hold'] = hold / 100

        # 
        slide_elem = driver.find_element_by_id('Slice')
        slide = slide_elem.text
        slide = re.sub('%$', '', slide)
        slide = float(slide)
        track['slide'] = slide / 100

        # 
        air_elem = driver.find_element_by_id('Air')
        air = air_elem.text
        air = re.sub('%$', '', air)
        air = float(air)
        track['air'] = air / 100

        # 
        flick_elem = driver.find_element_by_id('Flick')
        flick = flick_elem.text
        flick = re.sub('%$', '', flick)
        flick = float(flick)
        track['flick'] = flick / 100

        tracks.append(track)

        btn_back_elem.click()

    main_menu_elem = waitForPresenceOfElementById(driver, 'main_menu')
    btn_home_elem = findUniqueElementByClassName(main_menu_elem, 'btn_home')

    btn_home_elem.click()
    user_info_result_elem = waitForPresenceOfElementById(driver, 'userInfo_result')
    more_elem = findUniqueElementByClassName(user_info_result_elem, 'more')

    player = {}

    more_elem.click()
    user_lv_elem = waitForPresenceOfElementById(driver, 'UserLv')
    user_lv = user_lv_elem.text
    user_lv = int(user_lv)
    player['lv'] = user_lv

    user_rating_elem = waitForPresenceOfElementById(driver, 'UserRating')
    user_rating = user_rating_elem.text
    user_rating = float(user_rating)
    player['rating'] = user_rating

    mile_elem = waitForPresenceOfElementById(driver, 'Dolce')
    mile = mile_elem.text
    mile = int(mile)
    player['mile'] = mile

    total_mile_elem = waitForPresenceOfElementById(driver, 'TotalDolce')
    total_mile = total_mile_elem.text
    total_mile = int(total_mile)
    player['total mile'] = total_mile

    play_count_elem = waitForPresenceOfElementById(driver, 'PlayCount')
    play_count = play_count_elem.text
    m = re.compile(u'(\d+)回$').match(play_count)
    if not m:
        raise AssertionError
    play_count = m.group(1)
    play_count = int(play_count)
    player['play count'] = play_count

    for i in range(len(tracks)):
        tracks[i]['player level'] = None
        tracks[i]['rating'] = None
        tracks[i]['mile'] = None
        tracks[i]['total mile'] = None
        tracks[i]['play count'] = None

    tracks[0]['player level'] = user_lv
    tracks[0]['rating'] = user_rating
    tracks[0]['mile'] = mile
    tracks[0]['total mile'] = total_mile
    tracks[0]['play count'] = play_count

    with open('tracks.json', 'w') as f:
        json.dump(tracks, f)

driver = webdriver.Chrome()
try:
    main(driver)
    logging.info(u'Finish scrape.')
except:
    logging.exception(u'A fatal exception is thrown.')
    raise
driver.quit()
sys.exit(0)
