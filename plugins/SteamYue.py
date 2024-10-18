import os
import pickle
import time
from datetime import datetime

import json5
import json
import random

import apprise
from apprise import AppriseAsset
from steampy.models import GameOptions

from utils.logger import PluginLogger, handle_caught_exception
from utils.static import SESSION_FOLDER


class SteamYue:
    def __init__(self, steam_client, steam_client_mutex, config):
        self.logger = PluginLogger('SteamYue')
        self.steam_client = steam_client
        self.steam_client_mutex = steam_client_mutex
        self.config = config
        
        self.send_msg = apprise.Apprise()
        for server in self.config["buff_auto_accept_offer"]["servers"]:
            self.send_msg.add(server)
        self.list = []


    def init(self):
        return False


    def load_list(self):
        """从 JSON 文件加载列表"""
        list_path = os.path.join(SESSION_FOLDER, f"{self.steam_client.username.lower()}_list.json")
        if os.path.exists(list_path):
            try:
                with open(list_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error("无法解析 JSON 文件, 初始化为空列表")
                return []
        return []
    

    def load_list(self):
        """从 JSON 文件加载列表"""
        list_path = os.path.join(SESSION_FOLDER, f"{self.steam_client.username.lower()}_list.json")
        
        if os.path.exists(list_path):
            # 获取当前时间和文件最后修改时间
            file_mod_time = os.path.getmtime(list_path)
            current_time = time.time()
            
            # 检查文件修改时间是否超过 24 小时
            if current_time - file_mod_time > 24 * 60 * 60:
                self.logger.info("历史余额和库存文件超过24小时未修改，初始化为空列表")
                return []  # 文件修改时间超过24小时，返回空列表

            try:
                # 读取文件内容
                with open(list_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error("无法解析 JSON 文件, 初始化为空列表")
                return []
        return []


    def save_list(self):
        """保存列表为 JSON 文件"""
        if len(self.list) > 0:
            list_path = os.path.join(SESSION_FOLDER, f"{self.steam_client.username.lower()}_list.json")
            with open(list_path, "w", encoding="utf-8") as f:
                json.dump(self.list, f, ensure_ascii=False, indent=4)
        

    def exec(self):
        wait_time = random.randint(5, 50)
        self.logger = PluginLogger('启动插件')
        self.logger.info(f"余额查询，{wait_time}秒后正式启动")
        self.logger = PluginLogger('SteamYue')
        time.sleep(wait_time)

        self.list = self.load_list()
        while True:
            try:
                with self.steam_client_mutex:
                    if not self.steam_client.is_session_alive():
                        self.logger.info("Steam会话已过期, 正在重新登录...")
                        self.steam_client._session.cookies.clear()
                        self.steam_client.login(
                            self.steam_client.username, self.steam_client._password, json5.dumps(self.steam_client.steam_guard)
                        )
                        self.logger.info("Steam会话已更新")
                        steam_session_path = os.path.join(SESSION_FOLDER, self.steam_client.username.lower() + ".pkl")
                        with open(steam_session_path, "wb") as f:
                            pickle.dump(self.steam_client.session, f)
                with self.steam_client_mutex:
                    trade_summary = self.steam_client.get_my_inventory(game=GameOptions.CS) 
                    kucun = len(trade_summary)
                    try:
                        amount = self.steam_client.get_wallet_balance(False) 
                    except Exception as e:
                        amount = 'err'
                    current_time = datetime.now()
                    if len(self.list) >= 15:
                        self.list.pop(0)
                    self.list.append({"time":f'[{current_time.strftime("%H:%M")}]', 'amount': amount, 'kucun':f'{kucun}'})
                    title = f'[{self.steam_client.username}] 余额 - {amount} - {kucun}'
                    msg = ''
                    self.logger.info(f'{title}')
                    for li in self.list:
                        msg += f"{li['time']} - {li['amount']} - {li['kucun']}\n"
                    self.logger.info(msg)
                    self.send_msg.notify(
                        title = title,
                        body = msg,
                    )

            except Exception as e:
                handle_caught_exception(e, "SteamAutoAcceptOffer")
                self.logger.error("发生未知错误！稍后再试...")
                
            # 保存列表
            self.save_list()

            # 获取当前时间
            current_time = datetime.now()
            # 获取当前小时
            current_hour = current_time.hour
            if 0 <= current_hour < 8:
                time0 = self.config["steam_yue"]["jiange_hei"] * 60
                self.logger.info(f"等待{time0 / 60}分钟")
                time.sleep(time0)
            else:
                time0 = self.config["steam_yue"]["jiange_bai"] * 60
                self.logger.info(f"等待{time0 / 60}分钟")
                time.sleep(time0)
      
    def __del__(self):
        """程序退出时自动保存列表"""
        self.save_list()
        self.logger.info("查余额插件已关闭")

