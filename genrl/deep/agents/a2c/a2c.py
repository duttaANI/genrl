from typing import Any, Dict, Tuple, Union

import gym
import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as opt

from genrl.deep.agents.base import OnPolicyAgent
from genrl.deep.common import RolloutBuffer, get_env_properties, get_model, safe_mean
from genrl.environments.vec_env import VecEnv


class A2C(OnPolicyAgent):
    """
    Advantage Actor Critic algorithm (A2C)
    The synchronous version of A3C
    Paper: https://arxiv.org/abs/1602.01783

    :param network_type: The deep neural network layer types ['mlp']
    :param env: The environment to learn from
    :param gamma: Discount factor
    :param actor_batch_size: Update batch size
    :param lr_actor: Policy Network learning rate
    :param lr_critic: Value Network learning rate
    :param num_episodes: Number of episodes
    :param timesteps_per_actorbatch: Number of timesteps per epoch
    :param max_ep_len: Maximum timesteps in an episode
    :param layers: Number of neurons in hidden layers
    :param noise: Noise function to use
    :param noise_std: Standard deviation for action noise
    :param seed: Seed for reproducing results
    :param render: True if environment is to be rendered, else False
    :param device: Device to use for Tensor operation ['cpu', 'cuda']
    :param rollout_size: Rollout Buffer Size
    :param val_coeff: Coefficient of value loss in overall loss function
    :param entropy_coeff: Coefficient of entropy loss in overall loss function
    :type network_type: string
    :type env: Gym Environment
    :type gamma: float
    :type actor_batch_size: int
    :type lr_a: float
    :type lr_c: float
    :type num_episodes: int
    :type timesteps_per_actorbatch: int
    :type max_ep_len: int
    :type layers: tuple or list
    :type noise: function
    :type noise_std: float
    :type seed: int
    :type render: boolean
    :type device: string
    :type rollout_size: int
    :type val_coeff: float
    :type entropy_coeff: float
    """

    def __init__(
        self,
        network_type: str,
        env: Union[gym.Env, VecEnv],
        batch_size: int = 256,
        gamma: float = 0.99,
        lr_policy: float = 0.01,
        lr_value: float = 0.1,
        epochs: int = 100,
        max_ep_len: int = 1000,
        layers: Tuple = (32, 32),
        noise: Any = None,
        noise_std: float = 0.1,
        rollout_size: int = 2048,
        **kwargs
    ):

        super(A2C, self).__init__(
            network_type,
            env,
            batch_size,
            layers,
            gamma,
            lr_policy,
            lr_value,
            epochs,
            rollout_size,
            **kwargs
        )

        self.max_ep_len = max_ep_len
        self.noise = noise
        self.noise_std = noise_std
        self.value_coeff = kwargs.get("value_coeff", 0.5)
        self.entropy_coeff = kwargs.get("entropy_coeff", 0.01)

        self.empty_logs()
        self.create_model()

    def create_model(self) -> None:
        """
        Creates actor critic model and initialises optimizers
        """
        input_dim, action_dim, discrete, action_lim = get_env_properties(
            self.env, self.network_type
        )

        if self.noise is not None:
            self.noise = self.noise(
                np.zeros_like(action_dim), self.noise_std * np.ones_like(action_dim)
            )

        self.ac = get_model("ac", self.network_type)(
            input_dim, action_dim, self.layers, "V", discrete, action_lim=action_lim
        ).to(self.device)

        self.optimizer_policy = opt.Adam(self.ac.actor.parameters(), lr=self.lr_policy)
        self.optimizer_value = opt.Adam(self.ac.critic.parameters(), lr=self.lr_value)

        self.rollout = RolloutBuffer(self.rollout_size, self.env)

    def select_action(
        self, state: np.ndarray, deterministic: bool = False
    ) -> np.ndarray:
        """
        Selection of action

        :param state: Observation state
        :param deterministic: Action selection type
        :type state: int, float, ...
        :type deterministic: bool
        :returns: Action based on the state and epsilon value
        :rtype: int, float, ...
        """
        state = torch.as_tensor(state).float().to(self.device)

        # create distribution based on actor output
        action, dist = self.ac.get_action(state, deterministic=False)
        value = self.ac.get_value(state)

        return action.detach().cpu().numpy(), value, dist.log_prob(action).cpu()

    def get_traj_loss(self, values, dones) -> None:
        """
        (Get trajectory of agent to calculate discounted rewards and
calculate losses)
        """
        self.rollout.compute_returns_and_advantage(values.detach().cpu().numpy(), dones)

    def get_value_log_probs(self, state, action):
        state, action = state.to(self.device), action.to(self.device)
        _, dist = self.ac.get_action(state, deterministic=False)
        value = self.ac.get_value(state)
        return value, dist.log_prob(action).cpu()

    def update_policy(self) -> None:
        for rollout in self.rollout.get(self.batch_size):
            actions = rollout.actions

            if isinstance(self.env.action_space, gym.spaces.Discrete):
                actions = actions.long().flatten()

            values, log_prob = self.get_value_log_probs(rollout.observations, actions)

            policy_loss = rollout.advantages * log_prob
            policy_loss = -torch.mean(policy_loss)
            self.logs["policy_loss"].append(policy_loss.item())

            value_loss = self.value_coeff * F.mse_loss(rollout.returns, values.cpu())
            self.logs["value_loss"].append(torch.mean(value_loss).item())

            entropy_loss = (torch.exp(log_prob) * log_prob).sum()
            self.logs["policy_entropy"].append(entropy_loss.item())

            actor_loss = policy_loss + self.entropy_coeff * entropy_loss

            self.optimizer_policy.zero_grad()
            actor_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.ac.actor.parameters(), 0.5)
            self.optimizer_policy.step()

            self.optimizer_value.zero_grad()
            value_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.ac.critic.parameters(), 0.5)
            self.optimizer_value.step()

    def get_hyperparams(self) -> Dict[str, Any]:
        """
        Loads important hyperparameters that need to be loaded or saved

        :returns: Hyperparameters that need to be saved or loaded
        :rtype: dict
        """
        hyperparams = {
            "network_type": self.network_type,
            "batch_size": self.batch_size,
            "gamma": self.gamma,
            "lr_actor": self.lr_actor,
            "lr_critic": self.lr_critic,
            "rollout_size": self.rollout_size,
            "policy_weights": self.ac.actor.state_dict(),
            "value_weights": self.ac.critic.state_dict(),
        }

        return hyperparams

    def load_weights(self, weights) -> None:
        """
        Load weights for the agent from pretrained model
        """
        self.ac.actor.load_state_dict(weights["policy_weights"])
        self.ac.critic.load_state_dict(weights["value_weights"])

    def get_logging_params(self) -> Dict[str, Any]:
        """
        :returns: Logging parameters for monitoring training
        :rtype: dict
        """

        logs = {
            "policy_loss": safe_mean(self.logs["policy_loss"]),
            "value_loss": safe_mean(self.logs["value_loss"]),
            "policy_entropy": safe_mean(self.logs["policy_entropy"]),
            "mean_reward": safe_mean(self.rewards),
        }

        self.empty_logs()
        return logs

    def empty_logs(self):
        """
        Empties logs
        """

        self.logs = {}
        self.logs["policy_loss"] = []
        self.logs["value_loss"] = []
        self.logs["policy_entropy"] = []
        self.rewards = []
