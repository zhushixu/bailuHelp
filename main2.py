import re, sys
import time
from time import sleep
import requests, random, json
from PySide6.QtGui import QTextCursor
from lxml import etree
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableWidgetItem, QTableWidget
from ui_main import Ui_MainWindow
from PySide6.QtCore import Signal, QRunnable, QObject, QThreadPool
import http.cookies
from datetime import datetime
from pathlib2 import Path
import ddddocr

ocr = ddddocr.DdddOcr(show_ad=False)


class WorkerSignals(QObject):
    finished = Signal()


class Worker(QRunnable):

    def __init__(self, func, *args):
        super().__init__()
        self.func = func
        self.args = args
        self.signals = WorkerSignals()

    def run(self):
        print("这里的args:", *self.args)
        self.func(*self.args)
        self.signals.finished.emit()


def update_open(param1):
    """更新开奖信息显示"""
    cookies = cookie_str_to_dict(param1['cookies'])
    mode = param1['mode']
    window.open_time = True
    # print("cookies:",cookies)
    # print("mode:",mode)
    # print("time_Flag:",window.open_time)

    while not window.stop_flag:
        # print("stop_flag的值：", window.stop_flag)
        try:
            result = json.loads(getgameNow(cookies, mode))
        except json.JSONDecodeError as e:
            result = {'code': -1, 'open': {'status': False}}
        # print("读取完成：", result)
        # print(result['code'], result['open']['status'])
        if result['code'] == 1 and result['open']['status']:
            # print('进入到这里了1')
            try:
                endTime = int(result['time']['delay'])
                qihao = result['open']['game_no']
                num1 = result['open']['num1']
                num2 = result['open']['num2']
                num3 = result['open']['num3']
                num = result['open']['num']
            except KeyError:
                add_log(0, '读取开奖出现错误')
                qihao = "000000"
                num1 = 1
                num2 = 2
                num3 = 3
                num = 6
                endTime = 0

            window.ui.label_js60_qihao.setText(f'第{qihao}期')
            window.ui.label_js60_openNumber.setText(f'{num1}+{num2}+{num3}={num}')
            window.ui.label_js60_openNumber.setStyleSheet(" font-size:16pt; font-weight:700; color:#ffaa00;")
            for end in range(endTime, 0, -1):
                if window.stop_flag:
                    print("停止了")
                    window.open_time = False
                    return
                window.ui.label_js60_remainder.setText(f'据下次解谜还剩{end}秒')
                sleep(1)


class MyApp(QMainWindow):
    closed = Signal()

    def __init__(self):
        self.open_time = False
        self.stop_flag = False
        self.account_path = ""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        widgets = self.ui
        self.log_line = 0
        self.threadpool = QThreadPool()
        widgets.btn_account_import.clicked.connect(self.buttonClick)  # 点击导入按钮
        widgets.btn_account_clear.clicked.connect(self.buttonClick)  # 点击清空按钮
        widgets.btn_account_login.clicked.connect(self.buttonClick)  # 点击登录按钮
        widgets.btn_account_query.clicked.connect(self.buttonClick)  # 点击查询按钮
        widgets.btn_run.clicked.connect(self.buttonClick)  # 点击开始运行按钮
        widgets.btn_stop.clicked.connect(self.buttonClick)  # 点击停止运行按钮

        last_column_index = widgets.tableWidget_account.columnCount() - 1
        # 设置最后一列的宽度为300像素
        widgets.tableWidget_account.setColumnWidth(last_column_index, 300)
        config_path = Path("config.json")
        if config_path.exists():
            config_text = config_path.read_text()
            config_json = json.loads(config_text)
            widgets.comboBox_game_mode.setCurrentIndex(int(config_json['game_mode']))
            widgets.lineEdit_input_money.setText(config_json['input_money'])
            widgets.lineEdit_double_number.setText(config_json['double_number'])
            widgets.lineEdit_max_money.setText(config_json['max_money'])

        # 设置整行选择和不可修改
        widgets.tableWidget_account.setSelectionBehavior(QTableWidget.SelectRows)
        widgets.tableWidget_account.setEditTriggers(QTableWidget.NoEditTriggers)

    def closeEvent(self, event):
        # 发出自定义的信号，表示界面将要关闭
        self.closed.emit()
        super().closeEvent(event)
        self.stop_flag = True
        print("界面关闭了")
        sys.exit()

    def taskFinished(self):
        print("运行完毕")
        if QThreadPool.globalInstance().activeThreadCount() == 0:
            self.ui.btn_run.setEnabled(True)
            add_log(0, "所有任务已结束")

    # 开始登录账号
    def start_login(self):
        row_count = self.ui.tableWidget_account.rowCount()
        for row in range(row_count):
            username = self.ui.tableWidget_account.item(row, 0).text()
            password = self.ui.tableWidget_account.item(row, 1).text()
            cookies = self.ui.tableWidget_account.item(row, 2).text()
            if cookies != "":
                # 如果有cookies，则进行测试
                login_status = detect_account_status(cookies)
                if login_status:
                    # 如果检测到登录状态正常，则将登录成功写入到表格中
                    self.ui.tableWidget_account.setItem(row, 3, QTableWidgetItem("登录成功"))
                    continue

            # 如果没有ck,则直接登录
            login_result = login(username, password)
            if login_result == "账号密码错误":
                self.ui.tableWidget_account.setItem(row, 3, QTableWidgetItem("账号密码错误"))
            else:
                print(login_result)
                self.ui.tableWidget_account.setItem(row, 2, QTableWidgetItem(login_result))
                if login_result == "":
                    self.ui.tableWidget_account.setItem(row, 3, QTableWidgetItem("登录失败"))
                else:
                    self.ui.tableWidget_account.setItem(row, 3, QTableWidgetItem("登录成功"))

    # 登录完成
    def login_finshed(self):
        if QThreadPool.globalInstance().activeThreadCount() == 0:
            print("所有账号登录完成")
            # 重新将内容写入文件
            text_ = ""
            row_count = self.ui.tableWidget_account.rowCount()
            for row in range(row_count):
                username = self.ui.tableWidget_account.item(row, 0).text()
                password = self.ui.tableWidget_account.item(row, 1).text()
                cookies = self.ui.tableWidget_account.item(row, 2).text()
                if cookies != "":
                    text_ = text_ + f"{username}----{password}----{cookies}\n"
                else:
                    text_ = text_ + f"{username}----{password}\n"

            file_path_ = Path(self.account_path)
            with file_path_.open('w', encoding='utf-8') as file:
                file.write(text_)
            self.ui.btn_account_login.setEnabled(True)

    # 查询余额
    def start_query(self):
        print("开始查询")
        row_count = self.ui.tableWidget_account.rowCount()
        for row in range(row_count):
            login_status_ = self.ui.tableWidget_account.item(row, 3)
            print("这是结果：", login_status_)
            if login_status_:
                login_status = login_status_.text()
                if login_status == "登录成功":
                    cookies_str = self.ui.tableWidget_account.item(row, 2).text()
                    cookies = cookie_str_to_dict(cookies_str)
                    mode = self.ui.comboBox_game_mode.currentIndex() + 2
                    zhanji = get_record(cookies, mode)
                    print(zhanji)
                    add_table_zhanji(row, zhanji)

    def query_finshed(self):
        if QThreadPool.globalInstance().activeThreadCount() == 0:
            print("所有账号查询完成")
            self.ui.btn_account_query.setEnabled(True)

    def buttonClick(self):
        btn = self.sender()
        btnName = btn.objectName()
        widgets = self.ui
        # 点击导入按钮
        if btnName == "btn_account_import":

            # 点击导入按钮
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly  # 设置只读选项
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(self, '选择文件', '', '文本文件 (*.txt);;所有文件 (*)',
                                                       options=options)
            if file_path:
                self.account_path = file_path
                path = Path(file_path)
                file_text = path.read_text(encoding='utf-8')
                if file_text:
                    widgets.tableWidget_account.setRowCount(0)
                    for index, line in enumerate(file_text.split('\n')):
                        arr = line.split("----")
                        if len(arr) >= 2:
                            widgets.tableWidget_account.insertRow(index)
                            account = QTableWidgetItem(arr[0])
                            password = QTableWidgetItem(arr[1])
                            cookie = QTableWidgetItem("")
                            if len(arr) == 3:
                                cookie = QTableWidgetItem(arr[2])
                            widgets.tableWidget_account.setItem(index, 0, account)
                            widgets.tableWidget_account.setItem(index, 1, password)
                            widgets.tableWidget_account.setItem(index, 2, cookie)

            else:
                print("未选择文件")

        # 点击登录按钮
        if btnName == "btn_account_login":
            self.ui.btn_account_login.setEnabled(False)  # 设置按钮不可点击，防止有傻逼连续点击
            worker = Worker(self.start_login)
            worker.signals.finished.connect(self.login_finshed)
            self.threadpool.start(worker)

        # 点击开始运行按钮
        if btnName == "btn_run":
            params = {
                'game_mode': widgets.comboBox_game_mode.currentIndex(),
                'input_money': widgets.lineEdit_input_money.text(),
                'double_number': widgets.lineEdit_double_number.text(),
                'max_money': widgets.lineEdit_max_money.text()
            }

            json_str = json.dumps(params, indent=4)
            config_path = Path("config.json")
            with config_path.open('w') as file:
                file.write(json_str)

            # 开始运行
            mode = widgets.comboBox_game_mode.currentIndex() + 2
            row_count = widgets.tableWidget_account.rowCount()
            self.stop_flag = False
            self.open_time = False
            self.log_line = 0
            self.ui.textEdit_log.clear()
            for row in range(row_count):
                # 判断是否登录成功，只有登录成功的才可以进行
                is_login_ = widgets.tableWidget_account.item(row, 3)
                if is_login_:
                    is_login = is_login_.text()
                    if is_login == "登录成功":
                        # print("进来了")
                        cookies = widgets.tableWidget_account.item(row, 2).text()
                        print(self.open_time)
                        if not self.open_time:
                            # 这里要将开奖的信息显示在UI中
                            time_param = {
                                'cookies': cookies,
                                'mode': mode
                            }
                            worker = Worker(update_open, time_param)
                            # worker.signals.finished.connect(self.taskFinished)
                            QThreadPool.globalInstance().start(worker)

                        param1 = {
                            'jinee': widgets.lineEdit_input_money.text(),
                            'max_Number': widgets.lineEdit_double_number.text(),
                            'mode': mode,
                            'index': row,
                            'cookies': cookies,
                            'max_money': widgets.lineEdit_max_money.text()
                        }
                        worker = Worker(StartTask, param1)
                        worker.signals.finished.connect(self.taskFinished)
                        QThreadPool.globalInstance().start(worker)

        # 点击清理账号按钮
        if btnName == "btn_account_clear":
            widgets.tableWidget_account.setRowCount(0)

        # 点击停止按钮
        if btnName == "btn_stop":
            print("点击了停止！")
            add_log(0, "已点击停止，等待结束")
            self.stop_flag = True
            self.open_time = False

        # 点击查询按钮
        if btnName == "btn_account_query":
            self.ui.btn_account_query.setEnabled(False)  # 设置按钮不可点击，防止有傻逼连续点击
            worker = Worker(self.start_query)
            worker.signals.finished.connect(self.query_finshed)
            self.threadpool.start(worker)


def get_code():
    while True:
        random_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        url = "https://api.juyou98.com/verifyCode?t=0." + random_number
        response = requests.get(url=url)
        if response.status_code == 200:
            # path = Path("temp.png")
            # path.write_bytes(response.content)
            # sleep(1)
            # print(response.cookies.items())
            code = image_to_string(response.content)
            code = code.replace(" ", "").replace('\n', "").replace("", "")
            if len(code) == 4:
                print('识别结果：', code)
                dit = {
                    'cookies': response.cookies.values(),
                    'code': code
                }
                return dit


def image_to_string(img):
    try:
        code = ocr.classification(img)
        return code
    except IndexError:
        return ""


def login(username, password):
    for i in range(20):
        # 先获取验证码
        code_result = get_code()
        url = "https://www.juyou98.com/loginDo.html"
        # params = {"account": username, "password": password, "verify": code_result['code']}
        params = f"mobile={username}&password={password}&verify={code_result['code']}"
        cookies = {
            "PHPSESSID": code_result['cookies'][0]
        }
        # print(code_result['code'])
        # session = requests.Session()
        # session.cookies.update(cookies)
        response = requests.post(url=url, params=params, cookies=cookies)
        # print(response.status_code)
        if response.status_code == 200:
            login_result = json.loads(response.text)
            # print(login_result)
            login_result_code = login_result['code']
            if login_result_code == 1:
                print(login_result['msg'])
                cookies_dict = requests.utils.dict_from_cookiejar(response.cookies)
                cookie_str = '; '.join([f'{name}={value}' for name, value in cookies_dict.items()])
                print("这是返回的cookies", cookie_str)
                return cookie_str
            elif login_result_code == 0:
                msg = login_result['msg']
                if msg == "账号密码错误":
                    return "账号密码错误"

    return ""


def cookie_str_to_dict(cookies_str):
    cookies_dict = http.cookies.SimpleCookie()
    cookies_dict.load(cookies_str)
    cookies_dict = {key: morsel.value for key, morsel in cookies_dict.items()}
    return cookies_dict


def detect_account_status(cookies_str):
    """测试账号的Cookies是否正常"""
    url = 'https://www.juyou98.com/userInfo.html'
    cookies_dict = cookie_str_to_dict(cookies_str)
    # print("这是cookies_dict:", type(cookies_dict))
    response = requests.get(url=url, cookies=cookies_dict)
    if response.status_code == 200:
        # 寻找用户名是否存在
        pattern = '欢迎回来，<strong>(.*?)</strong>'
        try:
            username = re.findall(pattern=pattern, string=response.text)[0]
            if username != "":
                return True
            else:
                return False
        except Exception:
            return False
    else:
        return False


def get_period_id(cookies, gameid):
    url = "https://www.juyou98.com/gameIndex/2"
    response = requests.get(url=url, cookies=cookies)
    # print(response.status_code)
    if response.status_code == 200:
        # print(response.text)
        tree = etree.HTML(response.text)
        tbody = tree.xpath('//tbody/tr')
        for list in tbody:
            game_id = list.xpath('./td[1]/text()')[0]  # 游戏期号
            # game_open_time = list.xpath('./td[2]/text()')[0]  # 开奖时间
            # game_open_result = list.xpath('./td[3]/text()')[0]  # 解密结果
            # game_total = list.xpath('./td[4]/text()')[0]  # 奖池金额
            # game_people_number = list.xpath('./td[5]/text()')[0]  # 中奖人数
            # game_statistics = list.xpath('./td[6]/text()')[0]  # 投入/收入
            # game_participate = list.xpath('./td[7]/text()')[0]  # 开奖状态
            # print(game_id, game_open_time, game_open_result, game_total, game_people_number, game_statistics,game_participate)
            if gameid == game_id:
                game_canyu = str(list.xpath('./td[7]/button/@onclick')[0])
                game_canyu = re.findall(r'\d+', game_canyu)[0]
                # print(game_canyu)
                return game_canyu


def getgameNow(cookies_str, mode):
    # 2：急速60
    # 3：开心90
    # 4：欢乐210
    url = 'https://www.juyou98.com/gameNow/' + str(mode)
    response = requests.post(url=url, cookies=cookies_str)
    if response.status_code == 200:
        return response.text
    else:
        return {'code': -1, 'open': {'status': False}}


def determine_remainder(num):
    """判断余数，并返回组合"""
    filepath = Path("规则.txt")
    rema = num % 5
    try:
        print("使用自定义规则")
        file_text = filepath.read_text(encoding='utf-8')
        file_text = file_text.replace('：', ':').replace('，', ',')
        result = {}
        for line in file_text.split('\n'):
            parts = line.split(':')  # 按冒号分割键和值
            if len(parts) == 2:
                key = int(parts[0])  # 第一个部分是键
                values = [int(x) for x in parts[1].split(',')]  # 第二个部分是逗号分隔的值，将它们转换为整数
                result[key] = values
        return result[rema]
    except Exception as e:
        print(e)
        print("使用软件默认规则")
        if rema == 0:
            return [0, 2]
        elif rema == 1:
            return [1, 2]
        elif rema == 2:
            return [0, 2]
        elif rema == 3:
            return [3, 4]
        elif rema == 4:
            return [3, 4]


def determine(num1, num2, num3):
    if num1 == num2 == num3:
        return False
    elif num1 == num2 or num1 == num3 or num2 == num3:
        return True
    else:
        return False


def StartTask(_dict):
    # print("传输的参数：", _dict)
    max_Number = int(_dict['max_Number']) - 1  # 最多翻的次数
    jinee = int(_dict['jinee'])  # 押注金额
    cookies_str = _dict['cookies']
    mode = _dict['mode']
    index = _dict['index']  # 记录列表框中的索引，方便写日志
    max_money = int(_dict['max_money'])  # 设置上限
    First_dict = {}
    cookies = cookie_str_to_dict(cookies_str)
    window.ui.btn_run.setEnabled(False)
    while not window.stop_flag:
        # 获取最新开奖结果，并获取所有数字
        try:
            result = json.loads(getgameNow(cookies_str=cookies, mode=mode))
            print(result)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误：{e}")
            result = {'code': -1, 'open': {'status': False}}

        code = int(result['code'])
        open_status = result['open']['status']
        if code == 1 and open_status:
            try:
                num1 = int(result['open']['num1'])
                num2 = int(result['open']['num2'])
                num3 = int(result['open']['num3'])
                num = int(result['open']['num'])
                game_no = int(result['open']['game_no'])
                delay_time = int(result['time']['delay'])
                le = Path('记录.txt')
                with le.open('a') as file:
                    file.write(f"{str(game_no)}  {str(num1)}+{str(num2)}+{str(num3)}={str(num)}\n")
            except KeyError:
                add_log(index, "读取数据出错")
                print("读取数据出错")
                continue

            if not First_dict:
                # 先判断是否有对子，如果有对子再往下执行
                is_duizi = determine(num1, num2, num3)
                if is_duizi:
                    First_dict = {
                        'num1': num1,
                        'num2': num2,
                        'num3': num3,
                        'num': num,
                        'game_no': game_no,
                        'open_game_no': game_no + 2,
                        'xia': 0,
                        'xiaJine': 0
                    }
                    print("下期投注期数：", First_dict['open_game_no'])
                    add_table_status(index, f"下期投注期数：{First_dict['open_game_no']}")
                    sleep(delay_time)
                else:
                    print("没有对子，延时")
                    add_table_status(index, "没有特性牌，等待延时")
                    sleep(delay_time)
            elif game_no != First_dict['game_no']:
                # print("当前已开奖期数：%d" % game_no)
                # 判断本次是否也有对子，如果有对子则继续将投注期号往后延1
                is_duizi = determine(num1, num2, num3)
                # 判断本次号码的规则是否和检测的对子的规则相同
                is_zuhe = (determine_remainder(num) == determine_remainder(First_dict['num']))
                print("是否重复", is_zuhe)
                print('原始数据：', num, First_dict['num'])
                print('计算余数：', determine_remainder(num), determine_remainder(First_dict['num']))

                if is_zuhe and First_dict['xia'] < 1:
                    print("本次开奖结果为上把结果的规则，等待本局计时结束重新开始")
                    add_table_status(0, "本次开奖结果为上把结果的规则，等待本局计时结束重新开始")
                    First_dict.clear()
                    sleep(delay_time)
                    continue

                if is_duizi and First_dict['xia'] < 1:
                    print(f"又出现了对顺豹{num1},{num2},{num3}，等待本局结束，下局开奖")
                    add_table_status(index, f"又出现了特性牌{num1},{num2},{num3}，等待本局结束，下局开奖")
                    # 这里需要处理出现2次以上的情况
                    # 处理思路是当下局开奖结果不为对子、豹子、顺子时跳出循环
                    sleep(delay_time + 2)
                    while True:
                        # 判断是否新局是否还是对子
                        try:
                            new_result = json.loads(getgameNow(cookies_str=cookies, mode=mode))
                        except json.JSONDecodeError as e:
                            print(f"判断中json解析错误：{e}")
                            new_result = {'code': -1, 'open': {'status': False}}

                        if new_result['code'] == 1 and new_result['open']['status']:
                            try:
                                num1_ = int(new_result['open']['num1'])
                                num2_ = int(new_result['open']['num2'])
                                num3_ = int(new_result['open']['num3'])
                                num_ = int(new_result['open']['num'])
                                is_duizi_new = determine(num1_, num2_, num3_)
                                # is_zuhe_new = determine_remainder(First_dict['num']) != determine_remainder(num_)
                                if not is_duizi_new:
                                    break
                                else:
                                    print("又出现了设定型数字，等待延时")
                                    add_table_status(index,
                                                     f"又出现了特性牌{num1_},{num2_},{num3_}，等待本局结束，下局开奖")
                                    sleep(new_result['time']['endTime'])
                            except KeyError:
                                add_log(0, "判断二次特性出错")
                                continue

                    # 如果再次出现，则退出
                    First_dict.clear()
                    continue
                # 判断开奖号和首次获取的差，如果大于3则全部归零重新开始,符合投注期号，则进行投注
                if game_no >= First_dict['open_game_no'] - 1 and int(First_dict['xia']) <= max_Number:
                    random_delay_time = random.randint(10, 20)
                    print(f"等待投注，随机延时{random_delay_time}秒")
                    add_table_status(index, f"等待投注，随机延时{random_delay_time}秒")
                    sleep(random_delay_time)
                    print("开始投注，初始开奖的号码为：" + str(First_dict['num']))
                    add_table_status(index, "开始投注，初始开奖的号码为：" + str(First_dict['num']))
                    rema = determine_remainder(int(First_dict['num']))
                    if First_dict['xiaJine'] == 0:
                        First_dict['xiaJine'] = int(jinee)  # 初始化第一次投注的金额
                    else:
                        First_dict['xiaJine'] = int(First_dict['xiaJine']) * 2  # 如果已经投注过，则将金额翻倍
                    period_id = get_period_id(cookies, result['time']['game_no'])
                    url = 'https://www.juyou98.com/gameJoinDo.html'
                    for i in range(len(rema)):
                        params = set_value(mode, rema[i], First_dict['xiaJine'], period_id)
                        # print(params)
                        response = requests.post(url=url, params=params, cookies=cookies)
                        if response.status_code == 200:
                            try:
                                print(response.text)
                                resp_json = json.loads(response.text)
                                if resp_json['code'] == 1:
                                    print(
                                        f"在第{result['time']['game_no']}期，下5余{rema[i]}成功,下注金额为{First_dict['xiaJine']}")
                                    add_table_status(index,
                                                     f"在第{result['time']['game_no']}期，下5余{rema[i]}成功,下注金额为{First_dict['xiaJine']}")
                                elif resp_json['code'] == 0:
                                    add_table_status(index, "下注出错：" + resp_json['msg'])
                            except KeyError:
                                print("下注出错")
                                add_table_status(index, "下注出错")

                    try:
                        # 将下的次数写入字典
                        First_dict['xia'] = int(First_dict['xia']) + 1
                        print(f"第{First_dict['xia']}次投注完成")
                        add_table_status(index,
                                         f"第{First_dict['xia']}次投注完成，共投注：{str(int(First_dict['xiaJine']) * 2)}")
                        print("开始延时")
                        delay_time_ = int(delay_time) + 3 - random_delay_time
                        sleep(delay_time_)
                    except Exception as e:
                        print(f"投注位置出现错误：{e}")

                    # 判断开奖结果
                    print("延时结束，准备判断开奖结果")
                    while True:
                        try:
                            susses = json.loads(getgameNow(cookies_str=cookies, mode=mode))
                        except json.JSONDecodeError as e:
                            print(f"判断开奖出错：{e}")
                            susses = {'code': -1, 'open': {'status': False}, 'time:': {'game_no': '932581'}}
                        print("开奖的文本：", susses)
                        open_game_no = susses['open']['game_no']
                        open_game_status = susses['open']['status']
                        open_game_no_old = result['time']['game_no']
                        if susses['code'] == 1 and open_game_status and open_game_no == open_game_no_old:
                            open_num = susses['open']['num']
                            open_num1 = susses['open']['num1']
                            open_num2 = susses['open']['num2']
                            open_num3 = susses['open']['num3']
                            yushu = open_num % 5
                            if yushu == rema[0] or yushu == rema[1]:
                                print(f"恭喜中奖，开奖为{open_num1}+{open_num2}+{open_num3}={open_num}")
                                zhanji = get_record(cookies, mode)
                                # print(f"目前战绩：", zhanji, "等待本局完成")
                                add_table_status(index,
                                                 f"恭喜中奖，开奖为{open_num1}+{open_num2}+{open_num3}={open_num}，等待本局完成")
                                add_table_zhanji(index, zhanji)
                                if int(zhanji['zhanji']) >= int(max_money):
                                    add_table_zhanji(index, "今日战绩已达上限！")
                                    return
                                First_dict.clear()
                                print("延时1")
                                time_ = susses['time']['endTime']
                                print(f"延时：{time_}")
                                sleep(time_)
                                print("延时1结束")
                                break
                            else:
                                print("没有中奖")
                                zhanji = get_record(cookies, mode)
                                add_table_zhanji(index, zhanji)
                                add_table_status(index, "没有中奖")
                                # sleep(susses['time']['endTime'])
                                break

                elif int(First_dict['xia']) > int(max_Number):
                    print("翻倍超过上限，重新开始")
                    add_table_status(index, "翻倍超过上限，重新开始")
                    First_dict.clear()
            else:
                print('延时：', delay_time)
                add_table_status(index, "等待延时")
                sleep(delay_time)


def get_record(cookies, mode):
    """获取战绩，做到止盈止损"""
    url = 'https://www.juyou98.com/game.html?game=' + str(mode)
    response = requests.get(url=url, cookies=cookies)
    if response.status_code == 200:
        # print(response.text)
        try:
            zhaji = re.findall(pattern='今日战绩：(.*?)<i', string=response.text)
            jindou = re.findall(pattern='金豆：<strong>(.*?)</strong>', string=response.text)
            params = {
                'zhanji': int(str(zhaji[0]).replace(',', '')),
                'jindou': int(str(jindou[0]).replace(',', ''))
            }
            return params
        except Exception:
            params = {
                'zhanji': 0,
                'jindou': 0
            }
            return params

    return 0


def set_value(mode, value, total, period_id):
    """提交下注的参数"""
    # mode：玩法
    # value：5余几
    # total：投注金额

    init_value = {
        0: 1,
        1: 3,
        2: 6,
        3: 10,
        4: 15,
        5: 21,
        6: 28,
        7: 36,
        8: 45,
        9: 55,
        10: 63,
        11: 69,
        12: 73,
        13: 75,
        14: 75,
        15: 73,
        16: 69,
        17: 63,
        18: 55,
        19: 45,
        20: 36,
        21: 28,
        22: 21,
        23: 15,
        24: 10,
        25: 6,
        26: 3,
        27: 1
    }
    result = f"game={mode}&total={total}"

    for i in range(28):

        if i % 5 == value:
            result = result + "&bet_num[]=" + str(int(int(total) / 200 * init_value[i]))
        else:
            result = result + "&bet_num[]="

    result = result + "&period_id=" + period_id
    return result


def add_table_status(index, _text):
    window.ui.tableWidget_account.setItem(index, 6, QTableWidgetItem(_text))
    add_log(index, _text)


def add_table_zhanji(index, _text):
    zhanji = _text['zhanji']
    jindou = _text['jindou']
    window.ui.tableWidget_account.setItem(index, 5, QTableWidgetItem(str(zhanji)))
    window.ui.tableWidget_account.setItem(index, 4, QTableWidgetItem(str(jindou)))


def add_log(index, _text):
    current_time = time.time()  # 获取当前时间戳
    formatted_time = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')  # 格式化时间为字符串
    username = window.ui.tableWidget_account.item(index, 0).text()
    window.ui.textEdit_log.append(f'[{formatted_time}] {username}===>{_text}')
    cursor = window.ui.textEdit_log.textCursor()
    cursor.movePosition(QTextCursor.End)
    window.ui.textEdit_log.setTextCursor(cursor)
    window.log_line += 1
    # print(window.log_line)
    if window.log_line > 250:
        window.log_line = 0
        window.ui.textEdit_log.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
