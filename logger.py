#
# NP AIG Assignment 1
# Logger
#

import mlflow
from abc import ABC, abstractmethod
from Globals import TEAM_NAME, MLFLOW_EXPERIMENT, MLFLOW_RUN


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

    @abstractmethod
    def file(self, path):
        """
        Log the file a the given path.
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
            metric_map={
                f"team_{TEAM_NAME[0]}_score": scores[0],
                f"team_{TEAM_NAME[1]}_score": scores[1],
            },
            step=step,
        )

    @abstractmethod
    def __enter__(self):
        """
        Start a logging run.
        """
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """
        End a logging run.
        """
        pass


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

    def file(self, path):
        pass

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class MLFlowLogger(Logger):
    """
    Defines a Logger that logs to MLFlow.
    Since networks calls to log to MLFlow are expensive, only logs metrics to MLFlow if they change.
    """

    def __init__(self):
        super().__init__()
        self.prev_metrics = {}
        mlflow.set_experiment(MLFLOW_EXPERIMENT)

    def __enter__(self):
        mlflow.start_run(run_name=MLFLOW_RUN)

    def __exit__(self, exc_type, exc_value, traceback):
        mlflow.end_run()

    def param(self, name, value):
        mlflow.log_param(name, value)

    def params(self, param_map):
        for k, v in param_map.items():
            self.param(k, v)

    def metric(self, name, value, step=None):
        # check for change in metrics before logging to mlflow
        if name in self.prev_metrics and self.prev_metrics[name] == value:
            return
        mlflow.log_metric(name, value, step)
        self.prev_metrics[name] = value

    def metrics(self, metric_map, step=None):
        for k, v in metric_map.items():
            self.metric(k, v, step)

    def file(self, path):
        mlflow.log_artifact(path)


loggers = {"NOPLogger": NOPLogger, "MLFlowLogger": MLFlowLogger}
