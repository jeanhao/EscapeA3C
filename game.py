#!/usr/bin/python2.7
# encoding: utf-8
import pygame
import sys
import random
from collections import deque
from pygame.locals import *  # @UnusedWildImport



pygame.init()

FPS = 60
SCREENWIDTH = 200
SCREENHEIGHT = 300

score_font = pygame.font.SysFont("arial", 15)

FPSCLOCK = pygame.time.Clock()
SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT))
pygame.display.set_caption('Escape')

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

LINE_Y = 20

OBJECT_WIDTH = 50

PLAYER_HEIGHT = 50
PLAYER_POS_Y = SCREENHEIGHT - PLAYER_HEIGHT

PLAYER_SIZE = (OBJECT_WIDTH, PLAYER_HEIGHT)

MAX_PLAYER_POS = int(SCREENWIDTH / OBJECT_WIDTH) - 2

STONE_INIT_POS_Y = 0  # 石头初始化位置
STONE_POS_X = [0, 50, 100]
STONE_UPDATE_DISTANCE = 150  # 两层石头间的距离

SCORE_SPEED_RECORD_TIME_INTERVAL = 1000  # 每两秒记录一次
SAVE_SPPED_FLAG = 100  # 保存次数
class GameObject(object):

    def __init__(self, render=True):

        self.render = render
        self.init()
        self.score = 0
        # 用于统计速度
        self.last_score = deque([0])
        self.last_score_time = deque([0])
        self.speed = 0
        self.save_spped_index = 1

    def init(self):
        self.play = False
        self.player_pos = 1
        self.stone_speed_y = 5
        self.stones = deque()

    def welcome(self):
        SCREEN.fill(BLACK)
        score_surface = score_font.render("Click space to start game", True, WHITE)
        SCREEN.blit(score_surface, (25, 140))
        pygame.display.update()
        self.__init__()  # 更彻底地初始化，包括得分
        while not self.play:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_UP):
                    pygame.quit()
                    sys.exit()
                if event.type == KEYDOWN:
                    if event.key == K_SPACE:
                        self.play = True
            FPSCLOCK.tick(FPS)  # 一帧后处理下个事件
        # 初始化游戏数据
        self.start()

    def start(self):
        while True:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_UP):
                    pygame.quit()
                    sys.exit()
                if event.type == KEYDOWN:
                    if event.key == K_LEFT:
                        self.player_pos = max(self.player_pos - 1, 0)
                    elif event.key == K_RIGHT:
                        self.player_pos = min(self.player_pos + 1, MAX_PLAYER_POS)

            reward = self.update_stones()
            if reward == -1:  # 游戏结束
                self.score -= 1
                self.welcome()
            else:
                self.score += reward

            # 更新画面
            self.update_score_speed()
            self.update_screen()
            FPSCLOCK.tick(FPS)  # 一帧后处理下个事件

    def update_screen(self):
        # 重绘背景
        SCREEN.fill(BLACK)
        # 画右边部分，目前有分数和速度
        pygame.draw.line(SCREEN, WHITE, (SCREENWIDTH - 50, 0), (SCREENWIDTH - 50, SCREENHEIGHT))
        score_text_surface = score_font.render("score", True, WHITE)
        SCREEN.blit(score_text_surface, (160, 0))
        score_surface = score_font.render(str(self.score), True, WHITE)
        SCREEN.blit(score_surface, (160, 20))

        score_text_surface = score_font.render("speed", True, WHITE)
        SCREEN.blit(score_text_surface, (160, 40))
        score_surface = score_font.render(str(self.speed), True, WHITE)
        SCREEN.blit(score_surface, (160, 60))


        # 画主角
        pygame.draw.rect(SCREEN, WHITE, Rect((self.player_pos * OBJECT_WIDTH, PLAYER_POS_Y), PLAYER_SIZE))
        # 画石头
        for stones_row in self.stones:
            for stone_pos in stones_row:
                pygame.draw.rect(SCREEN, WHITE, Rect(stone_pos, PLAYER_SIZE))
        pygame.display.update()

    def gen_stones(self):  # 随机生成两个位置
        return [[pos, STONE_INIT_POS_Y] for pos in random.sample(STONE_POS_X, 2)]

    def update_stones(self):
        # 看是否需要产生新的石头
        if not self.stones:  # 如果没有石头
            self.stones.append(self.gen_stones())
        else:
            # 获取最后一组stone的第一个的其y坐标
            last_stone_y = self.stones[-1][0][1]
            if last_stone_y > STONE_UPDATE_DISTANCE:
                self.stones.append(self.gen_stones())

        # 更新所有石头距离
        for row in range(len(self.stones)):
            # 目前是两块，直接写死
            self.stones[row][0][1] += self.stone_speed_y  # 第1块石头y坐标
            self.stones[row][1][1] += self.stone_speed_y  # 第2块石头y坐标

        # 检查第一组石头是否和player发生碰撞
        stone_y = self.stones[0][0][1]

        reward = 0
        if SCREENHEIGHT >= stone_y > SCREENHEIGHT - PLAYER_HEIGHT * 2 :  # 检查两个石头是否和用户发生碰撞
            if self.stones[0][0][0] / OBJECT_WIDTH == self.player_pos or self.stones[0][1][0] / OBJECT_WIDTH == self.player_pos:  # 发生了碰撞
                reward = -1
        elif stone_y > SCREENHEIGHT:  # 已经过了，给用户加分
            reward = 1
            self.stones.popleft()  # 清空两块石头

        return reward

    # 下面是训练相关
    def frame_step(self, input_actions):
        pygame.event.pump()

#         if sum(input_actions) != 1:
#             raise ValueError('Multiple input actions!')

        # input_actions[0] == 1: do nothing
        # input_actions[1] == 1: left
        # input_actions[2] == 1: right
        if input_actions == 1:
#         if input_actions[1] == 1:
            self.player_pos = max(self.player_pos - 1, 0)
        if input_actions == 2:
#         elif input_actions[2] == 1:
            self.player_pos = min(self.player_pos + 1, MAX_PLAYER_POS)

        reward = self.update_stones()

        self.score += reward
        if reward == -1:  # 发生了碰撞
            self.init()

        # 更新速度
        self.update_score_speed()
        image_data = pygame.surfarray.array3d(pygame.display.get_surface())[:150]
        self.update_screen()

        FPSCLOCK.tick(FPS)
        return image_data, reward

    def update_score_speed(self):  # 更新速度
        if pygame.time.get_ticks() - self.last_score_time[-1] > SCORE_SPEED_RECORD_TIME_INTERVAL:  # 超过记录长度，可以开始记录
            if(len(self.last_score) >= 10):
                self.speed = (self.score - self.last_score.popleft()) / (pygame.time.get_ticks() - self.last_score_time.popleft()) * 1000
            self.last_score_time.append(pygame.time.get_ticks())
            self.last_score.append(self.score)
            if self.save_spped_index >= SAVE_SPPED_FLAG:
                self.save_spped_flag = 1
                with open('speeds_file.txt', 'a') as f:
                    f.write("time:%s, score:%5f, speed:%5f\n" % (str(pygame.time.get_ticks()), self.score, self.speed))
            else:
                self.save_spped_index += 1


if __name__ == '__main__':
        GameObject().welcome()
