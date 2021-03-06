from typing import Tuple, Type, Union

import numpy as np

from genrl.deep.common.base import BaseValue
from genrl.deep.common.utils import cnn, mlp


def _get_val_model(
    arch: str,
    val_type: str,
    state_dim: str,
    hidden: Tuple,
    action_dim: int = None,
    activation: str = "relu",
):
    """
    Returns Neural Network given specifications

    :param arch: Specifies type of architecture "mlp" for MLP layers
    :param val_type: Specifies type of value function: (
"V" for V(s), "Qs" for Q(s), "Qsa" for Q(s,a))
    :param state_dim: State dimensions of environment
    :param action_dim: Action dimensions of environment
    :param hidden: Sizes of hidden layers
    :type arch: string
    :type val_type: string
    :type state_dim: string
    :type action_dim: int
    :type hidden: tuple or list
    :returns: Neural Network model to be used for the Value function
    """
    if val_type == "V":
        return arch([state_dim] + list(hidden) + [1], activation=activation)
    elif val_type == "Qsa":
        return arch(
            [state_dim + action_dim] + list(hidden) + [1], activation=activation
        )
    elif val_type == "Qs":
        return arch([state_dim] + list(hidden) + [action_dim], activation=activation)
    else:
        raise ValueError


class MlpValue(BaseValue):
    """
    MLP Value Function class

    :param state_dim: State dimensions of environment
    :param action_dim: Action dimensions of environment
    :param val_type: Specifies type of value function: (
"V" for V(s), "Qs" for Q(s), "Qsa" for Q(s,a))
    :param hidden: Sizes of hidden layers
    :type state_dim: int
    :type action_dim: int
    :type val_type: string
    :type hidden: tuple or list
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = None,
        val_type: str = "V",
        hidden: Tuple = (32, 32),
        **kwargs,
    ):
        super(MlpValue, self).__init__()

        self.state_dim = state_dim
        self.action_dim = action_dim

        activation = kwargs["activation"] if "activation" in kwargs else "relu"

        self.model = _get_val_model(
            mlp, val_type, state_dim, hidden, action_dim, activation
        )


class CNNValue(BaseValue):
    """
    CNN Value Function class

    :param framestack: Number of previous frames to stack together
    :param action_dim: Action dimension of environment
    :param val_type: Specifies type of value function: (
"V" for V(s), "Qs" for Q(s), "Qsa" for Q(s,a))
    :param fc_layers: Sizes of hidden layers
    :type framestack: int
    :type action_dim: int
    :type val_type: string
    :type fc_layers: tuple or list
    """

    def __init__(
        self,
        framestack: int,
        action_dim: int,
        val_type: str = "Qs",
        fc_layers: Tuple = (256,),
        **kwargs,
    ):
        super(CNNValue, self).__init__()

        self.action_dim = action_dim

        activation = kwargs["activation"] if "activation" in kwargs else "relu"

        self.conv, output_size = cnn((framestack, 16, 32), activation=activation)

        self.fc = _get_val_model(mlp, val_type, output_size, fc_layers, action_dim)

    def forward(self, state: np.ndarray) -> np.ndarray:
        state = self.conv(state)
        state = state.view(state.size(0), -1)
        value = self.fc(state)
        return value


value_registry = {"mlp": MlpValue, "cnn": CNNValue}


def get_value_from_name(name_: str) -> Union[Type[MlpValue], Type[CNNValue]]:
    """
    Gets the value function given the name of the value function

    :param name_: Name of the value function needed
    :type name_: string
    :returns: Value function
    """
    if name_ in value_registry:
        return value_registry[name_]
    raise NotImplementedError
