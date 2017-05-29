import gym
import time
import random
import threading
import numpy as np
import tensorflow as tf
from skimage.color import rgb2gray
from skimage.transform import resize
from keras.models import Model
from keras.optimizers import RMSprop
from keras.layers import Dense, Flatten, Input
from keras.layers.convolutional import Conv2D
from keras import backend as K
from game import GameObject

# global variables for A3C
global episode
episode = 0
EPISODES = 8000000
THREAD_NUM = 1
# In case of BreakoutDeterministic-v3, always skip 4 frames
# Deterministic-v4 version use 4 actions
# env_name = "BreakoutDeterministic-v4"

# This is A3C(Asynchronous Advantage Actor Critic) agent(global) for the Cartpole
# In this example, we use A3C algorithm
class A3CAgent:
    def __init__(self, action_size):
        # environment settings
        self.state_size = (9, 36, 4)
        self.action_size = action_size

        self.discount_factor = 0.99
        self.no_op_steps = 30

        # optimizer parameters
        self.actor_lr = 2.5e-4
        self.critic_lr = 2.5e-4
        self.threads = THREAD_NUM

        # create model for actor and critic network
        self.actor, self.critic = self.build_model()

        # method for training actor and critic network
        self.optimizer = [self.actor_optimizer(), self.critic_optimizer()]

        self.sess = tf.InteractiveSession()
        K.set_session(self.sess)
        self.sess.run(tf.global_variables_initializer())

#         self.summary_placeholders, self.update_ops, self.summary_op = self.setup_summary()
#         self.summary_writer = tf.summary.FileWriter('summary/Breakout_A3C', self.sess.graph)

    def train(self):
        # self.load_model("./save_model/Breakout_A3C")
        agents = [Agent(self.action_size, self.state_size, [self.actor, self.critic], self.sess, self.optimizer,
                        self.discount_factor) for _ in range(self.threads)]

        for agent in agents:
            time.sleep(1)
            agent.start()

        while True:
            time.sleep(60 * 5)
            self.save_model("./save_model/Breakout_A3C")

    # approximate policy and value using Neural Network
    # actor -> state is input and probability of each action is output of network
    # critic -> state is input and value of state is output of network
    # actor and critic network share first hidden layer
    def build_model(self):
        input = Input(shape=self.state_size)
        conv = Conv2D(16, (3, 8), strides=(3, 3), activation='relu')(input)
        conv = Conv2D(32, (2, 2), strides=(2, 2), activation='relu')(conv)
#         conv = Conv2D(32, (3, 3), strides=(1, 1), activation='relu')(conv)
        conv = Flatten()(conv)
        fc = Dense(160, activation='relu')(conv)
        policy = Dense(self.action_size, activation='softmax')(fc)
        value = Dense(1, activation='linear')(fc)

        actor = Model(inputs=input, outputs=policy)
        critic = Model(inputs=input, outputs=value)

        actor.predict(np.random.rand(1, 9, 36, 4))
        critic.predict(np.random.rand(1, 9, 36, 4))

#         actor.summary()
#         critic.summary()

        return actor, critic

    # make loss function for Policy Gradient
    # [log(action probability) * advantages] will be input for the back prop
    # we add entropy of action probability to loss
    def actor_optimizer(self):
        action = K.placeholder(shape=[None, self.action_size])
        advantages = K.placeholder(shape=[None, ])

        policy = self.actor.output

        good_prob = K.sum(action * policy, axis=1)
        eligibility = K.log(good_prob + 1e-10) * advantages
        actor_loss = -K.sum(eligibility)

        entropy = K.sum(policy * K.log(policy + 1e-10), axis=1)
        entropy = K.sum(entropy)

        loss = actor_loss + 0.01 * entropy
        optimizer = RMSprop(lr=self.actor_lr, rho=0.99, epsilon=0.01)
        updates = optimizer.get_updates(self.actor.trainable_weights, [], loss)
        train = K.function([self.actor.input, action, advantages], [loss], updates=updates)

        return train

    # make loss function for Value approximation
    def critic_optimizer(self):
        discounted_reward = K.placeholder(shape=(None,))

        value = self.critic.output

        loss = K.mean(K.square(discounted_reward - value))

        optimizer = RMSprop(lr=self.critic_lr, rho=0.99, epsilon=0.01)
        updates = optimizer.get_updates(self.critic.trainable_weights, [], loss)
        train = K.function([self.critic.input, discounted_reward], [loss], updates=updates)
        return train

    def load_model(self, name):
        self.actor.load_weights(name + "_actor.h5")
        self.critic.load_weights(name + "_critic.h5")

    def save_model(self, name):
        self.actor.save_weights(name + "_actor.h5")
        self.critic.save_weights(name + '_critic.h5')

    # make summary operators for tensorboard
    def setup_summary(self):
        episode_total_reward = tf.Variable(0.)
        episode_avg_max_q = tf.Variable(0.)
        episode_duration = tf.Variable(0.)

        tf.summary.scalar('Total Reward/Episode', episode_total_reward)
        tf.summary.scalar('Average Max Prob/Episode', episode_avg_max_q)
        tf.summary.scalar('Duration/Episode', episode_duration)

        summary_vars = [episode_total_reward, episode_avg_max_q, episode_duration]
        summary_placeholders = [tf.placeholder(tf.float32) for _ in range(len(summary_vars))]
        update_ops = [summary_vars[i].assign(summary_placeholders[i]) for i in range(len(summary_vars))]
        summary_op = tf.summary.merge_all()
        return summary_placeholders, update_ops, summary_op

# make agents(local) and start training
class Agent(threading.Thread):
    def __init__(self, action_size, state_size, model, sess, optimizer, discount_factor):
        threading.Thread.__init__(self)

        self.action_size = action_size
        self.state_size = state_size
        self.actor, self.critic = model
        self.sess = sess
        self.optimizer = optimizer
        self.discount_factor = discount_factor
#         self.summary_op, self.summary_placeholders, self.update_ops, self.summary_writer = summary_ops

        self.states, self.actions, self.rewards = [], [], []

        self.avg_p_max = 0
        self.avg_loss = 0

        # t_max -> max batch size for training
        self.t_max = 20
        self.t = 0

    # Thread interactive with environment
    def run(self):
        # self.load_model('./save_model/Breakout_A3C')
        global episode

        game = GameObject(True)
        step = 0

        while episode < EPISODES:
            dead = False
            score = 0
            observe = game.frame_step(0)
            next_observe = observe

            # this is one of DeepMind's idea.
            # just do nothing at the start of episode to avoid sub-optimal
            for _ in range(random.randint(1, 5)):
                observe = next_observe
                next_observe, _ = game.frame_step(0)

            # At start of episode, there is no preceding frame. So just copy initial states to make history
            state = pre_processing(next_observe, observe)
            history = np.stack((state, state, state, state), axis=2)
            history = np.reshape([history], (1, 9, 36, 4))

            while not dead:
                step += 1
                self.t += 1
                observe = next_observe
                # get action for the current history and go one step in environment
                action, policy = self.get_action(history)
                # change action to real_action
#                 if action == 0: real_action = 1
#                 elif action == 1: real_action = 2
#                 else: real_action = 3

                next_observe, reward = game.frame_step(action)
                # pre-process the observation --> history
                next_state = pre_processing(next_observe, observe)
                next_state = np.reshape([next_state], (1, 9, 36, 1))
                next_history = np.append(next_state, history[:, :, :, :3], axis=3)

                self.avg_p_max += np.amax(self.actor.predict(np.float32(history / 255.)))

                score += reward
#                 reward = np.clip(reward, -1., 1.)

                # save the sample <s, a, r, s'> to the replay memory
                self.memory(history, action, reward)

                # if agent is dead, then reset the history
                if dead:
                    history = np.stack((next_state, next_state, next_state, next_state), axis=2)
                    history = np.reshape([history], (1, 9, 36, 4))
                    dead = False
                else:
                    history = next_history

                #
                done = reward == -1
                if self.t >= self.t_max:
                    self.train_t(done)
                    self.t = 0

                # if done, plot the score over episodes
                if done:
                    episode += 1
                    print("episode:", episode, "  score:", score, "  step:", step)

#                     stats = [score, self.avg_p_max / float(step),
#                              step]
#                     for i in range(len(stats)):
#                         self.sess.run(self.update_ops[i], feed_dict={
#                             self.summary_placeholders[i]: float(stats[i])
#                         })
#                     summary_str = self.sess.run(self.summary_op)
#                     self.summary_writer.add_summary(summary_str, episode + 1)
                    self.avg_p_max = 0
                    self.avg_loss = 0
                    step = 0

    # In Policy Gradient, Q function is not available.
    # Instead agent uses sample returns for evaluating policy
    def discount_rewards(self, rewards, done):
        discounted_rewards = np.zeros_like(rewards)
        running_add = 0
        if not done:
            running_add = self.critic.predict(np.float32(self.states[-1] / 255.))[0]
        for t in reversed(range(0, len(rewards))):
            running_add = running_add * self.discount_factor + rewards[t]
            discounted_rewards[t] = running_add
        return discounted_rewards

    # update policy network and value network every episode
    def train_t(self, done):
        discounted_rewards = self.discount_rewards(self.rewards, done)

        states = np.zeros((len(self.states), 9, 36, 4))
        for i in range(len(self.states)):
            states[i] = self.states[i]

        states = np.float32(states / 255.)

        values = self.critic.predict(states)
        values = np.reshape(values, len(values))

        advantages = discounted_rewards - values

        self.optimizer[0]([states, self.actions, advantages])
        self.optimizer[1]([states, discounted_rewards])
        self.states, self.actions, self.rewards = [], [], []

    def get_action(self, history):
        history = np.float32(history / 255.)
        policy = self.actor.predict(history)[0]

        policy = policy - np.finfo(np.float32).epsneg

        histogram = np.random.multinomial(1, policy)
        action_index = int(np.nonzero(histogram)[0])
        return action_index, policy

    # save <s, a ,r> of each step
    # this is used for calculating discounted rewards
    def memory(self, history, action, reward):
        self.states.append(history)
        act = np.zeros(self.action_size)
        act[action] = 1
        self.actions.append(act)
        self.rewards.append(reward)


# 210*160*3(color) --> 84*84(mono)
# float --> integer (to reduce the size of replay memory)
def pre_processing(next_observe, observe):
    processed_observe = np.maximum(next_observe, observe)
    processed_observe = np.uint8(resize(rgb2gray(processed_observe), (9, 36), mode='constant') * 255)
    return processed_observe


if __name__ == "__main__":
    global_agent = A3CAgent(action_size=3)
    global_agent.train()
