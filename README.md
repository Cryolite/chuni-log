# CHUNI-LOG
## 概要
[CHUNITHM-NET](https://chunithm-net.com/) からプレイヤーデータとプレイ履歴を抽出して [Google スプレッドシート](https://www.google.com/intl/ja_jp/sheets/about/)に保存するスクリプトを提供します。
## 必要なもの
### SEGA ID の登録
SEGA ID を登録していない方は、[Aimeサービスサイト](https://my-aime.net/)から SEGA ID を登録します。
### Aime カード/携帯電話の SEGA ID への登録
[CHUNITHM](http://chunithm.sega.jp/) をプレイした Aime カード/携帯電話を SEGA ID に登録していない方は[Aimeサービスサイト](https://my-aime.net/)で、 Aime カード/携帯電話を SEGA ID に登録します。
### [Google アカウント](https://accounts.google.com/)
保存先の Google スプレッドシートを作成する Google アカウントが必要です。
### Linux 環境
Ubuntu Desktop 16.04.1 LTS でのみ動作を確認しています。なお、スクリプトの実行において GUI は一切必要とされません。
### python-gflags
`$ pip install -U python-gflags`
### Standalone Selenium Server
詳しくは [Running Standalone Selenium Server for use with RemoteDrivers](http://www.seleniumhq.org/docs/03_webdriver.jsp#running-standalone-selenium-server-for-use-with-remotedrivers) を参照してください。
### Python language bindings for Selenium WebDriver
`$ pip install -U selenium`

詳しくは https://seleniumhq.github.io/selenium/docs/api/py/index.html を参照してください。
### Google APIs Client Library for Python
`$ pip install -U google-api-python-client`

詳しくは https://developers.google.com/api-client-library/python/start/installation を参照してください。
