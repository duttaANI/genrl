import numpy as np

from genrl.classical.bandit.contextual_bandits import ContextualBandit
from genrl.classical.bandit.contextual_policies.base import CBPolicy


class UCBCBPolicy(CBPolicy):
    """
    Multi-Armed Bandit Solver with Upper Confidence Bound based
    Action Selection Strategy.

    Refer to Section 2.7 of Reinforcement Learning: An Introduction.

    :param bandit: The Bandit to solve
    :param c: Confidence level which controls degree of exploration
    :type bandit: ContextualBandit type object
    :type c: float
    """

    def __init__(self, bandit: ContextualBandit, confidence: float = 1.0):
        super(UCBCBPolicy, self).__init__(bandit)
        self._c = confidence
        self._quality = np.zeros(shape=(bandit.bandits, bandit.arms))
        self._counts = np.zeros(shape=(bandit.bandits, bandit.arms))

    @property
    def confidence(self) -> float:
        """
        Get the confidence level which weights the exploration term

        :returns: Confidence level which controls degree of exploration
        :rtype: float
        """
        return self._c

    @property
    def quality(self) -> np.ndarray:
        """
        Get the q values assigned by the policy to all actions

        :returns: Numpy array of q values for all actions
        :rtype: numpy.ndarray
        """
        return self._quality

    def select_action(self, context: int, t: int) -> int:
        """
        Select an action according to upper confidence bound action selction

        Take action that maximises a weighted sum of the Q values for the action
        and an exploration encouragement term controlled by c.

        :param context: the context to select action for
        :param t: timestep to choose action for
        :type context: int
        :type t: int
        :returns: Selected action
        :rtype: int
        """
        action = np.argmax(
            self.quality[context]
            + self.confidence * np.sqrt(2 * np.log(t + 1) / (self.counts[context] + 1))
        )
        self.action_hist.append((context, action))
        return action

    def update_params(self, context: int, action: int, reward: float) -> None:
        """
        Update parmeters for the policy

        Updates the regret as the difference between max Q value and
        that of the action. Updates the Q values according to the
        reward recieved in this step.

        :param context: context for which action is taken
        :param action: action taken for the step
        :param reward: reward obtained for the step
        :type context: int
        :type action: int
        :type reward: float
        """
        self.reward_hist.append(reward)
        self._regret += max(self.quality[context]) - self.quality[context, action]
        self.regret_hist.append(self.regret)
        self.quality[context, action] += (reward - self.quality[context, action]) / (
            self.counts[context, action] + 1
        )
        self.counts[context, action] += 1
