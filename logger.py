#
# NP AIG Assignment 1
# Run multiple trials of HAL and aggregate metrics
#

import mlflow
from abc import ABC, abstractmethod


class Logger(ABC):
    """
    Defines an abstract logger that logs parameters, metrics, and artifacts
    """

    @abstractmethod
    def param(self, name, value):
        """
        Log the given param with the given value
        """
        pass

    @abstractmethod
    def params(self, param_map):
        """
        Log the given params dictionary with keys as the name of the param
        and value as the value of the param.
        """
        pass

    @abstractmethod
    def metric(self, name, value, step=None):
        """
        Log the given metric with the given value
        Optionally provide a step to specify metric at different time steps.
        """
        pass

    @abstractmethod
    def metrics(self, metric_map, step=None):
        """
        Log the given metrics dictionary with keys as the name of the metric
        and value as the value of the metric.
        Optionally provide a step to specify metrics at different time steps.
        """
        pass

    def scores(self, scores, step=None):
        """
        Log the given scores to as metrics.
        Assumes scores is a iterable of size 2, first element being score of team A,
        second element being score of team B.
        Optionally provide a step to specify scores at different time steps.
        """
        self.metrics(
            {
                "team_a_score": scores[0],
                "team_b_score": scores[1],
            }
        )


class NOPLogger(Logger):
    """
    Defines a do nothing Logger.
    """

    def param(self, name, value):
        pass

    def params(self, param_map):
        pass

    def metric(self, name, value, step=None):
        pass

    def metrics(self, metric_map, step=None):
        pass


class MLFlowLogger(Logger):
    """
    Defines a Logger that logs to MLFlow.
    """

    def param(self, name, value):
        mlflow.log_param(name, value)

    def params(self, param_map):
        mlflow.log_params(param_map)

    def metric(self, name, value, step=None):
        mlflow.log_metric(name, value, step)

    def metrics(self, metric_map, step=None):
        mlflow.log_metrics(metric_map, step)
