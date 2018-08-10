import time
import random
import logging
import requests
import planet_sql
from utils import robot
from planet import Planet
from datetime import datetime
from threading import Thread
from planet_spider import PlanetSpider


class PlanetRobot:
    def __init__(self, spider):
        self.spider = spider

    def user_dynamic(self):
        """获得全局的动态列表
        
        """

        sleep_time = random.randint(180, 300)
        data = {"list": 'explore', "offset": 0, "pagesize": 20}
        api = 'https://www.quanquanyuanyuan.cn/huodong/dog/api/tlmsg/list'

        logging.info('Start to get users dynamic')
        while True:
            resp = requests.post(api, json=data, headers=Planet.headers).json()

            messages = resp['messages']
            for index, message in enumerate(messages):
                msg_id = message['id']  # 消息id
                msg_user_id = message['user_id']  # 用户id
                comment = message['comment']  # 动态内容
                disable_comment = message['disable_comment']  # 是否关闭了评论
                tl_hash = resp['tl_hashes'][index]  # 动态hash值
                msg_type = message['msg_type']  # 消息类型
                if msg_type == 'Text':
                    comment = message['message']['text']['Text']

                user = resp['users'][index]
                user_hash = resp['uid_hashes'][index]
                key = 'planet:u:{0}:m:{1}:comment'.format(msg_user_id, msg_id)
                if not self.spider.redis.exists(key):
                    self.spider.parse(user, user_hash)

                if not disable_comment:
                    recent_comment = resp['recent_comments'][index]
                    # 无评论或者评论里没有机器人的回复
                    if not recent_comment:
                        comment_msg = robot.call_text_v1(comment, msg_user_id)
                        self.__robot_comment(msg_id, comment_msg, tl_hash, msg_user_id)

            logging.info('Dynamic to sleep , sleep time is %d', sleep_time)
            time.sleep(sleep_time)
            sleep_time = random.randint(180, 300)
            logging.info('Dynamic end sleep , next sleep time is %d', sleep_time)

    def reply_robot(self):
        """回复机器人的评论

        """

        data = {"offset": 0}
        sleep_time = random.randint(60, 90)
        api = 'https://www.quanquanyuanyuan.cn/huodong/dog/api/v2/tlmsg/comments/my-received'
        logging.info('Start to get reply robot')
        while True:
            resp = requests.post(api, json=data, headers=Planet.headers).json()

            now = datetime.now()
            comments = resp['comments']
            for index, comment in enumerate(comments):
                comment_id = comment['id']  # 评论id
                user_id = comment['user_id']  # 评论用户id
                msg_id = comment['tl_id']  # 动态id

                key = 'planet:u:{0}:m:{1}:comment'.format(user_id, msg_id)
                is_member = self.spider.redis.sismember(key, comment_id)
                if not is_member:
                    self.spider.redis.sadd(key, comment_id)
                    comment_time = comment['ctime']  # 回复时间
                    text = comment['message']['text']['Text']  # 回复内容

                    effect_count = self.spider.handler(planet_sql.add_user_comment(),
                                                       (comment_id, user_id, msg_id, text, comment_time, now))
                    if effect_count != 0:
                        comment_msg = robot.call_text_v1(text, user_id)
                        tl_hash = resp['tl_hashes'][index]
                        self.__robot_comment(msg_id, comment_msg, tl_hash, user_id)

            logging.info('Reply robot to sleep , sleep time is %d', sleep_time)
            time.sleep(sleep_time)
            sleep_time = random.randint(60, 90)
            logging.info('Reply robot end sleep , next sleep time is %d', sleep_time)

    def __robot_comment(self, msg_id, comment_msg, tl_hash, to_user_id):
        """机器人评论动态或回复评论
        
        :param msg_id: 动态id
        :param comment_msg: 内容
        :param tl_hash: 动态hash
        :param to_user_id: 目标用户id
        """

        api = 'https://www.quanquanyuanyuan.cn/huodong/dog/api/tlmsg/comment/add'
        data = {"tl_id": msg_id, "message": comment_msg, "hash": tl_hash, "to_user_id": to_user_id}
        resp = requests.post(api, json=data, headers=Planet.headers).json()

        comment = resp.get('comment')
        if comment:
            comment_id = comment['id']  # 评论id
            comment_time = comment['ctime']  # 评论时间

            key = 'planet:u:{0}:m:{1}:comment'.format(to_user_id, msg_id)
            self.spider.redis.sadd(key, comment_id)

            self.spider.handler(planet_sql.add_user_comment(),
                                (comment_id, Planet.my_user_id, msg_id, comment_msg, comment_time, datetime.now()))


# 程序入口
if __name__ == '__main__':
    ps = PlanetSpider()
    pr = PlanetRobot(ps)

    t1 = Thread(target=pr.user_dynamic, name='Thread-1')
    t2 = Thread(target=pr.reply_robot, name='Thread-2')

    t1.start()
    t2.start()