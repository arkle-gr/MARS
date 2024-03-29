"""
Function for building agents
Actually, agents could have different networks.
However, for simplifying, all networks are built by the same structure and parameters (fc1 and fc2).
Only learning rates are given by two different variables (alpha and beta).

Using:
numpy: 1.22.4
pytroch: 1.12.0
"""
import numpy as np
import torch as T
from noise import OUNoise
from networks import ActorNetwork, CriticNetwork
from parameter import get_args

args = get_args()

class Agent:
    def __init__(self, actor_dims, critic_dims, n_actions, n_agents, agent_idx, chkpt_dir,
                alpha=0.01, beta=0.01, fc1=128, fc2=64, gamma=0.99, tau=0.01):
        """
        :param actor_dims: number of dimensions for the actor
        :param critic_dims: number of dimensions for the critic
        :param n_actions: number of actions
        :param n_agents: number of agents
        :param agent_idx: agent index
        :param chkpt_dir: check point directory
        :param alpha: learning rate of actor (target) network, default value is 0.01
        :param beta: learning rate of critic (target) network, default value is 0.01
        :param fc1: number of dimensions for first layer, default value is 128
        :param fc2: number of dimensions for second layer, default value is 64
        :param gamma: discount factor, default value is 0.99
        :param tau: tau of soft target updating,  default value is 0.01
        """
        self.gamma = gamma
        self.tau = tau
        self.n_actions = n_actions
        self.agent_name = 'agent_%s' % agent_idx
        self.critic_loss = []
        self.actor_loss = []
        self.actor = ActorNetwork(alpha, actor_dims, fc1, fc2, n_actions, 
                                  chkpt_dir=chkpt_dir,  name=self.agent_name+'_actor')
        self.critic = CriticNetwork(beta, critic_dims, fc1, fc2, n_agents, n_actions,
                                    chkpt_dir=chkpt_dir, name=self.agent_name+'_critic')
        self.target_actor = ActorNetwork(alpha, actor_dims, fc1, fc2, n_actions,
                                         chkpt_dir=chkpt_dir, name=self.agent_name+'_target_actor')
        self.target_critic = CriticNetwork(beta, critic_dims, fc1, fc2, n_agents, n_actions,
                                           chkpt_dir=chkpt_dir, name=self.agent_name+'_target_critic')

        self.update_network_parameters(tau=1)
        self.exploration_noise = OUNoise(self.n_actions,  mu=0, theta=0.1, sigma=0.1)

    def reset_noise(self):
        """
        Re-initialize the random process when an episode ends
        :return:
        """
        self.exploration_noise.reset()

    def choose_action(self, observation, allowed_actions, exploration, n_l=0.2):
        """
        :param observation:
        :param exploration: exploration flag
        :param n_l: limit of noise
        :return:
        """
        # observations need to be converted to a tensor
        # state = T.tensor([observation], dtype=T.float).to(self.actor.device)
        # Creating a tensor from a list of numpy.ndarrays is extremely slow.
        # Convert the list to a single numpy.ndarray before converting to a tensor.
        obs = np.array(observation)
        state = T.tensor(obs, dtype=T.float).to(self.actor.device)
        outputs = self.actor.forward(state) # action_value

        actions = outputs.data.cpu().numpy()

        if exploration == True:
            noise = self.exploration_noise.noise() 
            actions += np.clip(noise, -n_l, n_l) # type:numpy.ndarray
            actions = T.tensor(actions.copy(), dtype=T.float).to(self.actor.device) # transform to tensor
            #actions = actions.clamp(-1, 1)
            #actions = actions.clamp(-1, args.task_num - 1).int()
            allowed = np.zeros(args.task_num)
            allowed[allowed_actions] = np.array(actions)[allowed_actions] # 可选的任务的action values
            allowed[allowed == 0] = -np.inf
            action = np.argmax(allowed) # 选择最大的action value        
        else: # not add noise
            actions = T.tensor(actions.copy(), dtype=T.float).to(self.actor.device)
            # print('test_actions:', actions)
            allowed = np.zeros(args.task_num)
            # print('test_allowed_actions:', allowed_actions)
            allowed[allowed_actions] = np.array(actions)[allowed_actions] 
            allowed[allowed == 0] = -np.inf
            action = np.argmax(allowed) # 选择最大的action value  
            # print('test_action:', action)

        # tensors could not be used in codes, so the data need to be converted to numpy array
        return action

    def update_network_parameters(self, tau=None):
        """
        soft update target network via current network
        :param tau: tau of soft target updating
        :return:
        """
        if tau is None:
            tau = self.tau
        # actor part
        target_actor_params = self.target_actor.named_parameters()
        actor_params = self.actor.named_parameters()

        target_actor_state_dict = dict(target_actor_params)
        actor_state_dict = dict(actor_params)
        for name in actor_state_dict:
            actor_state_dict[name] = tau*actor_state_dict[name].clone() + \
                    (1-tau)*target_actor_state_dict[name].clone()

        self.target_actor.load_state_dict(actor_state_dict)
        # self.target_actor.load_state_dict(actor_state_dict, strict=False)
        # critic part (similar with actor part)
        target_critic_params = self.target_critic.named_parameters()
        critic_params = self.critic.named_parameters()

        target_critic_state_dict = dict(target_critic_params)
        critic_state_dict = dict(critic_params)
        for name in critic_state_dict:
            critic_state_dict[name] = tau*critic_state_dict[name].clone() + \
                    (1-tau)*target_critic_state_dict[name].clone()

        self.target_critic.load_state_dict(critic_state_dict)
        # self.target_critic.load_state_dict(critic_state_dict, strict=False)

    def save_models(self):
        self.actor.save_checkpoint()
        self.target_actor.save_checkpoint()
        self.critic.save_checkpoint()
        self.target_critic.save_checkpoint()

    def load_models(self):
        self.actor.load_checkpoint()
        self.target_actor.load_checkpoint()
        self.critic.load_checkpoint()
        self.target_critic.load_checkpoint()
